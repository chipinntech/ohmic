"""
Ohmic KiCad Symbol Library Engine.
Indexes, searches, and extracts symbol definitions, pins, and footprints
from KiCad's official local symbol libraries (.kicad_sym).
Supports KiCad symbol inheritance (extends).
"""

import os
import re
from typing import Dict, List, Optional, Tuple, Any
from .models import Pin
from .sexp import parse_sexp, find_tag, find_all_tags

DEFAULT_SYMBOL_DIRS = [
    r"C:\Program Files\KiCad\10.0\share\kicad\symbols",
    r"C:\Program Files\KiCad\9.0\share\kicad\symbols",
    r"C:\Program Files\KiCad\8.0\share\kicad\symbols",
    r"C:\Program Files\KiCad\7.0\share\kicad\symbols",
    r"C:\Program Files\KiCad\share\kicad\symbols",
    r"/usr/share/kicad/symbols",
]

class SymbolDefinition:
    def __init__(self, lib_name: str, sym_name: str, raw_sexp: str, pins: Dict[str, Pin],
                 ref_prefix: str = "U", default_value: str = "", default_footprint: str = "",
                 description: str = "", extends: Optional[str] = None):
        self.lib_name = lib_name
        self.sym_name = sym_name
        self.lib_id = f"{lib_name}:{sym_name}"
        self.raw_sexp = raw_sexp
        self.pins = pins
        self.ref_prefix = ref_prefix
        self.default_value = default_value or sym_name
        self.default_footprint = default_footprint
        self.description = description
        self.extends = extends

    def get_lib_symbol_sexp(self) -> str:
        """
        Returns the formatted KiCad S-expression for (lib_symbols ...)
        with the symbol renamed to "LibraryName:SymbolName".
        """
        renamed = re.sub(
            r'\(symbol\s+"' + re.escape(self.sym_name) + r'"',
            f'(symbol "{self.lib_id}"',
            self.raw_sexp,
            count=1
        )
        return renamed

import json

CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".symbol_index.json")

class KiCadLibraryManager:
    def __init__(self, symbol_dir: Optional[str] = None):
        self.symbol_dir = symbol_dir or self._find_symbol_dir()
        self._index: Dict[str, str] = {}  # "LibName:SymName" -> filepath
        self._cache: Dict[str, SymbolDefinition] = {}
        if self.symbol_dir and os.path.exists(self.symbol_dir):
            self._load_or_build_index()
        self._register_builtin_custom_symbols()

    def _register_builtin_custom_symbols(self):
        rz_pins = {
            "1": Pin(number="1", name="Bi", pin_type="input", rel_x=-10.16, rel_y=3.81),
            "2": Pin(number="2", name="Fi", pin_type="input", rel_x=-10.16, rel_y=1.27),
            "3": Pin(number="3", name="GND", pin_type="power_in", rel_x=-10.16, rel_y=-1.27),
            "4": Pin(number="4", name="VCC", pin_type="power_in", rel_x=-10.16, rel_y=-3.81),
            "5": Pin(number="5", name="Fo", pin_type="output", rel_x=10.16, rel_y=-3.81),
            "6": Pin(number="6", name="Fo", pin_type="output", rel_x=10.16, rel_y=-1.27),
            "7": Pin(number="7", name="Bo", pin_type="output", rel_x=10.16, rel_y=1.27),
            "8": Pin(number="8", name="Bo", pin_type="output", rel_x=10.16, rel_y=3.81),
        }
        rz_sexp = """(symbol "RZ7889"
\t\t\t(pin_names
\t\t\t\t(offset 1.016)
\t\t\t)
\t\t\t(exclude_from_sim no)
\t\t\t(in_bom yes)
\t\t\t(on_board yes)
\t\t\t(in_pos_files yes)
\t\t\t(duplicate_pin_numbers_are_jumpers no)
\t\t\t(property "Reference" "U"
\t\t\t\t(at 0 6.35 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Value" "RZ7889"
\t\t\t\t(at 0 -6.35 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Footprint" "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1 1)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(property "Description" "Bi-directional DC Motor & Relay H-Bridge Driver, 5A, SOP-8"
\t\t\t\t(at 0 0 0)
\t\t\t\t(show_name no)
\t\t\t\t(do_not_autoplace no)
\t\t\t\t(hide yes)
\t\t\t\t(effects
\t\t\t\t\t(font
\t\t\t\t\t\t(size 1 1)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "RZ7889_0_1"
\t\t\t\t(rectangle
\t\t\t\t\t(start -7.62 5.08)
\t\t\t\t\t(end 7.62 -5.08)
\t\t\t\t\t(stroke
\t\t\t\t\t\t(width 0.254)
\t\t\t\t\t\t(type default)
\t\t\t\t\t)
\t\t\t\t\t(fill
\t\t\t\t\t\t(type background)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t\t(symbol "RZ7889_1_1"
\t\t\t\t(pin input line
\t\t\t\t\t(at -10.16 3.81 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "Bi"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1 1)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "1"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1 1)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin input line
\t\t\t\t\t(at -10.16 1.27 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "Fi"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1 1)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "2"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1 1)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin power_in line
\t\t\t\t\t(at -10.16 -1.27 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "GND"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1 1)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "3"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1 1)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin power_in line
\t\t\t\t\t(at -10.16 -3.81 0)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "VCC"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1 1)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "4"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1 1)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin output line
\t\t\t\t\t(at 10.16 -3.81 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "Fo"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1 1)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "5"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1 1)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin output line
\t\t\t\t\t(at 10.16 -1.27 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "Fo"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1 1)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "6"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1 1)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin output line
\t\t\t\t\t(at 10.16 1.27 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "Bo"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1 1)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "7"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1 1)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t\t(pin output line
\t\t\t\t\t(at 10.16 3.81 180)
\t\t\t\t\t(length 2.54)
\t\t\t\t\t(name "Bo"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1 1)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t\t(number "8"
\t\t\t\t\t\t(effects
\t\t\t\t\t\t\t(font
\t\t\t\t\t\t\t\t(size 1 1)
\t\t\t\t\t\t\t)
\t\t\t\t\t\t)
\t\t\t\t\t)
\t\t\t\t)
\t\t\t)
\t\t)"""
        self._cache["Driver_Motor:RZ7889"] = SymbolDefinition(
            lib_name="Driver_Motor",
            sym_name="RZ7889",
            raw_sexp=rz_sexp,
            pins=rz_pins,
            ref_prefix="U",
            default_value="RZ7889",
            default_footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
            description="Bi-directional DC Motor & Relay H-Bridge Driver, 5A, SOP-8"
        )
        self._index["Driver_Motor:RZ7889"] = "custom:Driver_Motor:RZ7889"

    def _find_symbol_dir(self) -> Optional[str]:
        for p in DEFAULT_SYMBOL_DIRS:
            if os.path.exists(p):
                return p
        return None

    def _load_or_build_index(self):
        """Loads cached index if valid, or builds and saves index."""
        if os.path.exists(CACHE_PATH):
            try:
                with open(CACHE_PATH, "r", encoding="utf-8") as f:
                    self._index = json.load(f)
                if self._index:
                    return
            except Exception:
                pass

        self._build_index()
        try:
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(self._index, f)
        except Exception:
            pass

    def _build_index(self):
        """Fast index scan of available .kicad_sym libraries."""
        if not self.symbol_dir:
            return
        for fname in os.listdir(self.symbol_dir):
            if fname.endswith(".kicad_sym"):
                lib_name = fname[:-10]
                fpath = os.path.join(self.symbol_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    syms = re.findall(r'\(symbol\s+"([^":]+)"', content)
                    for s in syms:
                        if not s.endswith(('_0_0', '_0_1', '_1_1', '_1_0', '_2_1')):
                            lib_id = f"{lib_name}:{s}"
                            self._index[lib_id] = fpath
                except Exception:
                    continue

    def search(self, query: str, limit: int = 10) -> List[str]:
        """Searches indexed symbols matching query string (case-insensitive)."""
        q = query.lower()
        matches = [lib_id for lib_id in self._index if q in lib_id.lower()]
        return matches[:limit]

    def _extract_symbol_block(self, content: str, sym_name: str) -> Optional[str]:
        m = re.search(r'\(symbol\s+"' + re.escape(sym_name) + r'"', content)
        if not m:
            return None
        start = m.start()
        depth = 0
        in_q = False
        esc = False
        for i in range(start, len(content)):
            c = content[i]
            if esc: esc = False; continue
            if c == '\\': esc = True; continue
            if c == '"': in_q = not in_q; continue
            if not in_q:
                if c == '(': depth += 1
                elif c == ')':
                    depth -= 1
                    if depth == 0:
                        return content[start:i+1]
        return None

    def get(self, lib_id: str) -> Optional[SymbolDefinition]:
        """
        Retrieves, parses, and caches a complete SymbolDefinition by its 'LibName:SymName' ID.
        Resolves symbol inheritance (extends) automatically.
        """
        if lib_id in self._cache:
            return self._cache[lib_id]

        fpath = self._index.get(lib_id)
        if not fpath:
            matches = self.search(lib_id, limit=1)
            if matches:
                fpath = self._index[matches[0]]
                lib_id = matches[0]
            else:
                return None

        lib_name, sym_name = lib_id.split(":", 1)
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        sym_text = self._extract_symbol_block(content, sym_name)
        if not sym_text:
            return None

        sym_tree = parse_sexp(sym_text)

        # Check for extends
        extends_node = find_tag(sym_tree, 'extends')
        extends_name = extends_node[1] if extends_node and len(extends_node) > 1 else None

        ref_prefix = "U"
        def_val = sym_name
        def_fp = ""
        desc = ""
        for p in find_all_tags(sym_tree, 'property'):
            if len(p) > 2:
                pname, pval = p[1], p[2]
                if pname == 'Reference': ref_prefix = pval
                elif pname == 'Value': def_val = pval
                elif pname == 'Footprint': def_fp = pval
                elif pname == 'Description': desc = pval

        pins: Dict[str, Pin] = {}
        def extract_pins(node: Any):
            if not isinstance(node, list) or not node:
                return
            if node[0] == 'pin':
                ptype = node[1] if len(node) > 1 else 'passive'
                num_node = find_tag(node, 'number')
                name_node = find_tag(node, 'name')
                at_node = find_tag(node, 'at')
                if num_node and len(num_node) > 1:
                    pnum = num_node[1]
                    pname = name_node[1] if name_node and len(name_node) > 1 else ''
                    px, py, prot = 0.0, 0.0, 0.0
                    if at_node and len(at_node) > 2:
                        px, py = float(at_node[1]), float(at_node[2])
                        if len(at_node) > 3: prot = float(at_node[3])
                    pins[pnum] = Pin(
                        number=pnum, name=pname, pin_type=ptype,
                        rel_x=px, rel_y=py, rel_rot=prot
                    )
            else:
                for child in node:
                    extract_pins(child)

        extract_pins(sym_tree)

        # If symbol extends a parent symbol, inherit pins and flatten parent graphics into child
        flattened_raw = sym_text
        if extends_name:
            parent_id = f"{lib_name}:{extends_name}"
            parent_def = self.get(parent_id)
            if parent_def:
                if not pins:
                    pins = dict(parent_def.pins)
                if not ref_prefix or ref_prefix == "U":
                    ref_prefix = parent_def.ref_prefix
                if not desc:
                    desc = parent_def.description

                # Extract and merge parent's sub-symbols (rectangles, pins, graphics) into child
                sub_sym_matches = list(re.finditer(r'\(symbol\s+"' + re.escape(extends_name) + r'_([^\"]+)"', parent_def.raw_sexp))
                sub_syms = []
                for match in sub_sym_matches:
                    start = match.start()
                    depth = 0
                    in_q = False
                    esc = False
                    for i in range(start, len(parent_def.raw_sexp)):
                        c = parent_def.raw_sexp[i]
                        if esc: esc = False; continue
                        if c == '\\': esc = True; continue
                        if c == '"': in_q = not in_q; continue
                        if not in_q:
                            if c == '(': depth += 1
                            elif c == ')':
                                depth -= 1
                                if depth == 0:
                                    sub_syms.append(parent_def.raw_sexp[start:i+1])
                                    break

                if sub_syms:
                    # Strip (extends "...") from child symbol
                    child_clean = re.sub(r'\s*\(extends\s+"[^"]+"\)', '', sym_text)
                    renamed_subs = []
                    for s in sub_syms:
                        renamed = re.sub(
                            r'\(symbol\s+"' + re.escape(extends_name) + r'_',
                            f'(symbol "{sym_name}_',
                            s
                        )
                        renamed_subs.append(renamed)
                    last_paren = child_clean.rfind(')')
                    if last_paren != -1:
                        flattened_raw = child_clean[:last_paren] + "\n\t\t" + "\n\t\t".join(renamed_subs) + "\n\t)"

        sym_def = SymbolDefinition(
            lib_name=lib_name, sym_name=sym_name, raw_sexp=flattened_raw,
            pins=pins, ref_prefix=ref_prefix, default_value=def_val,
            default_footprint=def_fp, description=desc, extends=extends_name
        )
        self._cache[lib_id] = sym_def
        return sym_def
