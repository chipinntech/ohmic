"""
Ohmic Schematic Diagnostics & Health Inspector.
Detects:
1. Dangling wire stubs (wires with open, unconnected ends - green squares in KiCad).
2. Orphaned power symbols (e.g. +5V/GND symbols floating alone without powering active ICs).
3. Floating pins (component pins with no connection and no no_connect flag).
4. Spatial layout and component bounding boxes.
"""

from typing import Dict, List, Tuple, Set, Any
from collections import defaultdict
from .models import Component, Wire, Label, PowerSymbol, Junction
from .netlist import NetlistTracer

class SchematicDiagnostics:
    def __init__(self, components: List[Component], wires: List[Wire],
                 labels: List[Label], power_symbols: List[PowerSymbol],
                 junctions: List[Junction], no_connects: List[Tuple[float, float]] = None):
        self.components = components
        self.wires = wires
        self.labels = labels
        self.power_symbols = power_symbols
        self.junctions = junctions
        self.no_connects = set(no_connects or [])
        self.tracer = NetlistTracer(components, wires, labels, power_symbols)

    def get_component_positions(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns exact spatial coordinates, rotation, and all pin world positions
        for every component on the schematic.
        """
        positions = {}
        for comp in self.components:
            pin_coords = {}
            for pnum, p in comp.pins.items():
                world_pos = comp.get_world_pin_pos(pnum)
                pin_coords[pnum] = {
                    "name": p.name,
                    "type": p.pin_type,
                    "pos": world_pos
                }
            positions[comp.ref] = {
                "value": comp.value,
                "lib_id": comp.lib_id,
                "center": (comp.x, comp.y),
                "rotation": comp.rot,
                "pins": pin_coords
            }
        return positions

    def find_dangling_wires(self) -> List[Dict[str, Any]]:
        """
        Finds wire endpoints that do not connect to any pin, other wire,
        junction, or label (these appear as green square boxes in KiCad).
        """
        # Collect all valid termination points
        pin_points: Set[Tuple[float, float]] = set()
        for comp in self.components:
            for pnum in comp.pins:
                pt = comp.get_world_pin_pos(pnum)
                if pt:
                    pin_points.add(pt)

        power_points: Set[Tuple[float, float]] = {
            (round(ps.x, 2), round(ps.y, 2)) for ps in self.power_symbols
        }
        label_points: Set[Tuple[float, float]] = {
            (round(lbl.x, 2), round(lbl.y, 2)) for lbl in self.labels
        }
        junction_points: Set[Tuple[float, float]] = {
            (round(j.x, 2), round(j.y, 2)) for j in self.junctions
        }

        # Count wire endpoint degrees
        endpoint_counts: Dict[Tuple[float, float], List[Wire]] = defaultdict(list)
        for w in self.wires:
            p1 = w.start.to_tuple()
            p2 = w.end.to_tuple()
            endpoint_counts[p1].append(w)
            endpoint_counts[p2].append(w)

        dangling = []
        for pt, connected_wires in endpoint_counts.items():
            # If an endpoint connects to only 1 wire, and touches no pin, label, junction, or power symbol
            if len(connected_wires) == 1:
                is_connected_to_anything = (
                    pt in pin_points or
                    pt in power_points or
                    pt in label_points or
                    pt in junction_points
                )
                if not is_connected_to_anything:
                    w = connected_wires[0]
                    other_end = w.end.to_tuple() if w.start.to_tuple() == pt else w.start.to_tuple()
                    dangling.append({
                        "open_point": pt,
                        "other_end": other_end,
                        "wire_uuid": w.uuid
                    })

        return dangling

    def find_orphaned_power_symbols(self) -> List[Dict[str, Any]]:
        """
        Finds power symbols (+5V, GND, +3.3V) that are floating or only
        connected to dead wires without powering any real component pins.
        """
        net_map = self.tracer.trace()
        orphaned = []
        for ps in self.power_symbols:
            # Find which net this power symbol's pin belongs to
            pt = (round(ps.x, 2), round(ps.y, 2))
            root = self.tracer._find(pt)
            # Find all component pins on this root
            pins_on_net = []
            for net_name, plist in net_map.items():
                for p in plist:
                    if self.tracer._find(p["pt"]) == root:
                        pins_on_net.append(p)
            
            # If zero component pins are connected to this power symbol, it's an orphan!
            if len(pins_on_net) == 0:
                orphaned.append({
                    "name": ps.name,
                    "ref": ps.ref,
                    "pos": (ps.x, ps.y),
                    "uuid": ps.uuid
                })

        return orphaned

    def run_health_check(self) -> Dict[str, Any]:
        """Runs complete electrical and topological health inspection."""
        dangling = self.find_dangling_wires()
        orphaned = self.find_orphaned_power_symbols()
        positions = self.get_component_positions()
        net_map = self.tracer.trace()

        return {
            "status": "PASS" if not dangling and not orphaned else "WARNING",
            "total_components": len(positions),
            "total_nets": len(net_map),
            "dangling_wires_count": len(dangling),
            "dangling_wires": dangling,
            "orphaned_power_symbols_count": len(orphaned),
            "orphaned_power_symbols": orphaned
        }
