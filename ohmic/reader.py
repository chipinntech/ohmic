"""
Ohmic Schematic Reader.
Parses KiCad .kicad_sch files into structured Ohmic models.
"""

from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import re

from .sexp import parse_sexp, find_tag, find_all_tags
from .models import Point, Pin, Component, Wire, Label, Junction, PowerSymbol

class SchematicReader:
    def __init__(self, sch_content: str):
        self.raw_text = sch_content
        self.tree = parse_sexp(sch_content)
        if not self.tree or self.tree[0] != 'kicad_sch':
            raise ValueError("Input text is not a valid KiCad schematic (missing 'kicad_sch' root).")

        self.lib_pins: Dict[str, Dict[str, Pin]] = defaultdict(dict)
        self.lib_symbols_raw: Dict[str, str] = {}
        self.components: List[Component] = []
        self.power_symbols: List[PowerSymbol] = []
        self.wires: List[Wire] = []
        self.labels: List[Label] = []
        self.junctions: List[Junction] = []
        self.paper: str = "A4"
        self.uuid: str = ""

        self._parse()

    def _parse(self):
        # 1. Parse Root UUID & Paper Size
        uuid_node = find_tag(self.tree, 'uuid')
        if uuid_node and len(uuid_node) > 1:
            self.uuid = uuid_node[1]

        paper_node = find_tag(self.tree, 'paper')
        if paper_node and len(paper_node) > 1:
            self.paper = paper_node[1]

        # 2. Parse Library Symbols (lib_symbols)
        lib_syms_node = find_tag(self.tree, 'lib_symbols')
        if lib_syms_node:
            for sym in find_all_tags(lib_syms_node, 'symbol'):
                if len(sym) > 1:
                    lib_id = sym[1]
                    self._extract_lib_pins(lib_id, sym)
                    # Extract raw block from raw_text for lossless round-tripping
                    raw_block = self._extract_raw_symbol_block(lib_id)
                    if raw_block:
                        self.lib_symbols_raw[lib_id] = raw_block

        # 3. Parse Placed Elements
        for item in self.tree[1:]:
            if not isinstance(item, list) or not item:
                continue
            tag = item[0]

            if tag == 'symbol':
                self._parse_symbol_instance(item)
            elif tag == 'wire':
                self._parse_wire(item)
            elif tag in ('label', 'global_label'):
                self._parse_label(item, is_global=(tag == 'global_label'))
            elif tag == 'junction':
                self._parse_junction(item)

    def _extract_lib_pins(self, lib_id: str, node: list):
        if not isinstance(node, list):
            return
        if node and node[0] == 'pin':
            p_type = node[1] if len(node) > 1 else 'passive'
            at_node = find_tag(node, 'at')
            num_node = find_tag(node, 'number')
            name_node = find_tag(node, 'name')

            if num_node and len(num_node) > 1:
                pnum = num_node[1]
                pname = name_node[1] if name_node and len(name_node) > 1 else ''
                px, py, prot = 0.0, 0.0, 0.0
                if at_node and len(at_node) > 2:
                    px, py = float(at_node[1]), float(at_node[2])
                    if len(at_node) > 3:
                        prot = float(at_node[3])

                self.lib_pins[lib_id][pnum] = Pin(
                    number=pnum, name=pname, pin_type=p_type,
                    rel_x=px, rel_y=py, rel_rot=prot
                )
        else:
            for child in node:
                self._extract_lib_pins(lib_id, child)

    def _parse_symbol_instance(self, sym_node: list):
        lib_id_node = find_tag(sym_node, 'lib_id')
        at_node = find_tag(sym_node, 'at')
        uuid_node = find_tag(sym_node, 'uuid')

        lib_id = lib_id_node[1] if lib_id_node and len(lib_id_node) > 1 else ''
        sx, sy, srot = 0.0, 0.0, 0.0
        if at_node and len(at_node) > 2:
            sx, sy = float(at_node[1]), float(at_node[2])
            if len(at_node) > 3:
                srot = float(at_node[3])

        sym_uuid = uuid_node[1] if uuid_node and len(uuid_node) > 1 else ''

        props = {}
        for prop_node in find_all_tags(sym_node, 'property'):
            if len(prop_node) > 2:
                props[prop_node[1]] = prop_node[2]

        ref = props.get('Reference', '')
        val = props.get('Value', '')

        if ref.startswith('#PWR'):
            self.power_symbols.append(PowerSymbol(
                name=val, ref=ref, x=sx, y=sy, rot=srot, uuid=sym_uuid
            ))
        else:
            # Instantiate component with copy of library pin definitions
            comp_pins = {}
            source_pins = self.lib_pins.get(lib_id, {})
            if not source_pins:
                from .library import KiCadLibraryManager
                mgr = KiCadLibraryManager()
                sym_def = mgr.get(lib_id)
                if sym_def:
                    source_pins = sym_def.pins

            for pnum, pdef in source_pins.items():
                comp_pins[pnum] = Pin(
                    number=pdef.number, name=pdef.name, pin_type=pdef.pin_type,
                    rel_x=pdef.rel_x, rel_y=pdef.rel_y, rel_rot=pdef.rel_rot
                )

            self.components.append(Component(
                ref=ref, value=val, lib_id=lib_id,
                x=sx, y=sy, rot=srot,
                footprint=props.get('Footprint', ''),
                description=props.get('Description', ''),
                properties=props, pins=comp_pins, uuid=sym_uuid
            ))

    def _parse_wire(self, wire_node: list):
        pts_node = find_tag(wire_node, 'pts')
        uuid_node = find_tag(wire_node, 'uuid')
        wire_uuid = uuid_node[1] if uuid_node and len(uuid_node) > 1 else ''

        if pts_node:
            xy_nodes = find_all_tags(pts_node, 'xy')
            if len(xy_nodes) >= 2:
                p1 = Point(float(xy_nodes[0][1]), float(xy_nodes[0][2]))
                p2 = Point(float(xy_nodes[1][1]), float(xy_nodes[1][2]))
                self.wires.append(Wire(start=p1, end=p2, uuid=wire_uuid))

    def _parse_label(self, label_node: list, is_global: bool = False):
        if len(label_node) > 1:
            text = label_node[1]
            at_node = find_tag(label_node, 'at')
            uuid_node = find_tag(label_node, 'uuid')
            lx, ly, lrot = 0.0, 0.0, 0.0
            if at_node and len(at_node) > 2:
                lx, ly = float(at_node[1]), float(at_node[2])
                if len(at_node) > 3:
                    lrot = float(at_node[3])
            lbl_uuid = uuid_node[1] if uuid_node and len(uuid_node) > 1 else ''

            self.labels.append(Label(
                text=text, x=lx, y=ly, rot=lrot, is_global=is_global, uuid=lbl_uuid
            ))

    def _parse_junction(self, junc_node: list):
        at_node = find_tag(junc_node, 'at')
        uuid_node = find_tag(junc_node, 'uuid')
        if at_node and len(at_node) > 2:
            jx, jy = float(at_node[1]), float(at_node[2])
            j_uuid = uuid_node[1] if uuid_node and len(uuid_node) > 1 else ''
            self.junctions.append(Junction(x=jx, y=jy, uuid=j_uuid))

    def _extract_raw_symbol_block(self, lib_id: str) -> Optional[str]:
        """Extracts the exact balanced parentheses S-expression block of a symbol from raw text."""
        m = re.search(r'\(symbol\s+"' + re.escape(lib_id) + r'"', self.raw_text)
        if not m:
            return None
        start = m.start()
        depth = 0
        in_q = False
        esc = False
        for i in range(start, len(self.raw_text)):
            c = self.raw_text[i]
            if esc: esc = False; continue
            if c == '\\': esc = True; continue
            if c == '"': in_q = not in_q; continue
            if not in_q:
                if c == '(': depth += 1
                elif c == ')':
                    depth -= 1
                    if depth == 0:
                        return self.raw_text[start:i+1]
        return None
