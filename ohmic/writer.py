"""
Ohmic Schematic Writer & Serializer.
Transforms structured OhmicSchematic objects into valid, parseable KiCad (.kicad_sch) files.
Automatically resolves missing library symbols from KiCadLibraryManager.
"""

import os
import uuid
from typing import Dict, List, Optional, Set, Any
from .models import Point, Pin, Component, Wire, Label, Junction, PowerSymbol
from .library import KiCadLibraryManager, SymbolDefinition

class SchematicWriter:
    def __init__(self, schematic: Any, lib_manager: Optional[KiCadLibraryManager] = None):
        self.sch = schematic
        self.lib_manager = lib_manager or KiCadLibraryManager()
        self.root_uuid = getattr(schematic, 'uuid', str(uuid.uuid4()))
        if not self.root_uuid:
            self.root_uuid = str(uuid.uuid4())

    def serialize(self) -> str:
        """Serializes the entire OhmicSchematic into KiCad S-expression text."""
        lines: List[str] = []

        # 1. Header
        lines.append("(kicad_sch")
        lines.append("\t(version 20260306)")
        lines.append('\t(generator "ohmic_engine")')
        lines.append('\t(generator_version "1.0")')
        lines.append(f'\t(uuid "{self.root_uuid}")')
        lines.append(f'\t(paper "{self.sch.paper}")')

        # 2. Library Symbols (lib_symbols)
        lib_syms_block = self._generate_lib_symbols()
        lines.append(lib_syms_block)

        # 3. Sheet Instances
        lines.append("\t(sheet_instances")
        lines.append('\t\t(path "/"')
        lines.append('\t\t\t(page "1")')
        lines.append("\t\t)")
        lines.append("\t)")
        lines.append("\t(embedded_fonts no)")
        lines.append("")

        # 4. Junctions
        for j in self.sch.junctions:
            lines.append(f'\t(junction (at {j.x:.2f} {j.y:.2f}) (diameter {j.diameter}) (color 0 0 0 0) (uuid "{j.uuid}"))')

        if self.sch.junctions:
            lines.append("")

        # 5. Wires
        for w in self.sch.wires:
            lines.append(
                f'\t(wire (pts (xy {w.start.x:.2f} {w.start.y:.2f}) (xy {w.end.x:.2f} {w.end.y:.2f})) '
                f'(stroke (width 0) (type default)) (uuid "{w.uuid}"))'
            )

        if self.sch.wires:
            lines.append("")

        # 6. Labels
        for lbl in self.sch.labels:
            if lbl.is_global:
                lines.append(
                    f'\t(global_label "{lbl.text}" (shape input) (at {lbl.x:.2f} {lbl.y:.2f} {int(lbl.rot)}) '
                    f'(fields_autoplaced yes) (effects (font (size 1.27 1.27))) (uuid "{lbl.uuid}"))'
                )
            else:
                lines.append(
                    f'\t(label "{lbl.text}" (at {lbl.x:.2f} {lbl.y:.2f} {int(lbl.rot)}) '
                    f'(fields_autoplaced yes) (effects (font (size 1.0 1.0))) (uuid "{lbl.uuid}"))'
                )

        if self.sch.labels:
            lines.append("")

        # 7. Power Symbols
        for pwr in self.sch.power_symbols:
            pwr_block = self._format_power_symbol(pwr)
            lines.append(pwr_block)

        # 8. Components (Placed Symbols)
        for comp in self.sch.components:
            comp_block = self._format_component(comp)
            lines.append(comp_block)

        # 9. Closing Parenthesis
        lines.append(")")
        lines.append("")

        return "\n".join(lines)

    def write_to_file(self, file_path: str):
        """Serializes and writes schematic directly to disk."""
        content = self.serialize()
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _generate_lib_symbols(self) -> str:
        """Collects and serializes all required symbol definitions into (lib_symbols ...)."""
        needed_lib_ids: Set[str] = set()

        for comp in self.sch.components:
            if comp.lib_id:
                needed_lib_ids.add(comp.lib_id)

        for pwr in self.sch.power_symbols:
            lib_id = pwr.name if ":" in pwr.name else f"power:{pwr.name}"
            needed_lib_ids.add(lib_id)

        existing_raw = getattr(self.sch, "lib_symbols_raw", {})

        sym_blocks: List[str] = []
        for lib_id in sorted(needed_lib_ids):
            if lib_id in existing_raw:
                sym_blocks.append(existing_raw[lib_id])
                continue

            sym_def = self.lib_manager.get(lib_id)
            if sym_def:
                sym_blocks.append(sym_def.get_lib_symbol_sexp())
            else:
                # Minimal fallback symbol if library lookup is missing
                sym_blocks.append(self._generate_fallback_symbol(lib_id))

        out = ["\t(lib_symbols"]
        for block in sym_blocks:
            # Indent symbol block lines under lib_symbols
            for bline in block.strip().splitlines():
                out.append(f"\t\t{bline}")
        out.append("\t)")
        return "\n".join(out)

    def _format_component(self, comp: Component) -> str:
        """Formats a placed Component instance into KiCad S-expression."""
        out: List[str] = []
        out.append(
            f'\t(symbol (lib_id "{comp.lib_id}") (at {comp.x:.2f} {comp.y:.2f} {int(comp.rot)}) '
            f'(unit 1) (in_bom yes) (on_board yes) (fields_autoplaced yes) (uuid "{comp.uuid}")'
        )

        # Reference & Value properties with autoplace support
        ref_y = comp.y - 10.0 if comp.rot == 0 else comp.y - 4.0
        val_y = comp.y + 10.0 if comp.rot == 0 else comp.y + 4.0

        out.append(
            f'\t\t(property "Reference" "{comp.ref}" (at {comp.x:.2f} {ref_y:.2f} 0) '
            f'(effects (font (size 1.0 1.0))))'
        )

        out.append(
            f'\t\t(property "Value" "{comp.value}" (at {comp.x:.2f} {val_y:.2f} 0) '
            f'(effects (font (size 1.0 1.0))))'
        )

        # Footprint property
        out.append(
            f'\t\t(property "Footprint" "{comp.footprint}" (at {comp.x:.2f} {comp.y:.2f} 0) '
            f'(hide yes) (effects (font (size 1.0 1.0))))'
        )

        # Optional Description / Datasheet
        ds = comp.properties.get("Datasheet", "")
        if ds:
            out.append(
                f'\t\t(property "Datasheet" "{ds}" (at {comp.x:.2f} {comp.y:.2f} 0) '
                f'(hide yes) (effects (font (size 1.0 1.0))))'
            )
        desc = comp.description or comp.properties.get("Description", "")
        if desc:
            out.append(
                f'\t\t(property "Description" "{desc}" (at {comp.x:.2f} {comp.y:.2f} 0) '
                f'(hide yes) (effects (font (size 1.0 1.0))))'
            )

        # Pins
        if comp.pins:
            pin_lines = [f'(pin "{pnum}" (uuid "{pin.uuid}"))' for pnum, pin in sorted(comp.pins.items())]
            out.append("\t\t" + " ".join(pin_lines))

        # Instances
        out.append(
            f'\t\t(instances (project "{self.sch.name}" (path "/{self.root_uuid}" (reference "{comp.ref}") (unit 1))))'
        )
        out.append("\t)")
        return "\n".join(out)

    def _format_power_symbol(self, pwr: PowerSymbol) -> str:
        """Formats a placed PowerSymbol instance into KiCad S-expression."""
        lib_id = pwr.name if ":" in pwr.name else f"power:{pwr.name}"
        out: List[str] = []
        out.append(
            f'\t(symbol (lib_id "{lib_id}") (at {pwr.x:.2f} {pwr.y:.2f} {int(pwr.rot)}) '
            f'(unit 1) (in_bom yes) (on_board yes) (uuid "{pwr.uuid}")'
        )
        out.append(
            f'\t\t(property "Reference" "{pwr.ref}" (at {pwr.x:.2f} {pwr.y - 3.0:.2f} 0) '
            f'(hide yes) (effects (font (size 1.0 1.0))))'
        )
        out.append(
            f'\t\t(property "Value" "{pwr.name}" (at {pwr.x:.2f} {pwr.y + 3.0:.2f} 0) '
            f'(effects (font (size 1.0 1.0))))'
        )
        out.append(f'\t\t(pin "1" (uuid "{pwr.uuid}"))')
        out.append(
            f'\t\t(instances (project "{self.sch.name}" (path "/{self.root_uuid}" (reference "{pwr.ref}") (unit 1))))'
        )
        out.append("\t)")
        return "\n".join(out)

    def _generate_fallback_symbol(self, lib_id: str) -> str:
        """Generates a minimal valid KiCad lib_symbol when symbol definition is not found."""
        return (
            f'(symbol "{lib_id}"\n'
            f'\t(in_bom yes) (on_board yes)\n'
            f'\t(property "Reference" "U" (at 0 0 0) (effects (font (size 1.27 1.27))))\n'
            f'\t(property "Value" "{lib_id}" (at 0 2.54 0) (effects (font (size 1.27 1.27))))\n'
            f')'
        )
