"""
Example: Inspect the Unity Meter Schematic using the Ohmic Engine.
"""

import sys
import os

# Add parent directory to path so ohmic can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ohmic import OhmicSchematic

def main():
    sch_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "unitycircuit", "unity_meters.kicad_sch"))
    print(f"Loading: {sch_file}")

    sch = OhmicSchematic.load(sch_file)
    summary = sch.get_summary()

    print("\n--- Ohmic Schematic Summary ---")
    print(f"Paper Size      : {sch.paper}")
    print(f"Total Components: {summary['components']}")
    print(f"Total Wires     : {summary['wires']}")
    print(f"Total Labels    : {summary['labels']}")
    print(f"Power Symbols   : {summary['power_symbols']}")
    print(f"Distinct Nets   : {summary['distinct_nets']}")

    # Check key net connections
    netlist = sch.get_netlist()
    print("\n--- Key Net Checks ---")
    for net in ["+12V_RELAY", "+3.3V", "GND", "T1_S", "T1_SET"]:
        pins = netlist.get(net, [])
        pin_names = [f"{p['ref']}.{p['pin']}" for p in pins]
        print(f"Net [{net}]: {len(pins)} pins -> {', '.join(sorted(pin_names))}")

if __name__ == "__main__":
    main()
