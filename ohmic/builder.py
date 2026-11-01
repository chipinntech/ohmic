"""
Ohmic Custom Symbol Builder.
Allows programmatic, declarative creation of standard-compliant KiCad symbols (.kicad_sym).
Supports automatic 4-sided pin distribution (Power Top/Bottom, Inputs Left, Outputs Right)
or direct synthesis from datasheet pin tables.
"""

import os
import re
from typing import Dict, List, Optional, Tuple, Any

from .models import Pin
from .library import SymbolDefinition
from .datasheet import DatasheetExtractor

POWER_TOP_NAMES = {"VCC", "VDD", "3V3", "+3.3V", "+5V", "5V", "VIN", "VBAT", "AVDD", "DVDD", "+12V", "VIO", "VDDIO", "PVCC"}
POWER_BOT_NAMES = {"GND", "VSS", "AGND", "DGND", "EP", "PAD", "0V", "PGND", "THERMAL"}
INPUT_LEFT_KEYWORDS = {"IN", "CLK", "SCLK", "SCK", "CS", "SS", "MOSI", "SDI", "SDA", "SCL", "RX", "EN", "RST", "RESET", "ENABLE", "TRIG", "THRES", "A0", "A1", "A2"}
OUTPUT_RIGHT_KEYWORDS = {"OUT", "MISO", "SDO", "TX", "INT", "IRQ", "ALERT", "PWM", "READY", "DRDY", "STATUS", "DISCH", "LED"}

class PinSpec:
    def __init__(self, num: str, name: str, ptype: str = "passive", side: str = "auto"):
        self.num = str(num)
        self.name = str(name).strip()
        self.ptype = ptype
        self.side = side.lower()

class SymbolBuilder:
    def __init__(self, name: str, ref_prefix: str = "U", lib_name: str = "OhmicCustom"):
        self.name = name
        self.ref_prefix = ref_prefix
        self.lib_name = lib_name
        self.lib_id = f"{lib_name}:{name}"
        self.description = ""
        self.footprint = ""
        self.datasheet = ""
        self.pins: List[PinSpec] = []

    def set_description(self, desc: str) -> 'SymbolBuilder':
        self.description = desc
        return self

    def set_footprint(self, fp: str) -> 'SymbolBuilder':
        self.footprint = fp
        return self

    def set_datasheet(self, ds: str) -> 'SymbolBuilder':
        self.datasheet = ds
        return self

    def add_pin(self, num: str, name: str, ptype: str = "passive", side: str = "auto") -> 'SymbolBuilder':
        """Adds a pin specification to the symbol."""
        self.pins.append(PinSpec(num=num, name=name, ptype=ptype, side=side))
        return self

    @classmethod
    def from_datasheet(
        cls,
        pdf_path: str,
        part_name: Optional[str] = None,
        ref_prefix: str = "U",
        lib_name: str = "OhmicCustom"
    ) -> 'SymbolBuilder':
        """Constructs a SymbolBuilder automatically from an IC datasheet PDF."""
        extractor = DatasheetExtractor()
        text = extractor.load_pdf(pdf_path)
        pins_data = extractor.extract_pin_table(text)
        ratings = extractor.extract_voltage_ratings(text)

        name = part_name or os.path.splitext(os.path.basename(pdf_path))[0]
        builder = cls(name=name, ref_prefix=ref_prefix, lib_name=lib_name)

        desc = f"Synthesized from {os.path.basename(pdf_path)}"
        if "v_min" in ratings and "v_max" in ratings:
            desc += f" (Operating: {ratings['v_min']}V - {ratings['v_max']}V)"
        builder.set_description(desc)

        for p in pins_data:
            builder.add_pin(num=p["number"], name=p["name"], ptype=p.get("type", "passive"), side="auto")

        return builder

    def _determine_side(self, p: PinSpec) -> str:
        """Determines optimal pin side (left, right, top, bottom) using engineering conventions."""
        if p.side in ("left", "right", "top", "bottom"):
            return p.side

        upper = p.name.upper()
        # 1. Power Top
        if upper in POWER_TOP_NAMES or p.ptype == "power_in" and "GND" not in upper and "VSS" not in upper:
            return "top"
        # 2. Power Bottom
        if upper in POWER_BOT_NAMES or "GND" in upper or "VSS" in upper:
            return "bottom"
        # 3. Signals based on type and keywords
        if p.ptype == "input" or any(kw in upper for kw in INPUT_LEFT_KEYWORDS):
            return "left"
        if p.ptype == "output" or any(kw in upper for kw in OUTPUT_RIGHT_KEYWORDS):
            return "right"

        # Default fallback: distribute bidirectional or unknown pins on left
        return "left"

    def build_symbol_definition(self) -> SymbolDefinition:
        """
        Builds and formats a complete KiCad 10 S-expression symbol definition
        with 4-sided pin placement and returns a SymbolDefinition.
        """
        # Partition pins by side
        left_pins: List[PinSpec] = []
        right_pins: List[PinSpec] = []
        top_pins: List[PinSpec] = []
        bottom_pins: List[PinSpec] = []

        for p in self.pins:
            side = self._determine_side(p)
            if side == "top": top_pins.append(p)
            elif side == "bottom": bottom_pins.append(p)
            elif side == "right": right_pins.append(p)
            else: left_pins.append(p)

        # Balance sides if one side is overloaded while the other is empty
        if not right_pins and len(left_pins) > 4:
            half = (len(left_pins) + 1) // 2
            right_pins = left_pins[half:]
            left_pins = left_pins[:half]

        # Calculate bounding box dimensions (2.54mm pitch)
        v_pins = max(len(left_pins), len(right_pins), 2)
        h_pins = max(len(top_pins), len(bottom_pins), 4)

        box_height = round((v_pins + 1) * 2.54, 2)
        box_width = round((h_pins + 2) * 2.54, 2)

        x_left = -round(box_width / 2.0, 2)
        x_right = round(box_width / 2.0, 2)
        y_top = round(box_height / 2.0, 2)
        y_bot = -round(box_height / 2.0, 2)

        # Build S-expression lines
        lines: List[str] = []
        lines.append(f'(symbol "{self.lib_id}"')
        lines.append('\t(in_bom yes) (on_board yes)')
        lines.append(
            f'\t(property "Reference" "{self.ref_prefix}" (at 0 {y_top + 3.81:.2f} 0) '
            f'(effects (font (size 1.27 1.27))))'
        )
        lines.append(
            f'\t(property "Value" "{self.name}" (at 0 {y_bot - 3.81:.2f} 0) '
            f'(effects (font (size 1.27 1.27))))'
        )
        if self.footprint:
            lines.append(f'\t(property "Footprint" "{self.footprint}" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))')
        if self.description:
            lines.append(f'\t(property "Description" "{self.description}" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))')
        if self.datasheet:
            lines.append(f'\t(property "Datasheet" "{self.datasheet}" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))')

        # Sub-symbol _0_1: Body Rectangle
        lines.append(f'\t(symbol "{self.name}_0_1"')
        lines.append(
            f'\t\t(rectangle (start {x_left:.2f} {y_top:.2f}) (end {x_right:.2f} {y_bot:.2f}) '
            f'(stroke (width 0.254)) (fill (type background)))'
        )
        lines.append('\t)')

        # Sub-symbol _1_1: Pins
        lines.append(f'\t(symbol "{self.name}_1_1"')
        parsed_pins: Dict[str, Pin] = {}

        # 1. Place Left Pins (rot=0, pointing right, tip at x_left - 2.54)
        for i, p in enumerate(left_pins):
            py = round(y_top - 2.54 - (i * 2.54), 2)
            tip_x = round(x_left - 2.54, 2)
            lines.append(
                f'\t\t(pin {p.ptype} line (at {tip_x:.2f} {py:.2f} 0) (length 2.54) '
                f'(name "{p.name}" (effects (font (size 1.0 1.0)))) '
                f'(number "{p.num}" (effects (font (size 1.0 1.0)))))'
            )
            parsed_pins[p.num] = Pin(number=p.num, name=p.name, pin_type=p.ptype, rel_x=tip_x, rel_y=py, rel_rot=0.0)

        # 2. Place Right Pins (rot=180, pointing left, tip at x_right + 2.54)
        for i, p in enumerate(right_pins):
            py = round(y_top - 2.54 - (i * 2.54), 2)
            tip_x = round(x_right + 2.54, 2)
            lines.append(
                f'\t\t(pin {p.ptype} line (at {tip_x:.2f} {py:.2f} 180) (length 2.54) '
                f'(name "{p.name}" (effects (font (size 1.0 1.0)))) '
                f'(number "{p.num}" (effects (font (size 1.0 1.0)))))'
            )
            parsed_pins[p.num] = Pin(number=p.num, name=p.name, pin_type=p.ptype, rel_x=tip_x, rel_y=py, rel_rot=180.0)

        # 3. Place Top Pins (rot=270, pointing down, tip at y_top + 2.54)
        for i, p in enumerate(top_pins):
            px = round(x_left + 2.54 + (i * 2.54), 2)
            tip_y = round(y_top + 2.54, 2)
            lines.append(
                f'\t\t(pin {p.ptype} line (at {px:.2f} {tip_y:.2f} 270) (length 2.54) '
                f'(name "{p.name}" (effects (font (size 1.0 1.0)))) '
                f'(number "{p.num}" (effects (font (size 1.0 1.0)))))'
            )
            parsed_pins[p.num] = Pin(number=p.num, name=p.name, pin_type=p.ptype, rel_x=px, rel_y=tip_y, rel_rot=270.0)

        # 4. Place Bottom Pins (rot=90, pointing up, tip at y_bot - 2.54)
        for i, p in enumerate(bottom_pins):
            px = round(x_left + 2.54 + (i * 2.54), 2)
            tip_y = round(y_bot - 2.54, 2)
            lines.append(
                f'\t\t(pin {p.ptype} line (at {px:.2f} {tip_y:.2f} 90) (length 2.54) '
                f'(name "{p.name}" (effects (font (size 1.0 1.0)))) '
                f'(number "{p.num}" (effects (font (size 1.0 1.0)))))'
            )
            parsed_pins[p.num] = Pin(number=p.num, name=p.name, pin_type=p.ptype, rel_x=px, rel_y=tip_y, rel_rot=90.0)

        lines.append('\t)')
        lines.append(')')
        sexp_text = "\n".join(lines)

        return SymbolDefinition(
            lib_name=self.lib_name,
            sym_name=self.name,
            raw_sexp=sexp_text,
            pins=parsed_pins,
            ref_prefix=self.ref_prefix,
            default_value=self.name,
            default_footprint=self.footprint,
            description=self.description
        )

    def save_to_file(self, file_path: str):
        """Saves or appends the symbol into a .kicad_sym library file."""
        sym_def = self.build_symbol_definition()
        sexp = sym_def.raw_sexp

        if not os.path.exists(file_path):
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("(kicad_symbol_lib\n\t(version 20260306)\n\t(generator \"ohmic_symbol_builder\")\n")
                f.write(sexp + "\n)\n")
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            last_paren = content.rfind(")")
            if last_paren != -1:
                updated = content[:last_paren] + "\n\t" + sexp + "\n)\n"
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(updated)
