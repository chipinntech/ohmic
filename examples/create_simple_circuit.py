"""
Ohmic Example: Programmatic Schematic Generation.
Creates a complete NE555 Timer Astable LED Flasher circuit from scratch,
routes connections orthogonally, checks health, and exports to PDF.
"""

import sys
import os

# Add ohmic to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ohmic import OhmicSchematic, Point

def build_555_flasher_circuit():
    print("=" * 60)
    print("Ohmic Autonomous Circuit Builder: NE555 Astable Flasher")
    print("=" * 60)

    # 1. Initialize Blank Schematic (A4 Landscape)
    sch = OhmicSchematic(name="NE555_LED_Flasher", paper="A4")

    # 2. Place Components
    print("\n[1/5] Placing Circuit Components...")
    u1 = sch.add_component("Timer:NE555P", ref="U1", value="NE555P", x=150.0, y=105.0)
    
    # Timing Ladder (Left Side)
    r1 = sch.add_component("Device:R", ref="R1", value="10k", x=105.0, y=80.0)
    r2 = sch.add_component("Device:R", ref="R2", value="100k", x=105.0, y=105.0)
    c1 = sch.add_component("Device:C", ref="C1", value="10uF", x=105.0, y=135.0)
    
    # Control Decoupling Capacitor (Above CONT pin)
    c2 = sch.add_component("Device:C", ref="C2", value="10nF", x=165.0, y=75.0)
    
    # Output Indicator (Right Side)
    r3 = sch.add_component("Device:R", ref="R3", value="330", x=185.0, y=105.0, rot=90.0)
    d1 = sch.add_component("Device:LED", ref="D1", value="RED", x=210.0, y=105.0, rot=90.0)

    # 3. Place Power Symbols
    print("[2/5] Placing Power Symbols (+5V & GND)...")
    # +5V rails
    pwr_vcc1 = sch.add_power_symbol("+5V", x=105.0, y=70.0)
    pwr_vcc2 = sch.add_power_symbol("+5V", x=152.54, y=88.0)
    pwr_vcc3 = sch.add_power_symbol("+5V", x=135.0, y=92.0)

    # GND rails
    pwr_gnd1 = sch.add_power_symbol("GND", x=150.0, y=122.0)
    pwr_gnd2 = sch.add_power_symbol("GND", x=105.0, y=145.0)
    pwr_gnd3 = sch.add_power_symbol("GND", x=165.0, y=85.0)
    pwr_gnd4 = sch.add_power_symbol("GND", x=210.0, y=116.0)

    # 4. Route Electrical Connections
    print("[3/5] Routing Orthogonal Manhattan Connections...")

    # Power connections
    sch.connect_points(Point(105.0, 70.0), Point(105.0, 76.19)) # +5V to R1 top (pin 1)
    sch.connect_points(Point(152.54, 94.84), Point(152.54, 88.0)) # U1 pin 8 to +5V
    sch.connect_points(Point(139.84, 99.92), Point(135.0, 99.92)) # U1 pin 4 (RST)
    sch.connect_points(Point(135.0, 99.92), Point(135.0, 92.0))

    # GND connections
    sch.connect_points(Point(150.0, 115.16), Point(150.0, 122.0)) # U1 pin 1 to GND
    sch.connect_points(Point(105.0, 138.81), Point(105.0, 145.0)) # C1 pin 2 to GND
    sch.connect_points(Point(165.0, 78.81), Point(165.0, 85.0))   # C2 pin 2 to GND
    sch.connect_points(Point(210.0, 108.81), Point(210.0, 116.0)) # D1 pin 1 (K) to GND

    # Timing ladder: R1 pin 2 -> R2 pin 1
    sch.connect_points(Point(105.0, 83.81), Point(105.0, 101.19))
    # DISCH (pin 7) to ladder node between R1 and R2
    sch.connect_points(Point(139.84, 102.46), Point(105.0, 92.5), bias="vertical")

    # R2 pin 2 -> C1 pin 1
    sch.connect_points(Point(105.0, 108.81), Point(105.0, 131.19))
    # TRIG (pin 2) & THRES (pin 6) to ladder node between R2 and C1
    ladder_node_y = 120.0
    sch.connect_points(Point(139.84, 110.08), Point(120.0, 110.08)) # Pin 2 (TRIG)
    sch.connect_points(Point(139.84, 107.54), Point(120.0, 107.54)) # Pin 6 (THRES)
    sch.connect_points(Point(120.0, 107.54), Point(120.0, 110.08))
    sch.connect_points(Point(120.0, 110.08), Point(120.0, ladder_node_y))
    sch.connect_points(Point(120.0, ladder_node_y), Point(105.0, ladder_node_y))

    # Control capacitor: U1 pin 5 (CONT) -> C2 pin 1
    sch.connect_points(Point(150.0, 94.84), Point(165.0, 94.84))
    sch.connect_points(Point(165.0, 94.84), Point(165.0, 71.19))

    # Output indicator: U1 pin 3 (OUT) -> R3 -> D1 (LED)
    sch.connect_pins("U1", "3", "R3", "1")
    sch.connect_pins("R3", "2", "D1", "2")

    # Net Labels for test points
    sch.add_label("OUT_PULSE", x=170.0, y=103.0)
    sch.add_label("TIMING_RAMP", x=105.0, y=120.0)

    # 5. Auto-Detect and Place Junctions
    print("[4/5] Auto-Detecting T-Junctions...")
    junctions = sch.auto_junctions()
    print(f"      Placed {len(junctions)} electrical junctions automatically.")

    # 6. Diagnostics & Verification
    print("[5/5] Running Engine Diagnostics...")
    health = sch.run_health_check()
    summary = sch.get_summary()

    print(f"      Components: {summary['components']}")
    print(f"      Wires: {summary['wires']}")
    print(f"      Junctions: {summary['junctions']}")
    print(f"      Distinct Electrical Nets: {summary['distinct_nets']}")
    print(f"      Health Check: {health['status']}")
    if health['dangling_wires_count'] > 0:
        print(f"        * Dangling wire stubs: {health['dangling_wires_count']}")
        for dw in health['dangling_wires']:
            print(f"          stub at {dw['open_point']}")
    if health['orphaned_power_symbols_count'] > 0:
        print(f"        * Orphaned power symbols: {health['orphaned_power_symbols_count']}")

    # 7. Save and Compile
    os.makedirs("scratch", exist_ok=True)
    out_sch = "scratch/ne555_flasher.kicad_sch"
    out_pdf = "scratch/ne555_flasher.pdf"

    print(f"\nWriting schematic to {out_sch}...")
    sch.save(out_sch)

    print(f"Compiling schematic to PDF via KiCad CLI: {out_pdf}...")
    success = sch.export_pdf(out_pdf)
    if success:
        print("SUCCESS! Generated vector PDF verified.")
    else:
        print("KiCad CLI compilation returned non-zero exit code.")

if __name__ == "__main__":
    build_555_flasher_circuit()
