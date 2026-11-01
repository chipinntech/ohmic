"""
Ohmic Example: Cloud Symbol Fetching & Custom Symbol Building.
Demonstrates:
1. Pulling missing external symbols directly from official cloud repositories.
2. Building a custom IC symbol (MAX31865 RTD Sensor) with 4-sided pin grouping.
3. Placing the custom symbol into a schematic and compiling to PDF.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ohmic import OhmicSchematic, CloudFetcher, SymbolBuilder, Point

def run_demo():
    print("=" * 65)
    print("Ohmic Cloud Fetcher & Custom Symbol Maker Demo")
    print("=" * 65)

    # 1. Test Cloud Symbol Fetching from GitLab
    print("\n[1/3] Testing Cloud Symbol Fetcher (GitLab API)...")
    fetcher = CloudFetcher()
    sym_name = "AD9513"
    lib_name = "Timer"
    print(f"      Requesting '{lib_name}:{sym_name}' from official cloud repo...")
    raw_sym = fetcher.fetch_and_cache_symbol(f"{lib_name}:{sym_name}")
    if raw_sym:
        print(f"      SUCCESS! Downloaded and cached {len(raw_sym)} bytes.")
    else:
        print("      Cloud fetch fallback.")

    # 2. Build Custom Symbol Declaratively
    print("\n[2/3] Building Custom Symbol: MAX31865 RTD-to-Digital SPI Converter...")
    builder = (
        SymbolBuilder("MAX31865", ref_prefix="U", lib_name="Sensor_Temperature")
        .set_description("RTD-to-Digital Converter with SPI Interface, SSOP-20")
        .set_footprint("Package_SO:SSOP-20_5.3x7.2mm_P0.65mm")
        .set_datasheet("https://www.analog.com/media/en/technical-documentation/data-sheets/MAX31865.pdf")
        # Power Pins
        .add_pin("1", "DVDD", "power_in", side="top")
        .add_pin("2", "AVDD", "power_in", side="top")
        .add_pin("19", "DGND", "power_in", side="bottom")
        .add_pin("20", "AGND", "power_in", side="bottom")
        # SPI & Control Pins (Left side)
        .add_pin("3", "CS", "input", side="left")
        .add_pin("4", "SDI", "input", side="left")
        .add_pin("5", "SCLK", "input", side="left")
        # Data Out & Flags (Right side)
        .add_pin("6", "SDO", "output", side="right")
        .add_pin("7", "DRDY", "output", side="right")
        # RTD Analog Inputs
        .add_pin("8", "BIAS", "passive", side="right")
        .add_pin("9", "REFIN+", "passive", side="right")
        .add_pin("10", "REFIN-", "passive", side="right")
        .add_pin("11", "ISENSOR", "passive", side="right")
        .add_pin("12", "FORCE+", "passive", side="right")
        .add_pin("13", "FORCE2", "passive", side="right")
        .add_pin("14", "RTDIN+", "passive", side="right")
        .add_pin("15", "RTDIN-", "passive", side="right")
    )

    custom_sym_def = builder.build_symbol_definition()
    print(f"      SUCCESS! Built symbol with {len(custom_sym_def.pins)} pins.")
    print(f"      Dimensions: {builder.pins[0].name} on {builder.pins[0].side.upper()}, {builder.pins[2].name} on {builder.pins[2].side.upper()}")

    # Save to local custom library file
    custom_lib_path = "scratch/ohmic_custom.kicad_sym"
    builder.save_to_file(custom_lib_path)
    print(f"      Saved custom library to {custom_lib_path}")

    # 3. Create a Schematic using the Custom Symbol!
    print("\n[3/3] Creating Schematic with Custom Symbol...")
    sch = OhmicSchematic(name="MAX31865_Interface", paper="A4")

    # Register the custom symbol directly into the schematic's raw lib symbols
    sch.lib_symbols_raw[custom_sym_def.lib_id] = custom_sym_def.raw_sexp

    # Place custom chip
    u1 = sch.add_component(
        lib_id=custom_sym_def.lib_id,
        ref="U1",
        value="MAX31865",
        x=150.0,
        y=100.0,
        footprint="Package_SO:SSOP-20_5.3x7.2mm_P0.65mm"
    )
    # Copy pins
    u1.pins = dict(custom_sym_def.pins)

    # Place Decoupling Capacitor and Power Rails
    c1 = sch.add_component("Device:C", ref="C1", value="100nF", x=120.0, y=70.0)
    pwr_vcc = sch.add_power_symbol("+3.3V", x=120.0, y=60.0)
    pwr_gnd = sch.add_power_symbol("GND", x=120.0, y=80.0)

    # Add Power Connections
    sch.connect_points(Point(120.0, 60.0), Point(120.0, 66.19))
    sch.connect_points(Point(120.0, 73.81), Point(120.0, 80.0))

    # Add Net Labels for SPI bus
    sch.connect_pin_to_net("U1", "3", "SPI_CS", stub_length=6.0, direction="left")
    sch.connect_pin_to_net("U1", "4", "SPI_MOSI", stub_length=6.0, direction="left")
    sch.connect_pin_to_net("U1", "5", "SPI_SCK", stub_length=6.0, direction="left")
    sch.connect_pin_to_net("U1", "6", "SPI_MISO", stub_length=6.0, direction="right")
    sch.connect_pin_to_net("U1", "7", "RTD_DRDY", stub_length=6.0, direction="right")

    # Connect top power pin to VCC net
    sch.connect_pin_to_net("U1", "1", "+3.3V", stub_length=6.0, direction="up")
    sch.connect_pin_to_net("U1", "19", "GND", stub_length=6.0, direction="down")

    sch.auto_junctions()
    health = sch.run_health_check()
    print(f"      Schematic Health: {health['status']}")

    # Save and Export to PDF
    out_sch = "scratch/max31865_board.kicad_sch"
    out_pdf = "scratch/max31865_board.pdf"
    sch.save(out_sch)
    print(f"      Saved schematic: {out_sch}")

    success = sch.export_pdf(out_pdf)
    if success:
        print(f"      SUCCESS! Compiled custom IC schematic to PDF: {out_pdf}")
    else:
        print("      PDF compilation error.")

if __name__ == "__main__":
    run_demo()
