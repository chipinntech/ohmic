"""
Ohmic Datasheet & Pinout Extractor.
Extracts pin tables, operating voltage ratings, and mode configurations from IC datasheets (PDF).
Can automatically synthesize valid KiCad symbol definitions (.kicad_sym) from datasheet pinouts.
"""

import os
import re
from typing import Dict, List, Optional, Tuple, Any

class DatasheetExtractor:
    def __init__(self, pdf_path: Optional[str] = None):
        self.pdf_path = pdf_path
        self._text: str = ""

    def load_pdf(self, pdf_path: str, max_pages: int = 50) -> str:
        """Loads and extracts text from PDF using PyMuPDF (fitz) or pypdf."""
        self.pdf_path = pdf_path
        pages_text: List[str] = []

        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            for i in range(min(len(doc), max_pages)):
                pages_text.append(doc[i].get_text())
            doc.close()
        except ImportError:
            try:
                import pypdf
                reader = pypdf.PdfReader(pdf_path)
                for i in range(min(len(reader.pages), max_pages)):
                    txt = reader.pages[i].extract_text()
                    if txt:
                        pages_text.append(txt)
            except Exception as e:
                raise RuntimeError(f"Failed to read PDF {pdf_path}: {e}")

        self._text = "\n".join(pages_text)
        return self._text

    def extract_pin_table(self, text: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Extracts structured pin table records:
        [{"number": "1", "name": "VCC", "type": "power_in", "description": "..."}]
        """
        content = text or self._text
        pins: List[Dict[str, str]] = []

        # Common table line patterns in semiconductor datasheets:
        # e.g., "1   VCC   P   Positive Supply Voltage"
        # e.g., "33  PM0   I   Power Mode Configuration Pin 0"
        pin_re = re.compile(
            r'^\s*(\d{1,3})\s+([A-Za-z0-9_/~#\+\-]+)\s+([A-Za-z/]+|\b[IOPADG]\b)\s+(.+)$',
            re.MULTILINE
        )

        seen_nums = set()
        for match in pin_re.finditer(content):
            num, name, ptype_raw, desc = match.group(1), match.group(2), match.group(3), match.group(4)
            if num in seen_nums:
                continue

            # Standardize pin electrical types for KiCad
            ptype_lower = ptype_raw.lower()
            if ptype_lower in ('p', 'power', 'supply', 'pwr'):
                ptype = 'power_in'
            elif ptype_lower in ('i', 'in', 'input'):
                ptype = 'input'
            elif ptype_lower in ('o', 'out', 'output'):
                ptype = 'output'
            elif ptype_lower in ('i/o', 'in/out', 'bidirectional', 'io'):
                ptype = 'bidirectional'
            elif ptype_lower in ('gnd', 'ground'):
                ptype = 'power_in'
            elif ptype_lower in ('passive', 'pass'):
                ptype = 'passive'
            else:
                ptype = 'passive'

            pins.append({
                "number": num,
                "name": name,
                "type": ptype,
                "description": desc.strip()
            })
            seen_nums.add(num)

        # Sort pins by pin number integer
        pins.sort(key=lambda p: int(p["number"]) if p["number"].isdigit() else 999)
        return pins

    def extract_voltage_ratings(self, text: Optional[str] = None) -> Dict[str, Any]:
        """Extracts recommended operating voltage conditions."""
        content = text or self._text
        ratings: Dict[str, Any] = {}

        # Look for supply voltage specifications (e.g. 3.0V to 3.6V, 4.5V to 5.5V)
        m = re.search(r'(?:supply\s+voltage|operating\s+voltage|VDD|VCC)[^\n]*?(\d+\.?\d*)\s*V\s*(?:to|-)\s*(\d+\.?\d*)\s*V', content, re.IGNORECASE)
        if m:
            ratings["v_min"] = float(m.group(1))
            ratings["v_max"] = float(m.group(2))
            ratings["v_typ"] = round((ratings["v_min"] + ratings["v_max"]) / 2, 2)

        return ratings

    @staticmethod
    def synthesize_kicad_symbol(
        part_name: str,
        pins: List[Dict[str, str]],
        ref_prefix: str = "U",
        footprint: str = "",
        description: str = ""
    ) -> str:
        """
        Synthesizes a complete, valid KiCad (lib_symbols ...) S-expression block
        with left/right dual-in-line pin layout.
        """
        lines: List[str] = []
        lib_id = f"OhmicCustom:{part_name}"
        lines.append(f'(symbol "{lib_id}"')
        lines.append('\t(in_bom yes) (on_board yes)')
        lines.append(f'\t(property "Reference" "{ref_prefix}" (at 0 12.7 0) (effects (font (size 1.27 1.27))))')
        lines.append(f'\t(property "Value" "{part_name}" (at 0 -12.7 0) (effects (font (size 1.27 1.27))))')
        if footprint:
            lines.append(f'\t(property "Footprint" "{footprint}" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))')
        if description:
            lines.append(f'\t(property "Description" "{description}" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))')

        # Generate rectangular body
        n = len(pins)
        half = (n + 1) // 2
        height = max(15.24, (half + 1) * 2.54)
        top_y = height / 2.0
        bot_y = -height / 2.0
        width = 25.4
        left_x = -width / 2.0
        right_x = width / 2.0

        lines.append(f'\t(symbol "{part_name}_0_1"')
        lines.append(f'\t\t(rectangle (start {left_x:.2f} {top_y:.2f}) (end {right_x:.2f} {bot_y:.2f}) (stroke (width 0.254)) (fill (type background)))')
        lines.append('\t)')

        # Place pins: left side (pins 1 to half), right side (pins half+1 to n)
        lines.append(f'\t(symbol "{part_name}_1_1"')
        for i, p in enumerate(pins[:half]):
            py = top_y - 2.54 - (i * 2.54)
            ptype = p.get("type", "passive")
            pnum = p["number"]
            pname = p["name"]
            # Pin on left side points right (rot=0)
            lines.append(
                f'\t\t(pin {ptype} line (at {left_x - 2.54:.2f} {py:.2f} 0) (length 2.54) '
                f'(name "{pname}" (effects (font (size 1.0 1.0)))) '
                f'(number "{pnum}" (effects (font (size 1.0 1.0)))))'
            )

        for i, p in enumerate(pins[half:]):
            py = bot_y + 2.54 + (i * 2.54)
            ptype = p.get("type", "passive")
            pnum = p["number"]
            pname = p["name"]
            # Pin on right side points left (rot=180)
            lines.append(
                f'\t\t(pin {ptype} line (at {right_x + 2.54:.2f} {py:.2f} 180) (length 2.54) '
                f'(name "{pname}" (effects (font (size 1.0 1.0)))) '
                f'(number "{pnum}" (effects (font (size 1.0 1.0)))))'
            )
        lines.append('\t)')
        lines.append(')')

        return "\n".join(lines)
