"""
Ohmic Core Schematic Engine.
High-level user-facing API for programmatic KiCad schematic design.
"""

from typing import Dict, List, Optional, Tuple, Any
import os
import uuid

from .models import Point, Pin, Component, Wire, Label, Junction, PowerSymbol
from .reader import SchematicReader
from .netlist import NetlistTracer
from .exporter import KiCadCliExporter
from .diagnostics import SchematicDiagnostics
from .library import KiCadLibraryManager, SymbolDefinition
from .writer import SchematicWriter
from .router import Router

class OhmicSchematic:
    def __init__(self, name: str = "OhmicProject", paper: str = "A3"):
        self.name = name
        self.paper = paper
        self.uuid: str = str(uuid.uuid4())
        self.components: List[Component] = []
        self.wires: List[Wire] = []
        self.labels: List[Label] = []
        self.power_symbols: List[PowerSymbol] = []
        self.junctions: List[Junction] = []
        self.lib_symbols_raw: Dict[str, str] = {}
        self.raw_text: str = ""
        self._reader: Optional[SchematicReader] = None
        self._lib_manager: Optional[KiCadLibraryManager] = None

    @property
    def lib_manager(self) -> KiCadLibraryManager:
        if self._lib_manager is None:
            self._lib_manager = KiCadLibraryManager()
        return self._lib_manager

    @classmethod
    def load(cls, file_path: str) -> 'OhmicSchematic':
        """Loads an existing .kicad_sch file into the Ohmic engine."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        sch = cls(name=os.path.splitext(os.path.basename(file_path))[0])
        sch.raw_text = content
        sch._reader = SchematicReader(content)
        sch.uuid = sch._reader.uuid or sch.uuid
        sch.paper = sch._reader.paper
        sch.components = sch._reader.components
        sch.wires = sch._reader.wires
        sch.labels = sch._reader.labels
        sch.power_symbols = sch._reader.power_symbols
        sch.junctions = sch._reader.junctions
        sch.lib_symbols_raw = sch._reader.lib_symbols_raw
        return sch

    # --- Schematic Construction Methods ---

    def add_component(
        self,
        lib_id: str,
        ref: str,
        value: str,
        x: float,
        y: float,
        rot: float = 0.0,
        footprint: str = "",
        description: str = ""
    ) -> Component:
        """
        Adds a component to the schematic, automatically resolving its pins from the symbol library.
        """
        sym_def = self.lib_manager.get(lib_id)
        pins: Dict[str, Pin] = {}
        if sym_def:
            for pnum, pdef in sym_def.pins.items():
                pins[pnum] = Pin(
                    number=pdef.number,
                    name=pdef.name,
                    pin_type=pdef.pin_type,
                    rel_x=pdef.rel_x,
                    rel_y=pdef.rel_y,
                    rel_rot=pdef.rel_rot
                )
            if not footprint and sym_def.default_footprint:
                footprint = sym_def.default_footprint
            if not description and sym_def.description:
                description = sym_def.description

        comp = Component(
            ref=ref,
            value=value,
            lib_id=lib_id,
            x=x,
            y=y,
            rot=rot,
            footprint=footprint,
            description=description,
            pins=pins
        )
        self.components.append(comp)
        return comp

    def add_power_symbol(
        self,
        name: str,
        x: float,
        y: float,
        rot: float = 0.0,
        ref: Optional[str] = None
    ) -> PowerSymbol:
        """Adds a power symbol (e.g. '+3.3V', '+5V', 'GND') to the schematic."""
        if not ref:
            pwr_idx = len(self.power_symbols) + 1
            clean_name = name.replace("+", "").replace(".", "_")
            ref = f"#PWR_{clean_name}_{pwr_idx}"

        pwr = PowerSymbol(name=name, ref=ref, x=x, y=y, rot=rot)
        self.power_symbols.append(pwr)
        return pwr

    def add_wire(self, p1: Point, p2: Point) -> Wire:
        """Adds a direct wire between two coordinates."""
        wire = Wire(start=p1, end=p2)
        self.wires.append(wire)
        return wire

    def add_label(self, text: str, x: float, y: float, rot: float = 0.0, is_global: bool = False) -> Label:
        """Adds a net label or global label."""
        lbl = Label(text=text, x=x, y=y, rot=rot, is_global=is_global)
        self.labels.append(lbl)
        return lbl

    def add_junction(self, x: float, y: float) -> Junction:
        """Adds an explicit junction dot."""
        junc = Junction(x=x, y=y)
        self.junctions.append(junc)
        return junc

    def get_component(self, ref: str) -> Optional[Component]:
        """Finds a placed component by reference designator (e.g. 'R1', 'U1')."""
        for c in self.components:
            if c.ref.upper() == ref.upper():
                return c
        return None

    # --- Routing & Connection Methods ---

    def connect_points(self, p1: Point, p2: Point, bias: str = "horizontal") -> List[Wire]:
        """Connects two arbitrary points with orthogonal Manhattan wires."""
        new_wires = Router.route_manhattan(p1, p2, bias=bias)
        self.wires.extend(new_wires)
        return new_wires

    def connect_pins(
        self,
        comp1_ref: str,
        pin1_num: str,
        comp2_ref: str,
        pin2_num: str,
        bias: str = "horizontal"
    ) -> List[Wire]:
        """
        Connects two component pins with orthogonal Manhattan wires.
        Calculates exact world pin coordinates considering rotation and symbol offsets.
        """
        c1 = self.get_component(comp1_ref)
        if not c1:
            raise ValueError(f"Component '{comp1_ref}' not found in schematic.")
        c2 = self.get_component(comp2_ref)
        if not c2:
            raise ValueError(f"Component '{comp2_ref}' not found in schematic.")

        pos1 = c1.get_world_pin_pos(str(pin1_num))
        if not pos1:
            raise ValueError(f"Pin '{pin1_num}' not found on component '{comp1_ref}'.")
        pos2 = c2.get_world_pin_pos(str(pin2_num))
        if not pos2:
            raise ValueError(f"Pin '{pin2_num}' not found on component '{comp2_ref}'.")

        p1 = Point(pos1[0], pos1[1])
        p2 = Point(pos2[0], pos2[1])
        return self.connect_points(p1, p2, bias=bias)

    def connect_pin_to_net(
        self,
        comp_ref: str,
        pin_num: str,
        net_name: str,
        stub_length: float = 5.08,
        direction: str = "right",
        is_global: bool = False
    ) -> Tuple[Wire, Label]:
        """
        Adds an exit wire stub from a pin and attaches a net label.
        direction: 'left', 'right', 'up', 'down'.
        """
        comp = self.get_component(comp_ref)
        if not comp:
            raise ValueError(f"Component '{comp_ref}' not found.")
        pos = comp.get_world_pin_pos(str(pin_num))
        if not pos:
            raise ValueError(f"Pin '{pin_num}' not found on '{comp_ref}'.")

        p_start = Point(pos[0], pos[1])
        if direction == "right":
            p_end = Point(round(pos[0] + stub_length, 2), pos[1])
            lbl_rot = 0.0
        elif direction == "left":
            p_end = Point(round(pos[0] - stub_length, 2), pos[1])
            lbl_rot = 0.0
        elif direction == "down":
            p_end = Point(pos[0], round(pos[1] + stub_length, 2))
            lbl_rot = 270.0
        else: # "up"
            p_end = Point(pos[0], round(pos[1] - stub_length, 2))
            lbl_rot = 90.0

        wire = self.add_wire(p_start, p_end)
        label = self.add_label(net_name, p_end.x, p_end.y, rot=lbl_rot, is_global=is_global)
        return wire, label

    def auto_junctions(self) -> List[Junction]:
        """Calculates and updates junctions across all wires in the schematic."""
        detected = Router.auto_detect_junctions(self.wires)
        self.junctions = detected
        return detected

    # --- Serialization, Export & Diagnostics ---

    def serialize(self) -> str:
        """Serializes schematic to KiCad S-expression string."""
        writer = SchematicWriter(self, self.lib_manager)
        return writer.serialize()

    def save(self, file_path: str):
        """Saves schematic to a .kicad_sch file."""
        writer = SchematicWriter(self, self.lib_manager)
        writer.write_to_file(file_path)

    def get_netlist(self) -> Dict[str, List[Dict[str, str]]]:
        """Traces and returns complete electrical netlist connectivity."""
        tracer = NetlistTracer(self.components, self.wires, self.labels, self.power_symbols)
        return tracer.trace()

    def get_diagnostics(self) -> SchematicDiagnostics:
        """Returns the diagnostic health inspector."""
        return SchematicDiagnostics(
            self.components, self.wires, self.labels,
            self.power_symbols, self.junctions
        )

    def run_health_check(self) -> Dict[str, Any]:
        """Runs automated health check for dangling wires, orphaned power, and shorts."""
        return self.get_diagnostics().run_health_check()

    def get_component_positions(self) -> Dict[str, Any]:
        """Returns exact millimeter coordinates of all components and their pins."""
        return self.get_diagnostics().get_component_positions()

    def get_summary(self) -> Dict[str, int]:
        """Returns a compact summary count of schematic elements."""
        return {
            "components": len(self.components),
            "wires": len(self.wires),
            "labels": len(self.labels),
            "power_symbols": len(self.power_symbols),
            "junctions": len(self.junctions),
            "distinct_nets": len(self.get_netlist())
        }

    def export_pdf(self, output_path: str) -> bool:
        """Exports the schematic to PDF using headless kicad-cli."""
        exporter = KiCadCliExporter()
        temp_sch = output_path + ".temp.kicad_sch"
        self.save(temp_sch)
        success = exporter.export_pdf(temp_sch, output_path)
        if os.path.exists(temp_sch):
            os.remove(temp_sch)
        return success
