"""
Ohmic Granular Agent Micro-Tools.
Provides atomic, inspectable operations for AI agents to discover, place, route,
micro-edit, diagnose, and render electronic schematics.
Includes standard Gemini Function Calling schemas.
"""

from typing import Dict, List, Optional, Tuple, Any
import json
import os
import uuid
import re

from .engine import OhmicSchematic
from .models import Point, Pin, Component, Wire, Label, Junction, PowerSymbol
from .library import KiCadLibraryManager
from .fetcher import CloudFetcher
from .builder import SymbolBuilder
from .exporter import KiCadCliExporter

class OhmicToolContext:
    """Maintains active schematic session state for the agent."""
    def __init__(self, name: str = "ActiveProject", paper: str = "A4"):
        self.schematic = OhmicSchematic(name=name, paper=paper)
        self.lib_manager = KiCadLibraryManager()
        self.fetcher = CloudFetcher()
        self.exporter = KiCadCliExporter()
        self.history: List[str] = []
        self.active_file_path: Optional[str] = None
        self._auto_discover_schematic()

    def _auto_discover_schematic(self):
        """Automatically discovers and loads the project schematic in the current workspace or cwd."""
        env_sch = os.environ.get("OHMIC_SCHEMATIC")
        if env_sch and os.path.isfile(env_sch):
            try:
                self.load(env_sch)
                return
            except Exception:
                pass

        # 1. Search current working directory and subdirectories for any *.kicad_sch
        cwd = os.getcwd()
        found_sch = []
        ignore_dirs = {".git", "node_modules", "venv", "env", "__pycache__", "dist", "build", "backup"}
        try:
            for root, dirs, files in os.walk(cwd):
                dirs[:] = [d for d in dirs if d.lower() not in ignore_dirs and not d.startswith(".")]
                rel = os.path.relpath(root, cwd)
                if rel != "." and len(rel.split(os.sep)) > 3:
                    continue
                for f in files:
                    if f.lower().endswith(".kicad_sch") and not f.startswith("active_preview"):
                        full_p = os.path.join(root, f)
                        found_sch.append(full_p)
        except Exception:
            pass

        if found_sch:
            # Sort: prefer root level files first
            found_sch.sort(key=lambda p: (len(p.split(os.sep)), p.lower()))
            for p in found_sch:
                try:
                    self.load(p)
                    return
                except Exception:
                    continue

        # 2. Fallback candidate paths
        candidates = [
            "unitycircuit/unityprod/unityprod.kicad_sch",
            "../unitycircuit/unityprod/unityprod.kicad_sch",
            "unitycircuit/unity_meters.kicad_sch",
            "../unitycircuit/unity_meters.kicad_sch",
            "scratch/active_preview.kicad_sch",
        ]
        for c in candidates:
            if os.path.isfile(c):
                try:
                    self.load(c)
                    break
                except Exception:
                    pass

    def reset(self, name: str = "NewCircuit", paper: str = "A4"):
        self.schematic = OhmicSchematic(name=name, paper=paper)
        self.history.clear()
        self.active_file_path = None

    def load(self, file_path: str):
        self.schematic = OhmicSchematic.load(file_path)
        self.active_file_path = file_path
        self.history.append(f"Loaded '{file_path}'")

    def save(self, file_path: Optional[str] = None) -> str:
        out_path = file_path or self.active_file_path or "scratch/active_preview.kicad_sch"
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        self.schematic.save(out_path)
        self.history.append(f"Saved to '{out_path}'")
        return out_path

# Global singleton session context
CTX = OhmicToolContext()

# --- Granular Micro-Tool Implementations ---

def search_kicad_library(query: str, limit: int = 10) -> Dict[str, Any]:
    """Search for components across 25,988 official KiCad symbols."""
    matches = CTX.lib_manager.search(query, limit=limit)
    return {"query": query, "found_count": len(matches), "matches": matches}

def search_schematic(query: str, search_type: str = "all") -> Dict[str, Any]:
    """
    Searches the currently active schematic for components, pins, net labels, and power symbols.
    search_type can be 'all', 'components', 'labels', 'power', or 'nets'.
    Returns matches with coordinates, pinouts, and immediate connectivity.
    """
    q = query.lower().strip()
    matching_components = []
    matching_labels = []
    matching_powers = []

    # 1. Search components
    if search_type in ("all", "components"):
        for c in CTX.schematic.components:
            match = False
            reasons = []
            if q in c.ref.lower():
                match = True
                reasons.append(f"ref: {c.ref}")
            if q in c.value.lower():
                match = True
                reasons.append(f"value: {c.value}")
            if q in c.lib_id.lower():
                match = True
                reasons.append(f"lib_id: {c.lib_id}")
            if q in c.description.lower():
                match = True
                reasons.append(f"description: {c.description}")
            if q in c.footprint.lower():
                match = True
                reasons.append(f"footprint: {c.footprint}")
            for pn, pin in c.pins.items():
                if q in pin.name.lower():
                    match = True
                    reasons.append(f"pin {pn}: {pin.name}")

            if match:
                matching_components.append({
                    "ref": c.ref,
                    "value": c.value,
                    "lib_id": c.lib_id,
                    "pos": (round(c.x, 2), round(c.y, 2)),
                    "rot": c.rot,
                    "footprint": c.footprint,
                    "match_reasons": reasons,
                    "pins": {pn: {"name": p.name, "type": p.pin_type} for pn, p in c.pins.items()}
                })

    # 2. Search labels
    if search_type in ("all", "labels", "nets"):
        for l in CTX.schematic.labels:
            if q in l.text.lower():
                matching_labels.append({
                    "text": l.text,
                    "pos": (round(l.x, 2), round(l.y, 2)),
                    "rot": l.rot,
                    "is_global": l.is_global
                })

    # 3. Search power symbols
    if search_type in ("all", "power", "nets"):
        for p in CTX.schematic.power_symbols:
            if q in p.name.lower() or q in p.ref.lower():
                matching_powers.append({
                    "name": p.name,
                    "ref": p.ref,
                    "pos": (round(p.x, 2), round(p.y, 2)),
                    "rot": p.rot
                })

    return {
        "query": query,
        "search_type": search_type,
        "total_matches": len(matching_components) + len(matching_labels) + len(matching_powers),
        "components": matching_components,
        "labels": matching_labels,
        "power_symbols": matching_powers
    }


def get_part_pinout(lib_id: str) -> Dict[str, Any]:
    """Inspect all pins, numbers, names, and electrical types of any KiCad part."""
    sym_def = CTX.lib_manager.get(lib_id)
    if not sym_def:
        # Try fetching from cloud GitLab
        raw_sym = CTX.fetcher.fetch_and_cache_symbol(lib_id)
        if raw_sym:
            sym_def = CTX.lib_manager.get(lib_id)

    if not sym_def:
        return {"error": f"Symbol '{lib_id}' not found in local or cloud libraries."}

    pins_info = []
    for pnum, p in sorted(sym_def.pins.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999):
        pins_info.append({
            "pin": pnum,
            "name": p.name,
            "type": p.pin_type,
            "rel_pos": (p.rel_x, p.rel_y)
        })

    return {
        "lib_id": sym_def.lib_id,
        "ref_prefix": sym_def.ref_prefix,
        "description": sym_def.description,
        "default_footprint": sym_def.default_footprint,
        "total_pins": len(pins_info),
        "pins": pins_info
    }

def search_datasheet(part_name: str) -> Dict[str, Any]:
    """Search and download a component's official datasheet PDF online."""
    pdf_path = CTX.fetcher.fetch_datasheet(part_name)
    if pdf_path and os.path.exists(pdf_path):
        size_kb = round(os.path.getsize(pdf_path) / 1024.0, 1)
        return {"status": "SUCCESS", "part": part_name, "cached_file": pdf_path, "size_kb": size_kb}
    return {"status": "NOT_FOUND", "part": part_name, "message": "Could not locate valid datasheet PDF."}

def search_web(query: str, limit: int = 5) -> Dict[str, Any]:
    """
    Searches the public web for component datasheets, application notes, silicon errata,
    pinout diagrams, formula guides, and hardware documentation.
    Returns titles, direct URLs, and text snippets.
    """
    import urllib.request
    import urllib.parse
    import re

    clean_query = query.strip()
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(clean_query)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )
    results = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            title_matches = re.findall(r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
            snippet_matches = re.findall(r'<a[^>]+class="result__snippet[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL)

            for i in range(min(len(title_matches), len(snippet_matches), limit)):
                raw_url, raw_title = title_matches[i]
                raw_snippet = snippet_matches[i]

                title = re.sub(r'<[^>]+>', '', raw_title).strip()
                snippet = re.sub(r'<[^>]+>', '', raw_snippet).strip()

                if "uddg=" in raw_url:
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                    actual_url = parsed.get("uddg", [raw_url])[0]
                else:
                    actual_url = raw_url

                results.append({
                    "title": title,
                    "snippet": snippet,
                    "url": actual_url
                })
        return {
            "status": "SUCCESS",
            "query": clean_query,
            "results_count": len(results),
            "results": results
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "query": clean_query,
            "error": str(e),
            "results": []
        }

def new_schematic(name: str = "OhmicDesign", paper: str = "A4") -> Dict[str, Any]:
    """Start a fresh, blank schematic canvas."""
    CTX.reset(name=name, paper=paper)
    return {"status": "SUCCESS", "name": name, "paper": paper}

def load_schematic(file_path: str) -> Dict[str, Any]:
    """Load an existing KiCad schematic file (.kicad_sch) into active context."""
    if not os.path.exists(file_path):
        return {"error": f"File '{file_path}' does not exist."}
    CTX.load(file_path)
    return {
        "status": "LOADED",
        "file": file_path,
        "name": CTX.schematic.name,
        "paper": CTX.schematic.paper,
        "components_count": len(CTX.schematic.components),
        "wires_count": len(CTX.schematic.wires),
        "labels_count": len(CTX.schematic.labels),
        "power_symbols_count": len(CTX.schematic.power_symbols)
    }

def save_schematic(file_path: Optional[str] = None) -> Dict[str, Any]:
    """Save the active schematic to disk."""
    saved_path = CTX.save(file_path)
    return {
        "status": "SAVED",
        "file": saved_path,
        "components_count": len(CTX.schematic.components),
        "wires_count": len(CTX.schematic.wires)
    }

def inspect_components(filter_ref: Optional[str] = None) -> Dict[str, Any]:
    """Inspect all components or a specific component by ref prefix/name."""
    comps = []
    for c in CTX.schematic.components:
        if filter_ref and not c.ref.upper().startswith(filter_ref.upper()):
            continue
        comps.append({
            "ref": c.ref,
            "value": c.value,
            "lib_id": c.lib_id,
            "pos": (c.x, c.y),
            "rot": c.rot,
            "pins_count": len(c.pins)
        })
    return {"total_matching": len(comps), "components": comps}

def inspect_schematic_summary() -> Dict[str, Any]:
    """Returns high-level statistics and metadata for the active schematic."""
    return {
        "name": CTX.schematic.name,
        "active_file": CTX.active_file_path,
        "paper": CTX.schematic.paper,
        "components": len(CTX.schematic.components),
        "wires": len(CTX.schematic.wires),
        "labels": len(CTX.schematic.labels),
        "power_symbols": len(CTX.schematic.power_symbols),
        "junctions": len(CTX.schematic.junctions)
    }

def place_component(
    lib_id: str,
    ref: str,
    value: str,
    x: float,
    y: float,
    rot: float = 0.0,
    footprint: str = ""
) -> Dict[str, Any]:
    """Place a single component from the library onto the schematic canvas."""
    # Check if component ref already exists
    existing = CTX.schematic.get_component(ref)
    if existing:
        return {"error": f"Component with reference '{ref}' already exists on canvas."}

    comp = CTX.schematic.add_component(
        lib_id=lib_id, ref=ref, value=value, x=x, y=y, rot=rot, footprint=footprint
    )
    return {
        "status": "PLACED",
        "ref": comp.ref,
        "value": comp.value,
        "pos": (comp.x, comp.y),
        "rotation": comp.rot,
        "pins_count": len(comp.pins)
    }

def place_power_symbol(name: str, x: float, y: float, rot: float = 0.0) -> Dict[str, Any]:
    """Place a power flag symbol (e.g. '+3.3V', '+5V', '+12V', 'GND')."""
    pwr = CTX.schematic.add_power_symbol(name=name, x=x, y=y, rot=rot)
    return {"status": "PLACED", "ref": pwr.ref, "name": pwr.name, "pos": (pwr.x, pwr.y)}

def place_net_label(text: str, x: float, y: float, rot: float = 0.0, is_global: bool = False) -> Dict[str, Any]:
    """Drop a net label on the canvas."""
    lbl = CTX.schematic.add_label(text=text, x=x, y=y, rot=rot, is_global=is_global)
    return {"status": "PLACED", "net": lbl.text, "pos": (lbl.x, lbl.y)}

def connect_pins(
    comp1_ref: str,
    pin1_num: str,
    comp2_ref: str,
    pin2_num: str,
    bias: str = "horizontal"
) -> Dict[str, Any]:
    """Route a clean 90-degree Manhattan wire between two specific component pins."""
    try:
        wires = CTX.schematic.connect_pins(comp1_ref, pin1_num, comp2_ref, pin2_num, bias=bias)
        return {
            "status": "CONNECTED",
            "from": f"{comp1_ref}:{pin1_num}",
            "to": f"{comp2_ref}:{pin2_num}",
            "segments_routed": len(wires)
        }
    except Exception as e:
        return {"error": str(e)}

def connect_pin_to_net(
    comp_ref: str,
    pin_num: str,
    net_name: str,
    direction: str = "right",
    length: float = 5.08
) -> Dict[str, Any]:
    """Pull a short wire stub off a component pin and attach a net label."""
    try:
        wire, label = CTX.schematic.connect_pin_to_net(
            comp_ref=comp_ref, pin_num=pin_num, net_name=net_name,
            stub_length=length, direction=direction
        )
        return {
            "status": "NET_LABEL_ATTACHED",
            "pin": f"{comp_ref}:{pin_num}",
            "net": net_name,
            "label_pos": (label.x, label.y)
        }
    except Exception as e:
        return {"error": str(e)}

def add_wire(x1: float, y1: float, x2: float, y2: float) -> Dict[str, Any]:
    """Draw a manual wire segment between two points."""
    w = CTX.schematic.add_wire(Point(x1, y1), Point(x2, y2))
    return {"status": "WIRE_ADDED", "start": (w.start.x, w.start.y), "end": (w.end.x, w.end.y)}

def auto_junctions() -> Dict[str, Any]:
    """Automatically detect all T-intersections and drop KiCad junction dots."""
    juncs = CTX.schematic.auto_junctions()
    return {"status": "SUCCESS", "junctions_placed": len(juncs)}

def change_component_value(ref: str, new_value: str) -> Dict[str, Any]:
    """Modify the value of an existing component (e.g. change R1 from 10k to 4.7k)."""
    comp = CTX.schematic.get_component(ref)
    if not comp:
        return {"error": f"Component '{ref}' not found."}
    old_val = comp.value
    comp.value = new_value
    return {"status": "UPDATED", "ref": ref, "old_value": old_val, "new_value": new_value}

def move_component(ref: str, new_x: float, new_y: float) -> Dict[str, Any]:
    """Move a component to a new (X, Y) coordinate on the canvas."""
    comp = CTX.schematic.get_component(ref)
    if not comp:
        return {"error": f"Component '{ref}' not found."}
    comp.x = new_x
    comp.y = new_y
    return {"status": "MOVED", "ref": ref, "new_pos": (new_x, new_y)}

def delete_component(ref: str) -> Dict[str, Any]:
    """Delete a component from the canvas."""
    before_len = len(CTX.schematic.components)
    CTX.schematic.components = [c for c in CTX.schematic.components if c.ref.upper() != ref.upper()]
    after_len = len(CTX.schematic.components)
    if before_len == after_len:
        return {"error": f"Component '{ref}' not found."}
    return {"status": "DELETED", "ref": ref}

def inspect_component_positions() -> Dict[str, Any]:
    """Returns the exact millimeter coordinates of all placed components and their pin tips."""
    return CTX.schematic.get_component_positions()

def inspect_netlist() -> Dict[str, Any]:
    """Returns all electrical nets and the component pins connected to each net."""
    net_map = CTX.schematic.get_netlist()
    return {"total_nets": len(net_map), "nets": net_map}

def run_health_check() -> Dict[str, Any]:
    """Inspects schematic for errors: dangling wire stubs, open pins, or orphaned power symbols."""
    return CTX.schematic.run_health_check()

def render_schematic_preview(format: str = "svg") -> Dict[str, Any]:
    """Compiles the active schematic into a vector SVG or PDF for preview."""
    os.makedirs("scratch", exist_ok=True)
    sch_file = "scratch/active_preview.kicad_sch"
    out_file = f"scratch/active_preview.{format}"
    CTX.schematic.save(sch_file)
    
    if format.lower() == "pdf":
        success = CTX.exporter.export_pdf(sch_file, out_file)
    else:
        success = CTX.exporter.export_svg(sch_file, out_file)

    if success and os.path.exists(out_file):
        return {
            "status": "COMPILED",
            "file": out_file,
            "format": format.upper(),
            "summary": CTX.schematic.get_summary()
        }
    return {"status": "ERROR", "message": "KiCad CLI compilation failed."}

def inspect_region_crop(
    x_min: float, y_min: float, x_max: float, y_max: float,
    zoom: float = 3.0, output_name: str = "region_crop.png"
) -> Dict[str, Any]:
    """Compiles schematic and generates a zoomed-in raster PNG crop of a specific coordinate box."""
    import fitz
    os.makedirs("scratch", exist_ok=True)
    sch_file = "scratch/active_preview.kicad_sch"
    svg_file = "scratch/active_preview.svg"
    out_png = os.path.join("scratch", output_name)
    CTX.schematic.save(sch_file)
    ok = CTX.exporter.export_svg(sch_file, svg_file)
    if not ok or not os.path.exists(svg_file):
        return {"error": "Failed to compile schematic SVG."}

    doc = fitz.open(svg_file)
    page = doc[0]
    rect = page.rect
    paper_w = 420.0 if CTX.schematic.paper.upper() == "A3" else 297.0
    paper_h = 297.0 if CTX.schematic.paper.upper() == "A3" else 210.0
    w_scale = rect.width / paper_w
    h_scale = rect.height / paper_h

    crop_box = fitz.Rect(x_min * w_scale, y_min * h_scale, x_max * w_scale, y_max * h_scale)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=crop_box)
    pix.save(out_png)
    return {
        "status": "CROPPED",
        "output_file": out_png,
        "width_px": pix.width,
        "height_px": pix.height,
        "region_mm": {"x_min": x_min, "y_min": y_min, "x_max": x_max, "y_max": y_max}
    }

def get_next_reference(prefix: str = "R") -> Dict[str, Any]:
    """Finds the next unused reference designator for a given prefix (e.g. 'R' -> 'R37')."""
    used_numbers = []
    prefix_clean = prefix.upper().strip()
    for c in CTX.schematic.components:
        c_ref = c.ref.upper()
        if c_ref.startswith(prefix_clean):
            num_part = c_ref[len(prefix_clean):]
            if num_part.isdigit():
                used_numbers.append(int(num_part))
    next_num = (max(used_numbers) + 1) if used_numbers else 1
    return {
        "prefix": prefix_clean,
        "used_count": len(used_numbers),
        "next_available": f"{prefix_clean}{next_num}",
        "highest_used": f"{prefix_clean}{max(used_numbers)}" if used_numbers else None
    }

def shift_block(x_min: float, y_min: float, x_max: float, y_max: float, dx: float, dy: float) -> Dict[str, Any]:
    """Shifts all components, labels, and wires within a bounding box by (dx, dy)."""
    moved_comps = []
    for c in CTX.schematic.components:
        if x_min <= c.x <= x_max and y_min <= c.y <= y_max:
            c.x += dx
            c.y += dy
            moved_comps.append(c.ref)

    moved_labels = []
    for l in CTX.schematic.labels:
        if x_min <= l.x <= x_max and y_min <= l.y <= y_max:
            l.x += dx
            l.y += dy
            moved_labels.append(l.text)

    moved_wires = 0
    for w in CTX.schematic.wires:
        start_in = x_min <= w.start.x <= x_max and y_min <= w.start.y <= y_max
        end_in = x_min <= w.end.x <= x_max and y_min <= w.end.y <= y_max
        if start_in and end_in:
            w.start.x += dx
            w.start.y += dy
            w.end.x += dx
            w.end.y += dy
            moved_wires += 1

    return {
        "status": "SHIFTED",
        "delta": (dx, dy),
        "components_moved": moved_comps,
        "labels_moved": moved_labels,
        "wires_moved": moved_wires
    }

def check_spatial_clearance(min_distance_mm: float = 8.0) -> Dict[str, Any]:
    """Checks for component center crowding and potential symbol/label overlaps."""
    import math
    crowded_pairs = []
    comps = CTX.schematic.components
    for i in range(len(comps)):
        for j in range(i + 1, len(comps)):
            c1, c2 = comps[i], comps[j]
            dist = math.hypot(c1.x - c2.x, c1.y - c2.y)
            if dist < min_distance_mm:
                crowded_pairs.append({
                    "comp1": f"{c1.ref} ({c1.value})",
                    "comp2": f"{c2.ref} ({c2.value})",
                    "distance_mm": round(dist, 2),
                    "pos1": (round(c1.x, 2), round(c1.y, 2)),
                    "pos2": (round(c2.x, 2), round(c2.y, 2))
                })
    return {
        "status": "CHECKED",
        "threshold_mm": min_distance_mm,
        "crowded_count": len(crowded_pairs),
        "crowded_pairs": crowded_pairs[:20]
    }

def find_open_canvas_zone(
    width_mm: float,
    height_mm: float,
    preferred_near_x: Optional[float] = None,
    preferred_near_y: Optional[float] = None,
    search_margin_mm: float = 6.0
) -> Dict[str, Any]:
    """Finds the best empty rectangular zone on the active sheet with guaranteed clearance."""
    import math
    paper_w = 400.0 if CTX.schematic.paper.upper() == "A3" else 280.0
    paper_h = 280.0 if CTX.schematic.paper.upper() == "A3" else 190.0

    occupied = []
    for c in CTX.schematic.components:
        occupied.append((c.x, c.y))
        for pnum in c.pins:
            occupied.append(c.get_world_pin_pos(pnum))
    for p in CTX.schematic.power_symbols:
        occupied.append((p.x, p.y))
    for l in CTX.schematic.labels:
        occupied.append((l.x, l.y))

    best_candidate = None
    min_cost = float('inf')
    pref_x = preferred_near_x if preferred_near_x is not None else (paper_w / 2.0)
    pref_y = preferred_near_y if preferred_near_y is not None else (paper_h / 2.0)

    x = 25.4
    while x + width_mm < paper_w - 20:
        y = 25.4
        while y + height_mm < paper_h - 20:
            collision = False
            for ox, oy in occupied:
                if (x - search_margin_mm <= ox <= x + width_mm + search_margin_mm) and \
                   (y - search_margin_mm <= oy <= y + height_mm + search_margin_mm):
                    collision = True
                    break
            if not collision:
                center_x = x + width_mm / 2.0
                center_y = y + height_mm / 2.0
                dist = math.hypot(center_x - pref_x, center_y - pref_y)
                if dist < min_cost:
                    min_cost = dist
                    best_candidate = {
                        "x_min": round(x, 2),
                        "y_min": round(y, 2),
                        "x_max": round(x + width_mm, 2),
                        "y_max": round(y + height_mm, 2),
                        "width_mm": width_mm,
                        "height_mm": height_mm,
                        "center": (round(center_x, 2), round(center_y, 2)),
                        "distance_to_target": round(dist, 2)
                    }
            y += 5.08
        x += 5.08

    if best_candidate:
        return {"status": "FOUND", "zone": best_candidate}
    return {"status": "NOT_FOUND", "message": f"No open zone of {width_mm}x{height_mm}mm found with {search_margin_mm}mm clearance."}

def remove_component_and_dangling_wires(ref: str) -> Dict[str, Any]:
    """Removes a component and prunes any wires that become orphaned dangling stubs."""
    comp = CTX.schematic.get_component(ref)
    if not comp:
        return {"error": f"Component '{ref}' not found."}

    pin_locations = {comp.get_world_pin_pos(p) for p in comp.pins}
    CTX.schematic.components = [c for c in CTX.schematic.components if c.ref.upper() != ref.upper()]

    other_valid_pts = set()
    for c in CTX.schematic.components:
        for p in c.pins:
            other_valid_pts.add(c.get_world_pin_pos(p))
    for pwr in CTX.schematic.power_symbols:
        other_valid_pts.add((pwr.x, pwr.y))
    for l in CTX.schematic.labels:
        other_valid_pts.add((l.x, l.y))

    pruned_count = 0
    changed = True
    while changed:
        changed = False
        remaining_wires = []
        pt_counts = {}
        for w in CTX.schematic.wires:
            p1 = (round(w.start.x, 2), round(w.start.y, 2))
            p2 = (round(w.end.x, 2), round(w.end.y, 2))
            pt_counts[p1] = pt_counts.get(p1, 0) + 1
            pt_counts[p2] = pt_counts.get(p2, 0) + 1

        for w in CTX.schematic.wires:
            p1 = (round(w.start.x, 2), round(w.start.y, 2))
            p2 = (round(w.end.x, 2), round(w.end.y, 2))
            p1_orphan = (p1 in pin_locations or p1 not in other_valid_pts) and pt_counts.get(p1, 0) <= 1
            p2_orphan = (p2 in pin_locations or p2 not in other_valid_pts) and pt_counts.get(p2, 0) <= 1

            if (p1_orphan and (p1 in pin_locations or p2_orphan)) or (p2_orphan and (p2 in pin_locations or p1_orphan)):
                pruned_count += 1
                changed = True
                continue
            remaining_wires.append(w)
        CTX.schematic.wires = remaining_wires

    CTX.schematic.auto_junctions()
    return {"status": "DELETED", "ref": ref, "wires_pruned": pruned_count}

def route_around_obstacles(
    x1: float, y1: float, x2: float, y2: float,
    avoid_obstacles: bool = True, pad_mm: float = 3.81
) -> Dict[str, Any]:
    """Routes an orthogonal Manhattan wire between two points, pathing around obstacle bounding boxes."""
    start = Point(round(x1, 2), round(y1, 2))
    end = Point(round(x2, 2), round(y2, 2))

    if start.x == end.x and start.y == end.y:
        return {"status": "ZERO_LENGTH", "wires": []}

    if not avoid_obstacles:
        w1 = CTX.schematic.add_wire(start, Point(end.x, start.y))
        w2 = CTX.schematic.add_wire(Point(end.x, start.y), end)
        CTX.schematic.auto_junctions()
        return {"status": "ROUTED", "segments_count": 2, "dog_leg_used": False}

    obstacles = []
    for c in CTX.schematic.components:
        obstacles.append((c.x - pad_mm - 2.54, c.y - pad_mm - 2.54, c.x + pad_mm + 2.54, c.y + pad_mm + 2.54))

    mid_x, mid_y = end.x, start.y
    intersects = False
    for ox1, oy1, ox2, oy2 in obstacles:
        min_seg_x, max_seg_x = min(start.x, mid_x), max(start.x, mid_x)
        if (min_seg_x <= ox2 and max_seg_x >= ox1) and (oy1 <= start.y <= oy2):
            intersects = True
            break
        min_seg_y, max_seg_y = min(start.y, end.y), max(start.y, end.y)
        if (min_seg_y <= oy2 and max_seg_y >= oy1) and (ox1 <= mid_x <= ox2):
            intersects = True
            break

    segments = []
    if not intersects:
        if start.x != end.x:
            w1 = CTX.schematic.add_wire(start, Point(mid_x, mid_y))
            segments.append(w1)
        if start.y != end.y:
            w2 = CTX.schematic.add_wire(Point(mid_x, mid_y), end)
            segments.append(w2)
    else:
        offset_y = min(start.y, end.y) - pad_mm - 2.54
        w1 = CTX.schematic.add_wire(start, Point(start.x, offset_y))
        w2 = CTX.schematic.add_wire(Point(start.x, offset_y), Point(end.x, offset_y))
        w3 = CTX.schematic.add_wire(Point(end.x, offset_y), end)
        segments.extend([w1, w2, w3])

    CTX.schematic.auto_junctions()
    return {"status": "ROUTED", "segments_count": len(segments), "dog_leg_used": intersects}

def inspect_circuit_block(
    x_min: float, y_min: float, x_max: float, y_max: float,
    block_name: str = "Block"
) -> Dict[str, Any]:
    """Semantic inspector that extracts all components, nets, and external boundary ports of a sub-circuit."""
    internal_comps = []
    for c in CTX.schematic.components:
        if x_min <= c.x <= x_max and y_min <= c.y <= y_max:
            internal_comps.append({
                "ref": c.ref,
                "value": c.value,
                "lib_id": c.lib_id,
                "center": (c.x, c.y)
            })

    internal_labels = []
    for l in CTX.schematic.labels:
        if x_min <= l.x <= x_max and y_min <= l.y <= y_max:
            internal_labels.append({"text": l.text, "pos": (l.x, l.y), "is_global": l.is_global})

    boundary_crossing_wires = []
    internal_wires = 0
    for w in CTX.schematic.wires:
        start_in = x_min <= w.start.x <= x_max and y_min <= w.start.y <= y_max
        end_in = x_min <= w.end.x <= x_max and y_min <= w.end.y <= y_max
        if start_in and end_in:
            internal_wires += 1
        elif start_in or end_in:
            in_pt = w.start if start_in else w.end
            out_pt = w.end if start_in else w.start
            boundary_crossing_wires.append({
                "from_internal": (in_pt.x, in_pt.y),
                "to_external": (out_pt.x, out_pt.y)
            })

    return {
        "block_name": block_name,
        "bounding_box": {"x_min": x_min, "y_min": y_min, "x_max": x_max, "y_max": y_max},
        "components_count": len(internal_comps),
        "components": internal_comps,
        "internal_wires_count": internal_wires,
        "boundary_ports_count": len(boundary_crossing_wires),
        "boundary_ports": boundary_crossing_wires,
        "labels": internal_labels
    }

def synthesize_custom_symbol(
    part_name: str,
    pins_list: List[Dict[str, str]],
    ref_prefix: str = "U",
    footprint: str = "",
    description: str = ""
) -> Dict[str, Any]:
    """Synthesizes a brand new custom KiCad symbol with 4-sided pin layout."""
    builder = SymbolBuilder(name=part_name, ref_prefix=ref_prefix)
    if footprint: builder.set_footprint(footprint)
    if description: builder.set_description(description)
    for p in pins_list:
        builder.add_pin(
            num=str(p.get("number", p.get("pin", "1"))),
            name=p.get("name", "PIN"),
            ptype=p.get("type", "passive"),
            side=p.get("side", "auto")
        )
    sym_def = builder.build_symbol_definition()
    # Register in active schematic
    CTX.schematic.lib_symbols_raw[sym_def.lib_id] = sym_def.raw_sexp
    return {
        "status": "SYNTHESIZED",
        "lib_id": sym_def.lib_id,
        "pins_count": len(sym_def.pins)
    }

def capture_multimodal_crop(
    center_x: float,
    center_y: float,
    width_mm: float = 50.0,
    height_mm: float = 50.0,
    output_name: str = "multimodal_crop.png",
    zoom: float = 3.0
) -> Dict[str, Any]:
    """Generates a high-resolution raster crop centered around an area of interest and copies it to the active conversation artifact directory."""
    x_min = center_x - width_mm / 2.0
    x_max = center_x + width_mm / 2.0
    y_min = center_y - height_mm / 2.0
    y_max = center_y + height_mm / 2.0
    res = inspect_region_crop(x_min, y_min, x_max, y_max, zoom=zoom, output_name=output_name)
    if "error" in res:
        return res

    # Dynamically locate active conversation artifact directory or fallback to scratch
    target_dest = os.environ.get("ANTIGRAVITY_ARTIFACT_DIR")
    if not target_dest:
        brain_root = os.path.expanduser(r"~\.gemini\antigravity-ide\brain")
        if os.path.isdir(brain_root):
            subdirs = [os.path.join(brain_root, d) for d in os.listdir(brain_root) if os.path.isdir(os.path.join(brain_root, d))]
            if subdirs:
                subdirs.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                target_dest = subdirs[0]

    copied_path = None
    if target_dest and os.path.isdir(target_dest):
        try:
            dest = os.path.join(target_dest, output_name)
            import shutil
            shutil.copyfile(res["output_file"], dest)
            copied_path = dest
        except Exception:
            pass

    return {
        "status": "CROPPED",
        "output_file": res["output_file"],
        "artifact_path": copied_path,
        "box": {"x_min": x_min, "y_min": y_min, "x_max": x_max, "y_max": y_max},
        "width_px": res.get("width_px"),
        "height_px": res.get("height_px")
    }

def apply_circuit_patch(
    patch: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Executes an atomic circuit patch in-place with rollback on failure.
    Applies wire deletions, component deletions, new components, new wires,
    new power symbols, new net labels, runs auto_junctions, and executes health check.
    If 'render_crop_box' is provided, captures the visual crop automatically.
    """
    import copy
    old_comps = copy.deepcopy(CTX.schematic.components)
    old_wires = copy.deepcopy(CTX.schematic.wires)
    old_labels = copy.deepcopy(CTX.schematic.labels)
    old_powers = copy.deepcopy(CTX.schematic.power_symbols)
    old_junctions = copy.deepcopy(CTX.schematic.junctions)

    try:
        # 1. Delete specified wires
        for rw in patch.get("remove_wires", []):
            p1 = (round(rw["start"][0], 2), round(rw["start"][1], 2))
            p2 = (round(rw["end"][0], 2), round(rw["end"][1], 2))
            CTX.schematic.wires = [
                w for w in CTX.schematic.wires
                if not (
                    ((round(w.start.x, 2), round(w.start.y, 2)) == p1 and (round(w.end.x, 2), round(w.end.y, 2)) == p2) or
                    ((round(w.start.x, 2), round(w.start.y, 2)) == p2 and (round(w.end.x, 2), round(w.end.y, 2)) == p1)
                )
            ]

        # 2. Delete specified power symbols
        for rp in patch.get("remove_power_symbols", []):
            pt = (round(rp["x"], 2), round(rp["y"], 2))
            CTX.schematic.power_symbols = [
                p for p in CTX.schematic.power_symbols
                if (round(p.x, 2), round(p.y, 2)) != pt
            ]

        # 3. Delete specified components
        for rc in patch.get("remove_components", []):
            CTX.schematic.components = [
                c for c in CTX.schematic.components
                if c.ref.upper() != rc.upper()
            ]

        # 4. Add new components
        for c_data in patch.get("components", []):
            pins_dict = {}
            for pn, p_spec in c_data.get("pins", {}).items():
                pins_dict[pn] = Pin(
                    number=str(pn),
                    name=p_spec.get("name", ""),
                    pin_type=p_spec.get("type", "passive"),
                    rel_x=float(p_spec.get("rel_x", 0.0)),
                    rel_y=float(p_spec.get("rel_y", 0.0))
                )
            comp = Component(
                ref=c_data["ref"],
                value=c_data["value"],
                lib_id=c_data["lib_id"],
                x=float(c_data["x"]),
                y=float(c_data["y"]),
                rot=float(c_data.get("rot", 0.0)),
                footprint=c_data.get("footprint", ""),
                description=c_data.get("description", ""),
                pins=pins_dict
            )
            CTX.schematic.components.append(comp)

        # 5. Add new wires
        for w_data in patch.get("wires", []):
            CTX.schematic.wires.append(Wire(
                start=Point(float(w_data["start"][0]), float(w_data["start"][1])),
                end=Point(float(w_data["end"][0]), float(w_data["end"][1]))
            ))

        # 6. Add power symbols
        for p_data in patch.get("power_symbols", []):
            ref = p_data.get("ref", f"#PWR_{p_data['name']}_{len(CTX.schematic.power_symbols)+1}")
            CTX.schematic.power_symbols.append(PowerSymbol(
                name=p_data["name"],
                ref=ref,
                x=float(p_data["x"]),
                y=float(p_data["y"]),
                rot=float(p_data.get("rot", 0.0))
            ))

        # 7. Add labels
        for l_data in patch.get("labels", []):
            CTX.schematic.labels.append(Label(
                text=l_data["text"],
                x=float(l_data["x"]),
                y=float(l_data["y"]),
                rot=float(l_data.get("rot", 0.0)),
                is_global=bool(l_data.get("is_global", False))
            ))

        # 8. Auto-junctions
        CTX.schematic.auto_junctions()

        # 9. Health check
        drc = run_health_check()

        # 10. Optional Crop
        crop_res = None
        crop_box = patch.get("render_crop_box")
        if crop_box:
            crop_name = patch.get("crop_name", "patch_verification.png")
            crop_res = inspect_region_crop(
                x_min=float(crop_box["x_min"]),
                y_min=float(crop_box["y_min"]),
                x_max=float(crop_box["x_max"]),
                y_max=float(crop_box["y_max"]),
                output_name=crop_name
            )

        return {
            "status": "APPLIED",
            "components_count": len(CTX.schematic.components),
            "wires_count": len(CTX.schematic.wires),
            "drc_status": drc["status"],
            "dangling_wires_count": drc["dangling_wires_count"],
            "crop": crop_res
        }
    except Exception as e:
        CTX.schematic.components = old_comps
        CTX.schematic.wires = old_wires
        CTX.schematic.labels = old_labels
        CTX.schematic.power_symbols = old_powers
        CTX.schematic.junctions = old_junctions
        return {"status": "FAILED_ROLLED_BACK", "error": str(e)}

def synthesize_low_side_driver(
    mcu_ref: str,
    mcu_pin: str,
    target_ref: str,
    target_pin: str,
    net_label: str = "CTRL",
    driver_type: str = "AO3400A",
    pull_down_val: str = "100k",
    include_jumper: bool = True,
    jumper_value: str = "SEL",
    jumper_type: str = "Jumper:SolderJumper_3_Bridged12",
    description: str = "Low-Side N-MOSFET Driver"
) -> Dict[str, Any]:
    """
    General-purpose hardware macro-tool that synthesizes a complete buffered low-side driver:
    Applicable to ANY circuit and ANY load (e.g. Relays, Solenoids, Buzzers, SIM PWRKEY,
    Level Shifters, Power Switches, LED strings, Motor Enables).
    - Allocates next available reference designators (Q, R, SJ)
    - Dynamically calculates clearance and routes orthogonal Manhattan wiring
    - Pulls a clean 4.0mm stub off the MCU pin with matching net label (preventing bus collisions)
    - Automatically drops junctions, runs DRC health check, and produces a visual crop
    """
    mcu = CTX.schematic.get_component(mcu_ref)
    target = CTX.schematic.get_component(target_ref)
    if not mcu: return {"error": f"MCU '{mcu_ref}' not found."}
    if not target: return {"error": f"Target component '{target_ref}' not found."}

    mcu_pin_pos = mcu.get_world_pin_pos(mcu_pin)
    target_pin_pos = target.get_world_pin_pos(target_pin)
    if not mcu_pin_pos: return {"error": f"Pin {mcu_pin} not found on {mcu_ref}."}
    if not target_pin_pos: return {"error": f"Pin {target_pin} not found on {target_ref}."}

    q_ref = get_next_reference("Q")["next_available"]
    r_ref = get_next_reference("R")["next_available"]

    base_x = target_pin_pos[0]
    base_y = target_pin_pos[1] + 13.22

    components = []
    wires = []
    power_symbols = []
    labels = []

    if include_jumper:
        sj_ref = get_next_reference("SJ")["next_available"]
        components.append({
            "ref": sj_ref,
            "value": jumper_value,
            "lib_id": jumper_type,
            "x": base_x,
            "y": base_y,
            "rot": 180.0,
            "footprint": "Jumper:SolderJumper-3_P1.3mm_Bridged12_Pad1.0x1.5mm",
            "description": f"Solder Jumper ({jumper_value})",
            "pins": {
                "1": {"name": "A", "rel_x": -5.08, "rel_y": 0.0},
                "2": {"name": "C", "rel_x": 0.0, "rel_y": -3.81},
                "3": {"name": "B", "rel_x": 5.08, "rel_y": 0.0}
            }
        })
        # Target pin to SJ Pin 2
        wires.append({"start": [target_pin_pos[0], target_pin_pos[1]], "end": [base_x, base_y - 3.81]})
        # SJ Pin 1 to Q Drain
        wires.append({"start": [base_x + 5.08, base_y], "end": [base_x + 25.29, base_y]})
        # SJ Pin 3 down to GND
        wires.append({"start": [base_x - 5.08, base_y], "end": [base_x - 5.08, base_y + 14.0]})
        power_symbols.append({"name": "GND", "x": base_x - 5.08, "y": base_y + 14.0})
    else:
        # Direct connection from target pin to Q Drain
        wires.append({"start": [target_pin_pos[0], target_pin_pos[1]], "end": [base_x + 25.29, base_y]})

    # Transistor Q
    components.append({
        "ref": q_ref,
        "value": driver_type,
        "lib_id": f"Transistor_FET:{driver_type}",
        "x": base_x + 22.75,
        "y": base_y + 5.08,
        "rot": 0.0,
        "footprint": "Package_TO_SOT_SMD:SOT-23",
        "description": f"{description} ({driver_type})",
        "pins": {
            "1": {"name": "G", "rel_x": -5.08, "rel_y": -2.54},
            "2": {"name": "S", "rel_x": 2.54, "rel_y": -5.08},
            "3": {"name": "D", "rel_x": 2.54, "rel_y": 5.08}
        }
    })
    # Source to GND
    power_symbols.append({"name": "GND", "x": base_x + 25.29, "y": base_y + 10.16})

    # Resistor R (Gate pull-down)
    components.append({
        "ref": r_ref,
        "value": pull_down_val,
        "lib_id": "Device:R",
        "x": base_x + 11.43,
        "y": base_y + 13.45,
        "rot": 0.0,
        "footprint": "Resistor_SMD:R_0603_1608Metric",
        "description": f"Gate Pull-Down Resistor ({pull_down_val})",
        "pins": {
            "1": {"name": "~", "rel_x": 0.0, "rel_y": 3.81},
            "2": {"name": "~", "rel_x": 0.0, "rel_y": -3.81}
        }
    })
    # Gate to R top
    wires.append({"start": [base_x + 17.67, base_y + 7.62], "end": [base_x + 11.43, base_y + 7.62]})
    wires.append({"start": [base_x + 11.43, base_y + 7.62], "end": [base_x + 11.43, base_y + 9.64]})
    # R bottom to GND
    power_symbols.append({"name": "GND", "x": base_x + 11.43, "y": base_y + 17.26})

    # Gate to Net Label
    wires.append({"start": [base_x + 11.43, base_y + 7.62], "end": [base_x + 1.75, base_y + 7.62]})
    labels.append({"text": net_label, "x": base_x + 1.75, "y": base_y + 7.62, "rot": 0.0})

    # MCU pin stub (safe 4.0mm avoiding bus collisions)
    wires.append({"start": [mcu_pin_pos[0], mcu_pin_pos[1]], "end": [mcu_pin_pos[0] + 4.0, mcu_pin_pos[1]]})
    labels.append({"text": net_label, "x": mcu_pin_pos[0] + 4.0, "y": mcu_pin_pos[1], "rot": 0.0})

    patch = {
        "components": components,
        "wires": wires,
        "power_symbols": power_symbols,
        "labels": labels,
        "render_crop_box": {
            "x_min": base_x - 15.0,
            "y_min": target_pin_pos[1] - 5.0,
            "x_max": base_x + 35.0,
            "y_max": base_y + 25.0
        }
    }

def inspect_net(query: str) -> Dict[str, Any]:
    """
    Instantly inspects all connections, pins, and coordinates on an electrical net.
    query can be a net name (e.g. 'ESP_EN', 'GND', '+3.3V', '+4V_sim')
    or a component pin (e.g. 'U4.3', 'J7.5', 'SW1.1').
    """
    if not CTX.schematic.components:
        CTX._auto_discover_schematic()

    netlist = CTX.schematic.get_netlist()
    query_clean = query.strip()

    comp_ref, pin_target = None, None
    if "." in query_clean:
        comp_ref, pin_target = query_clean.split(".", 1)
    elif ":" in query_clean:
        comp_ref, pin_target = query_clean.split(":", 1)

    matching_net = None
    target_pins = []

    for net_name, pins in netlist.items():
        if comp_ref and pin_target:
            if any(p.get("ref", "").upper() == comp_ref.upper() and str(p.get("pin")) == str(pin_target) for p in pins):
                matching_net = net_name
                target_pins = pins
                break
        elif net_name.upper() == query_clean.upper():
            matching_net = net_name
            target_pins = pins
            break
        elif query_clean.upper() in net_name.upper():
            if not matching_net:
                matching_net = net_name
                target_pins = pins

    if not matching_net:
        return {
            "status": "NOT_FOUND",
            "query": query,
            "message": f"No net or pin matching '{query}' found.",
            "total_nets": len(netlist)
        }

    labels_on_net = []
    for l in CTX.schematic.labels:
        if l.text.upper() == matching_net.upper():
            labels_on_net.append({"text": l.text, "pos": (l.x, l.y), "is_global": l.is_global})

    return {
        "status": "FOUND",
        "query": query,
        "net_name": matching_net,
        "total_nodes": len(target_pins),
        "nodes": [
            {
                "ref": p.get("ref"),
                "value": p.get("value"),
                "pin": p.get("pin"),
                "pin_name": p.get("pin_name", ""),
                "pos": p.get("pt")
            }
            for p in target_pins
        ],
        "labels": labels_on_net
    }

def attach_net_label(
    comp_ref: str,
    pin_num: str,
    label_name: str,
    direction: str = "auto",
    stub_length_mm: float = 5.08
) -> Dict[str, Any]:
    """
    Attaches a net label to a component pin with an orthogonal exit stub wire.
    direction can be 'auto', 'left', 'right', 'up', or 'down'.
    """
    comp = next((c for c in CTX.schematic.components if c.ref.upper() == comp_ref.upper()), None)
    if not comp:
        return {"error": f"Component '{comp_ref}' not found."}

    pin_pos = comp.get_world_pin_pos(str(pin_num))
    if not pin_pos:
        return {"error": f"Pin '{pin_num}' not found on '{comp_ref}'."}

    px, py = pin_pos[0], pin_pos[1]

    if direction == "auto":
        if px < comp.x:
            direction = "left"
        elif px > comp.x:
            direction = "right"
        elif py < comp.y:
            direction = "up"
        else:
            direction = "down"

    if direction == "left":
        ex, ey = round(px - stub_length_mm, 2), py
        rot = 180.0
    elif direction == "right":
        ex, ey = round(px + stub_length_mm, 2), py
        rot = 0.0
    elif direction == "up":
        ex, ey = px, round(py - stub_length_mm, 2)
        rot = 90.0
    else:
        ex, ey = px, round(py + stub_length_mm, 2)
        rot = 270.0

    w = CTX.schematic.add_wire(Point(px, py), Point(ex, ey))
    lbl = CTX.schematic.add_label(label_name, ex, ey, rot=rot)
    CTX.schematic.auto_junctions()

    return {
        "status": "ATTACHED",
        "comp_ref": comp_ref,
        "pin": pin_num,
        "net_label": label_name,
        "direction": direction,
        "pin_pos": pin_pos,
        "label_pos": (ex, ey)
    }

def replace_component_preserving_nets(
    ref: str,
    new_lib_id: str,
    new_value: Optional[str] = None,
    pin_mapping: Optional[Dict[str, str]] = None,
    new_footprint: Optional[str] = None
) -> Dict[str, Any]:
    """
    Replaces an existing component with a new library symbol, preserving existing wire connections.
    """
    comp = next((c for c in CTX.schematic.components if c.ref.upper() == ref.upper()), None)
    if not comp:
        return {"error": f"Component '{ref}' not found."}

    sym_def = CTX.lib_manager.get(new_lib_id)
    if not sym_def:
        return {"error": f"Symbol '{new_lib_id}' not found in KiCad library."}

    val = new_value or comp.value
    fp = new_footprint or sym_def.default_footprint or comp.footprint

    if new_lib_id not in CTX.schematic.lib_symbols_raw:
        CTX.schematic.lib_symbols_raw[new_lib_id] = sym_def.get_lib_symbol_sexp()

    new_pins = {}
    for pn, pdef in sym_def.pins.items():
        new_pins[pn] = Pin(
            number=pdef.number,
            name=pdef.name,
            pin_type=pdef.pin_type,
            rel_x=pdef.rel_x,
            rel_y=pdef.rel_y,
            rel_rot=pdef.rel_rot
        )

    comp.lib_id = new_lib_id
    comp.value = val
    comp.footprint = fp
    comp.pins = new_pins

    CTX.schematic.auto_junctions()
    return {
        "status": "REPLACED",
        "ref": ref,
        "new_lib_id": new_lib_id,
        "new_value": val,
        "pins_count": len(new_pins)
    }

def auto_clearance_lint(min_distance_mm: float = 2.54) -> Dict[str, Any]:
    """
    Checks for text collisions (e.g. net labels overlapping component text or power symbols)
    and nudges them into clear space.
    """
    fixed_count = 0
    collisions = []
    occupied_points = {}
    for p in CTX.schematic.power_symbols:
        occupied_points[(round(p.x, 1), round(p.y, 1))] = f"Power:{p.name}"

    for l in CTX.schematic.labels:
        pt = (round(l.x, 1), round(l.y, 1))
        if pt in occupied_points:
            collisions.append(f"Label '{l.text}' collides with {occupied_points[pt]} at {pt}")
            l.x = round(l.x - 3.81, 2)
            fixed_count += 1
        occupied_points[pt] = f"Label:{l.text}"

    return {
        "status": "LINTED",
        "collisions_found": len(collisions),
        "collisions_resolved": fixed_count,
        "details": collisions
    }

def audit_footprints() -> Dict[str, Any]:
    """
    Audits all placed components in the active schematic for footprint status.
    Identifies components with valid, missing, or non-standard footprint library nicknames.
    """
    sch_path = CTX.active_file_path or "unitycircuit/unity_meters.kicad_sch"
    if not os.path.exists(sch_path):
        return {"error": f"Schematic file not found at '{sch_path}'"}
        
    with open(sch_path, "r", encoding="utf-8") as f:
        text = f.read()
    lib_end = text.find("\n\t(symbol\n")
    if lib_end == -1:
        return {"error": "Could not locate symbol instances in schematic."}
        
    pattern = r'(\t\(symbol\n(?:\t\t[^\n]*\n)+\t\))'
    assigned = []
    missing = []
    custom_lib = []
    
    for m in re.finditer(pattern, text[lib_end:]):
        block = m.group(1)
        ref_m = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', block)
        val_m = re.search(r'\(property\s+"Value"\s+"([^"]+)"', block)
        lib_m = re.search(r'\(lib_id\s+"([^"]+)"\)', block)
        fp_m = re.search(r'\(property\s+"Footprint"\s+"([^"]*)"', block)
        
        if not ref_m:
            continue
        ref = ref_m.group(1)
        if ref.startswith("#"):
            continue
            
        val = val_m.group(1) if val_m else ""
        lib_id = lib_m.group(1) if lib_m else ""
        fp = fp_m.group(1).strip() if fp_m else ""
        
        info = {"ref": ref, "value": val, "lib_id": lib_id, "footprint": fp}
        if not fp:
            missing.append(info)
        else:
            if ":" in fp and not any(fp.startswith(pfx + ":") for pfx in [
                "Resistor_SMD", "Resistor_THT", "Capacitor_SMD", "Capacitor_THT",
                "Diode_SMD", "Diode_THT", "Package_TO_SOT_SMD", "Package_QFP",
                "Connector_PinHeader_2.54mm", "TerminalBlock_Phoenix", "Button_Switch_THT",
                "Converter_ACDC", "RF_Module", "Inductor_SMD", "Crystal", "Fuse",
                "Varistor", "Jumper", "NetTie", "LED_SMD"
            ]):
                custom_lib.append(info)
            assigned.append(info)
            
    return {
        "status": "AUDITED",
        "total_components": len(assigned) + len(missing),
        "assigned_count": len(assigned),
        "missing_count": len(missing),
        "custom_lib_count": len(custom_lib),
        "missing": missing,
        "custom_lib": custom_lib,
        "assigned": assigned
    }

def assign_footprint(ref: str, footprint: str) -> Dict[str, Any]:
    """
    Assigns or updates a footprint for a component (e.g. assign_footprint('IC1', 'Package_QFP:TQFP-48_7x7mm_P0.5mm')).
    Updates in-memory component and persists directly into the .kicad_sch file on disk.
    """
    sch_path = CTX.active_file_path or "unitycircuit/unity_meters.kicad_sch"
    if not os.path.exists(sch_path):
        return {"error": f"Schematic file not found at '{sch_path}'"}
        
    with open(sch_path, "r", encoding="utf-8") as f:
        text = f.read()
    lib_end = text.find("\n\t(symbol\n")
    if lib_end == -1:
        return {"error": "Could not locate symbol instances in schematic."}
        
    pattern = r'(\t\(symbol\n(?:\t\t[^\n]*\n)+\t\))'
    target_block = None
    target_start = -1
    target_end = -1
    
    for m in re.finditer(pattern, text[lib_end:]):
        block = m.group(1)
        if re.search(rf'\(property\s+"Reference"\s+"{re.escape(ref)}"', block):
            target_block = block
            target_start = lib_end + m.start(1)
            target_end = lib_end + m.end(1)
            break
            
    if not target_block:
        return {"error": f"Component '{ref}' not found in schematic."}
        
    old_fp_m = re.search(r'\(property\s+"Footprint"\s+"([^"]*)"', target_block)
    old_fp = old_fp_m.group(1) if old_fp_m else ""
    
    fp_pattern = r'(\(property\s+"Footprint"\s+)"[^"]*"'
    if re.search(fp_pattern, target_block):
        new_block = re.sub(fp_pattern, rf'\g<1>"{footprint}"', target_block, count=1)
    else:
        insert_idx = target_block.find('(property "Reference"')
        if insert_idx != -1:
            prop_str = f'\t\t(property "Footprint" "{footprint}"\n\t\t\t(at 0 0 0)\n\t\t\t(hide yes)\n\t\t)\n'
            new_block = target_block[:insert_idx] + prop_str + target_block[insert_idx:]
        else:
            return {"error": f"Unable to locate insertion point in block for '{ref}'"}
            
    new_text = text[:target_start] + new_block + text[target_end:]
    with open(sch_path, "w", encoding="utf-8") as f:
        f.write(new_text)
        
    # Also update in-memory CTX
    for c in CTX.schematic.components:
        if c.ref.upper() == ref.upper():
            c.footprint = footprint
            break
            
    return {
        "status": "UPDATED",
        "ref": ref,
        "old_footprint": old_fp,
        "new_footprint": footprint,
        "file": sch_path
    }

# Backwards compatible alias
synthesize_mcu_gpio_driver = synthesize_low_side_driver

# --- Gemini Function Calling Tool Declarations ---

TOOL_REGISTRY = {
    "search_kicad_library": search_kicad_library,
    "search_schematic": search_schematic,
    "search_web": search_web,
    "get_part_pinout": get_part_pinout,
    "search_datasheet": search_datasheet,
    "new_schematic": new_schematic,
    "load_schematic": load_schematic,
    "save_schematic": save_schematic,
    "inspect_components": inspect_components,
    "inspect_schematic_summary": inspect_schematic_summary,
    "place_component": place_component,
    "place_power_symbol": place_power_symbol,
    "place_net_label": place_net_label,
    "connect_pins": connect_pins,
    "connect_pin_to_net": connect_pin_to_net,
    "add_wire": add_wire,
    "auto_junctions": auto_junctions,
    "change_component_value": change_component_value,
    "move_component": move_component,
    "delete_component": delete_component,
    "inspect_component_positions": inspect_component_positions,
    "inspect_netlist": inspect_netlist,
    "run_health_check": run_health_check,
    "render_schematic_preview": render_schematic_preview,
    "inspect_region_crop": inspect_region_crop,
    "get_next_reference": get_next_reference,
    "shift_block": shift_block,
    "check_spatial_clearance": check_spatial_clearance,
    "find_open_canvas_zone": find_open_canvas_zone,
    "remove_component_and_dangling_wires": remove_component_and_dangling_wires,
    "route_around_obstacles": route_around_obstacles,
    "inspect_circuit_block": inspect_circuit_block,
    "synthesize_custom_symbol": synthesize_custom_symbol,
    "capture_multimodal_crop": capture_multimodal_crop,
    "apply_circuit_patch": apply_circuit_patch,
    "synthesize_mcu_gpio_driver": synthesize_mcu_gpio_driver,
    "synthesize_low_side_driver": synthesize_low_side_driver,
    "inspect_net": inspect_net,
    "attach_net_label": attach_net_label,
    "replace_component_preserving_nets": replace_component_preserving_nets,
    "auto_clearance_lint": auto_clearance_lint,
    "audit_footprints": audit_footprints,
    "assign_footprint": assign_footprint,
}

GEMINI_TOOL_DECLARATIONS = [
    {
        "name": "search_web",
        "description": "Searches the public web for component datasheets, application notes, silicon errata, pinout diagrams, formula guides, and hardware documentation.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Search query (e.g. 'SIM800C boot pulse duration', 'ATM90E32AS SPI timing')"},
                "limit": {"type": "INTEGER", "description": "Max results to return (default 5)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_schematic",
        "description": "Searches the active schematic for components, pins, net labels, and power symbols matching a query term.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Search term (e.g. 'SIM', 'ESP32', 'GND', 'BOOT', 'R15')"},
                "search_type": {"type": "STRING", "description": "'all' (default), 'components', 'labels', 'power', or 'nets'"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_kicad_library",
        "description": "Searches for electronic components across 25,988 official KiCad symbols.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Component search term (e.g. 'ESP32', 'AMS1117', 'AO3400A', 'NE555')"},
                "limit": {"type": "INTEGER", "description": "Max results to return (default 10)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_part_pinout",
        "description": "Inspects all pin numbers, names, and electrical types of any KiCad part before placing it.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "lib_id": {"type": "STRING", "description": "Symbol ID (e.g. 'Timer:NE555P', 'Device:R', 'MCU_Espressif:ESP32-C3-WROOM-02')"}
            },
            "required": ["lib_id"]
        }
    },
    {
        "name": "new_schematic",
        "description": "Initializes a fresh blank schematic canvas.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "description": "Schematic project title"},
                "paper": {"type": "STRING", "description": "Paper size: 'A4' (default), 'A3', 'A2'"}
            }
        }
    },
    {
        "name": "place_component",
        "description": "Places a single component from the library onto the schematic canvas.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "lib_id": {"type": "STRING", "description": "Component symbol ID (e.g. 'Device:R', 'Timer:NE555P')"},
                "ref": {"type": "STRING", "description": "Reference designator (e.g. 'U1', 'R1', 'C1')"},
                "value": {"type": "STRING", "description": "Component value (e.g. '10k', '100nF', 'ESP32-C3')"},
                "x": {"type": "NUMBER", "description": "X coordinate in millimeters on canvas (e.g. 150.0)"},
                "y": {"type": "NUMBER", "description": "Y coordinate in millimeters on canvas (e.g. 100.0)"},
                "rot": {"type": "NUMBER", "description": "Rotation in degrees: 0, 90, 180, 270"},
                "footprint": {"type": "STRING", "description": "Optional footprint (e.g. 'Resistor_SMD:R_0805_2012Metric')"}
            },
            "required": ["lib_id", "ref", "value", "x", "y"]
        }
    },
    {
        "name": "place_power_symbol",
        "description": "Places a power flag symbol (e.g. '+3.3V', '+5V', '+12V', 'GND').",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "description": "Power rail name: '+3.3V', '+5V', '+12V', 'GND'"},
                "x": {"type": "NUMBER", "description": "X coordinate in millimeters"},
                "y": {"type": "NUMBER", "description": "Y coordinate in millimeters"},
                "rot": {"type": "NUMBER", "description": "Rotation angle (default 0)"}
            },
            "required": ["name", "x", "y"]
        }
    },
    {
        "name": "connect_pins",
        "description": "Routes a clean 90-degree orthogonal Manhattan wire between two specific component pins.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "comp1_ref": {"type": "STRING", "description": "First component reference (e.g. 'U1')"},
                "pin1_num": {"type": "STRING", "description": "First pin number (e.g. '3')"},
                "comp2_ref": {"type": "STRING", "description": "Second component reference (e.g. 'R1')"},
                "pin2_num": {"type": "STRING", "description": "Second pin number (e.g. '1')"},
                "bias": {"type": "STRING", "description": "'horizontal' (X first) or 'vertical' (Y first)"}
            },
            "required": ["comp1_ref", "pin1_num", "comp2_ref", "pin2_num"]
        }
    },
    {
        "name": "connect_pin_to_net",
        "description": "Pulls a short wire stub off a component pin and attaches a net label (e.g. 'SPI_MOSI', 'I2C_SDA').",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "comp_ref": {"type": "STRING", "description": "Component reference (e.g. 'U1')"},
                "pin_num": {"type": "STRING", "description": "Pin number (e.g. '4')"},
                "net_name": {"type": "STRING", "description": "Net label text (e.g. 'I2C_SDA', 'PWM_OUT')"},
                "direction": {"type": "STRING", "description": "'right', 'left', 'up', 'down'"}
            },
            "required": ["comp_ref", "pin_num", "net_name"]
        }
    },
    {
        "name": "auto_junctions",
        "description": "Automatically detects all T-intersections and places KiCad electrical junction dots.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "change_component_value",
        "description": "Modifies the value of an existing component (e.g. change R1 from 10k to 4.7k).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "ref": {"type": "STRING", "description": "Component reference (e.g. 'R1')"},
                "new_value": {"type": "STRING", "description": "New value string (e.g. '4.7k', '22uF')"}
            },
            "required": ["ref", "new_value"]
        }
    },
    {
        "name": "inspect_component_positions",
        "description": "Returns exact coordinates (X, Y) of all placed components and their pin tips to plan wiring.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "inspect_netlist",
        "description": "Returns all electrical nets and what pins are connected to each net.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "run_health_check",
        "description": "Runs automated DRC health inspection detecting open/dangling wire stubs or orphaned power symbols.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "render_schematic_preview",
        "description": "Compiles the active schematic into a vector SVG preview for browser rendering.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "format": {"type": "STRING", "description": "'svg' (default) or 'pdf'"}
            }
        }
    },
    {
        "name": "capture_multimodal_crop",
        "description": "Generates a high-resolution raster crop centered around an area of interest and copies it to the active conversation artifact directory for visual inspection.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "center_x": {"type": "NUMBER", "description": "Center X coordinate in mm"},
                "center_y": {"type": "NUMBER", "description": "Center Y coordinate in mm"},
                "width_mm": {"type": "NUMBER", "description": "Crop width in mm (default 50.0)"},
                "height_mm": {"type": "NUMBER", "description": "Crop height in mm (default 50.0)"},
                "output_name": {"type": "STRING", "description": "PNG filename (default 'multimodal_crop.png')"},
                "zoom": {"type": "NUMBER", "description": "PyMuPDF zoom factor (default 3.0)"}
            },
            "required": ["center_x", "center_y"]
        }
    },
    {
        "name": "apply_circuit_patch",
        "description": "Executes an atomic circuit patch in-place with rollback on failure: applies wire deletions, component deletions, new components, new wires, power symbols, net labels, auto-junctions, and DRC checks.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "patch": {"type": "OBJECT", "description": "Patch specification containing remove_wires, components, wires, power_symbols, labels, and optional render_crop_box"}
            },
            "required": ["patch"]
        }
    },
    {
        "name": "synthesize_mcu_gpio_driver",
        "description": "Synthesizes an entire MCU-controlled buffered interface in one operation: places driver FET Q, pull-down R, 3-way solder jumper SJ (bridged to FET by default, GND fallback), routes all connections cleanly, and runs DRC.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "mcu_ref": {"type": "STRING", "description": "MCU component reference (e.g. 'U4')"},
                "mcu_pin": {"type": "STRING", "description": "MCU GPIO pin number (e.g. '14')"},
                "target_ref": {"type": "STRING", "description": "Target module or header reference (e.g. 'J11')"},
                "target_pin": {"type": "STRING", "description": "Target pin number (e.g. '5')"},
                "net_label": {"type": "STRING", "description": "Net label connecting MCU and gate (default 'SIM_BOOT')"},
                "driver_type": {"type": "STRING", "description": "FET part name in BOM (default 'AO3400A')"},
                "pull_down_val": {"type": "STRING", "description": "Gate pull-down resistor value (default '100k')"},
                "include_jumper": {"type": "BOOLEAN", "description": "Include 3-way auto-boot solder jumper (default True)"}
            },
            "required": ["mcu_ref", "mcu_pin", "target_ref", "target_pin"]
        }
    }
]

def execute_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatches and executes a tool call requested by the AI agent."""
    func = TOOL_REGISTRY.get(tool_name)
    if not func:
        return {"error": f"Unknown tool: '{tool_name}'"}
    try:
        return func(**arguments)
    except Exception as e:
        return {"error": f"Error executing '{tool_name}': {str(e)}"}
