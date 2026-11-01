"""
Ohmic Schematic Auto-Router.
Generates clean 90-degree Manhattan wire paths between pins and coordinates,
and automatically calculates electrical junctions.
"""

from typing import List, Tuple, Dict, Set, Optional
from collections import defaultdict
import uuid

from .models import Point, Wire, Junction

class Router:
    @staticmethod
    def route_manhattan(p1: Point, p2: Point, bias: str = "horizontal") -> List[Wire]:
        """
        Generates orthogonal 90-degree wires between two points.
        bias: "horizontal" (X-first then Y) or "vertical" (Y-first then X).
        """
        # Snap coordinates to 2 decimal places to avoid floating point drift
        x1, y1 = round(p1.x, 2), round(p1.y, 2)
        x2, y2 = round(p2.x, 2), round(p2.y, 2)

        if x1 == x2 and y1 == y2:
            return []

        # Straight line
        if x1 == x2 or y1 == y2:
            return [Wire(start=Point(x1, y1), end=Point(x2, y2))]

        # Manhattan 2-segment path
        if bias == "horizontal":
            corner = Point(x2, y1)
            return [
                Wire(start=Point(x1, y1), end=corner),
                Wire(start=corner, end=Point(x2, y2))
            ]
        else:
            corner = Point(x1, y2)
            return [
                Wire(start=Point(x1, y1), end=corner),
                Wire(start=corner, end=Point(x2, y2))
            ]

    @staticmethod
    def route_step(p1: Point, p2: Point, step_offset: float = 5.0, axis: str = "x") -> List[Wire]:
        """
        Generates a 3-segment Z-step path exiting p1 by step_offset before turning towards p2.
        """
        x1, y1 = round(p1.x, 2), round(p1.y, 2)
        x2, y2 = round(p2.x, 2), round(p2.y, 2)

        if axis == "x":
            mid_x = round(x1 + step_offset, 2)
            c1 = Point(mid_x, y1)
            c2 = Point(mid_x, y2)
            return [
                Wire(start=Point(x1, y1), end=c1),
                Wire(start=c1, end=c2),
                Wire(start=c2, end=Point(x2, y2))
            ]
        else:
            mid_y = round(y1 + step_offset, 2)
            c1 = Point(x1, mid_y)
            c2 = Point(x2, mid_y)
            return [
                Wire(start=Point(x1, y1), end=c1),
                Wire(start=c1, end=c2),
                Wire(start=c2, end=Point(x2, y2))
            ]

    @staticmethod
    def auto_detect_junctions(wires: List[Wire]) -> List[Junction]:
        """
        Detects all points requiring KiCad junctions:
        1. Where a wire endpoint terminates onto the interior body of another wire segment (T-junction).
        2. Where 3 or more wire endpoints meet at the exact same coordinate.
        """
        junction_coords: Set[Tuple[float, float]] = set()
        endpoint_counts: Dict[Tuple[float, float], int] = defaultdict(int)

        # Collect all endpoints
        for w in wires:
            p1 = (round(w.start.x, 2), round(w.start.y, 2))
            p2 = (round(w.end.x, 2), round(w.end.y, 2))
            endpoint_counts[p1] += 1
            endpoint_counts[p2] += 1

        # 1. Condition: 3+ wire endpoints meeting at the same coordinate
        for pt, count in endpoint_counts.items():
            if count >= 3:
                junction_coords.add(pt)

        # 2. Condition: Wire endpoint touches interior of another wire
        for pt in endpoint_counts.keys():
            px, py = pt
            for w in wires:
                x1, y1 = round(w.start.x, 2), round(w.start.y, 2)
                x2, y2 = round(w.end.x, 2), round(w.end.y, 2)

                # Ignore if pt is one of w's own endpoints
                if pt == (x1, y1) or pt == (x2, y2):
                    continue

                # Check horizontal segment
                if y1 == y2 and abs(py - y1) < 0.01:
                    min_x, max_x = min(x1, x2), max(x1, x2)
                    if min_x < px < max_x:
                        junction_coords.add(pt)
                        break

                # Check vertical segment
                elif x1 == x2 and abs(px - x1) < 0.01:
                    min_y, max_y = min(y1, y2), max(y1, y2)
                    if min_y < py < max_y:
                        junction_coords.add(pt)
                        break

        return [Junction(x=pt[0], y=pt[1], diameter=0.0) for pt in sorted(junction_coords)]
