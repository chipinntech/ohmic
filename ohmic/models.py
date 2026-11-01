"""
Ohmic Schematic Data Models.
Defines clean, typed data structures for electronic schematic entities.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import math
import uuid

@dataclass
class Point:
    x: float
    y: float

    def to_tuple(self) -> Tuple[float, float]:
        return (round(self.x, 2), round(self.y, 2))

@dataclass
class Pin:
    number: str
    name: str
    pin_type: str = "passive"
    rel_x: float = 0.0
    rel_y: float = 0.0
    rel_rot: float = 0.0
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class Component:
    ref: str
    value: str
    lib_id: str
    x: float
    y: float
    rot: float = 0.0
    footprint: str = ""
    description: str = ""
    properties: Dict[str, str] = field(default_factory=dict)
    pins: Dict[str, Pin] = field(default_factory=dict)
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))

    def get_world_pin_pos(self, pin_num: str) -> Optional[Tuple[float, float]]:
        """Calculates absolute (X, Y) coordinate of a pin in KiCad schematic space."""
        if pin_num not in self.pins:
            return None
        p = self.pins[pin_num]
        rad = math.radians(self.rot)
        cos_a = round(math.cos(rad))
        sin_a = round(math.sin(rad))
        rx = p.rel_x * cos_a - p.rel_y * sin_a
        ry = p.rel_x * sin_a + p.rel_y * cos_a
        return (round(self.x + rx, 2), round(self.y - ry, 2))

@dataclass
class Wire:
    start: Point
    end: Point
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class Label:
    text: str
    x: float
    y: float
    rot: float = 0.0
    is_global: bool = False
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class Junction:
    x: float
    y: float
    diameter: float = 0.0
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class PowerSymbol:
    name: str  # e.g. "+3.3V", "+5V", "GND"
    ref: str   # e.g. "#PWR01"
    x: float
    y: float
    rot: float = 0.0
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
