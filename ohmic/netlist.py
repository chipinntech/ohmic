"""
Ohmic Electrical Netlist Engine.
Implements Disjoint-Set Union (DSU) to trace complete pin-to-pin electrical connectivity.
"""

from typing import Dict, List, Tuple, Set
from collections import defaultdict
from .models import Component, Wire, Label, PowerSymbol

class NetlistTracer:
    def __init__(self, components: List[Component], wires: List[Wire],
                 labels: List[Label], power_symbols: List[PowerSymbol]):
        self.components = components
        self.wires = wires
        self.labels = labels
        self.power_symbols = power_symbols
        self.parent: Dict[Tuple[float, float], Tuple[float, float]] = {}

    def _find(self, pt: Tuple[float, float]) -> Tuple[float, float]:
        if pt not in self.parent:
            self.parent[pt] = pt
        while self.parent[pt] != pt:
            self.parent[pt] = self.parent[self.parent[pt]]
            pt = self.parent[pt]
        return pt

    def _union(self, pt1: Tuple[float, float], pt2: Tuple[float, float]):
        r1, r2 = self._find(pt1), self._find(pt2)
        if r1 != r2:
            self.parent[r1] = r2

    def trace(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Traces and returns a dictionary of:
        {
          "Net_Name": [
             {"ref": "U1", "pin": "13", "name": "IO13", "pt": (x, y)}, ...
          ]
        }
        """
        # 1. Union wire endpoints
        for w in self.wires:
            self._union(w.start.to_tuple(), w.end.to_tuple())

        def _point_on_segment(pt: Tuple[float, float], p1: Tuple[float, float], p2: Tuple[float, float], eps: float = 0.05) -> bool:
            min_x, max_x = min(p1[0], p2[0]) - eps, max(p1[0], p2[0]) + eps
            min_y, max_y = min(p1[1], p2[1]) - eps, max(p1[1], p2[1]) + eps
            if not (min_x <= pt[0] <= max_x and min_y <= pt[1] <= max_y):
                return False
            cross = abs((pt[1] - p1[1]) * (p2[0] - p1[0]) - (pt[0] - p1[0]) * (p2[1] - p1[1]))
            return cross < eps

        # 1.5 Union any labels, power symbols, or pins that lie along wire segments
        for w in self.wires:
            p1, p2 = w.start.to_tuple(), w.end.to_tuple()
            for lbl in self.labels:
                lpt = (round(lbl.x, 2), round(lbl.y, 2))
                if _point_on_segment(lpt, p1, p2):
                    self._union(lpt, p1)
            for ps in self.power_symbols:
                ppt = (round(ps.x, 2), round(ps.y, 2))
                if _point_on_segment(ppt, p1, p2):
                    self._union(ppt, p1)
            for comp in self.components:
                for pnum in comp.pins:
                    wpt = comp.get_world_pin_pos(pnum)
                    if wpt and _point_on_segment(wpt, p1, p2):
                        self._union(wpt, p1)

        # 2. Union power symbols
        power_groups: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        for ps in self.power_symbols:
            root = self._find((round(ps.x, 2), round(ps.y, 2)))
            power_groups[ps.name].append(root)

        for p_name, roots in power_groups.items():
            if roots:
                r0 = roots[0]
                for r in roots[1:]:
                    self._union(r0, r)

        # 3. Union labels by name
        label_groups: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        for lbl in self.labels:
            root = self._find((round(lbl.x, 2), round(lbl.y, 2)))
            label_groups[lbl.text].append(root)

        for l_name, roots in label_groups.items():
            if roots:
                r0 = roots[0]
                for r in roots[1:]:
                    self._union(r0, r)

        # 4. Resolve canonical net names
        root_to_name: Dict[Tuple[float, float], str] = {}
        for p_name, roots in power_groups.items():
            root_to_name[self._find(roots[0])] = p_name
        for l_name, roots in label_groups.items():
            root_to_name[self._find(roots[0])] = l_name

        # 5. Map connected pins to nets
        net_pins: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        for comp in self.components:
            for pnum, pin in comp.pins.items():
                world_pt = comp.get_world_pin_pos(pnum)
                if world_pt:
                    root = self._find(world_pt)
                    net_name = root_to_name.get(root, f"Net_{root[0]}_{root[1]}")
                    net_pins[net_name].append({
                        "ref": comp.ref,
                        "value": comp.value,
                        "pin": pnum,
                        "pin_name": pin.name,
                        "pt": world_pt
                    })

        return dict(net_pins)
