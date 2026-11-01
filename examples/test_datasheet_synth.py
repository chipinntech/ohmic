"""
Ohmic Example: Datasheet Pinout Extraction & Symbol Synthesis.
Demonstrates extracting pin tables and synthesizing custom KiCad symbols.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ohmic import DatasheetExtractor

def test_synthesis():
    sample_text = """
    Pin Description Table for Custom_Micro_IC:
    1   VDD     Power   Positive 3.3V Power Supply
    2   GPIO0   I/O     General Purpose Input Output 0
    3   GPIO1   I/O     General Purpose Input Output 1 (TX)
    4   GPIO2   I/O     General Purpose Input Output 2 (RX)
    5   SDA     I/O     I2C Data Bus
    6   SCL     Output  I2C Clock Output
    7   RESET   Input   Active Low Reset
    8   GND     Power   Ground Supply
    
    Electrical Characteristics:
    Operating Supply Voltage VDD is 3.0V to 3.6V.
    """

    extractor = DatasheetExtractor()
    pins = extractor.extract_pin_table(sample_text)
    ratings = extractor.extract_voltage_ratings(sample_text)

    print(f"Extracted {len(pins)} pins from datasheet:")
    for p in pins:
        print(f"  Pin {p['number']:>2} [{p['type']:<12}]: {p['name']:<8} - {p['description']}")

    print(f"\nExtracted Voltage Ratings: {ratings}")

    # Synthesize KiCad Symbol
    kicad_sym_text = extractor.synthesize_kicad_symbol(
        part_name="Custom_Micro_IC",
        pins=pins,
        ref_prefix="U",
        footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        description="Synthesized 8-pin microcontroller"
    )

    print(f"\nSynthesized KiCad Symbol Definition ({len(kicad_sym_text)} chars):")
    for line in kicad_sym_text.splitlines()[:10]:
        print(f"  {line}")
    print("  ... [pins omitted for brevity] ...")

if __name__ == "__main__":
    test_synthesis()
