"""
Demonstration: Ohmic Automated Health Inspector & Position Extractor.
Tests both the current clean schematic and the backup to detect orphaned power & dangling wires.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ohmic import OhmicSchematic

def test_file(sch_file: str, label: str):
    print(f"\n==========================================")
    print(f"Testing: {label}")
    print(f"Path   : {sch_file}")
    print(f"==========================================")

    sch = OhmicSchematic.load(sch_file)
    health = sch.run_health_check()

    print(f"Status                  : {health['status']}")
    print(f"Total Components Found  : {health['total_components']}")
    print(f"Total Electrical Nets   : {health['total_nets']}")
    print(f"Dangling Wires Detected : {health['dangling_wires_count']}")
    if health['dangling_wires_count'] > 0:
        for dw in health['dangling_wires'][:5]:
            print(f"  [!] Open wire end at {dw['open_point']} -> other end at {dw['other_end']}")

    print(f"Orphaned Power Symbols  : {health['orphaned_power_symbols_count']}")
    if health['orphaned_power_symbols_count'] > 0:
        for op in health['orphaned_power_symbols']:
            print(f"  [!] Floating {op['name']} symbol ({op['ref']}) at {op['pos']}")

    # Component Position Sample
    positions = sch.get_component_positions()
    sample_refs = ["U4", "IC1", "U5", "J10", "Q1"]
    print("\n--- Component Positions Sample ---")
    for ref in sample_refs:
        if ref in positions:
            c = positions[ref]
            print(f"Component [{ref}] ({c['value']}): Center={c['center']}, Rot={c['rotation']}°, Pins={len(c['pins'])}")

def main():
    curr_sch = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "unitycircuit", "unity_meters.kicad_sch"))
    test_file(curr_sch, "CURRENT CLEAN SCHEMATIC")

    bak_sch = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "unitycircuit", "unity_meters.kicad_sch.backup"))
    test_file(bak_sch, "ORIGINAL BACKUP SCHEMATIC")

if __name__ == "__main__":
    main()
