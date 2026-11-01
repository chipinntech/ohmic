"""
Test Script: Search and extract KiCad symbols using the Ohmic Library Manager.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ohmic import KiCadLibraryManager

def main():
    print("Initializing Ohmic KiCad Library Manager...")
    lib = KiCadLibraryManager()
    print(f"KiCad Symbol Library Directory: {lib.symbol_dir}")
    print(f"Total Symbols Indexed         : {len(lib._index)}")

    queries = ["ESP32-WROOM", "LM358", "NE555", "STM32F103C8", "AO3400A"]
    print("\n--- Testing Search & Part Retrieval ---")
    for q in queries:
        results = lib.search(q, limit=3)
        print(f"\nSearch for '{q}': found {len(results)} matches -> {results}")
        if results:
            first_id = results[0]
            part = lib.get(first_id)
            if part:
                print(f"  [+] Loaded Part       : {part.lib_id}")
                print(f"  [+] Reference Prefix  : {part.ref_prefix}")
                print(f"  [+] Default Footprint : {part.default_footprint}")
                print(f"  [+] Description       : {part.description[:60]}...")
                print(f"  [+] Pin Count         : {len(part.pins)} pins")
                sample_pins = list(part.pins.items())[:4]
                print(f"  [+] Sample Pins       : {[f'Pin {pnum} ({p.name})' for pnum, p in sample_pins]}")

if __name__ == "__main__":
    main()
