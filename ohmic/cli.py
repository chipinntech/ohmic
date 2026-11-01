"""
Ohmic Robust CLI Dispatcher.
Provides a clean, shell-agnostic interface for executing EDA micro-tools
without Python syntax escaping issues in Windows PowerShell or Bash.

Usage:
    python -m ohmic.cli inspect-net ESP_EN
    python -m ohmic.cli search-schematic SIM
    python -m ohmic.cli health-check
    python -m ohmic.cli attach-label J7 5 ESP_EN --direction left
    python -m ohmic.cli crop --x 85.09 --y 163.83 --width 45 --height 35 --out j7_crop.png
    python -m ohmic.cli lint-clearance
"""

import sys
import os
import json
import argparse

# Ensure ohmic package is importable
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from ohmic.tools import (
    CTX,
    TOOL_REGISTRY,
    execute_tool_call,
    inspect_net,
    attach_net_label,
    replace_component_preserving_nets,
    auto_clearance_lint,
    search_schematic,
    search_kicad_library,
    search_web,
    run_health_check,
    capture_multimodal_crop,
    render_schematic_preview,
    load_schematic,
    save_schematic,
)

MUTATING_TOOLS = {
    "change_component_value", "delete_component", "place_component",
    "place_power_symbol", "place_net_label", "connect_pins", "connect_pin_to_net",
    "add_wire", "auto_junctions", "move_component", "remove_component_and_dangling_wires",
    "replace_component_preserving_nets", "assign_footprint", "apply_circuit_patch",
    "synthesize_mcu_gpio_driver", "attach_net_label"
}

def parse_kv_or_json(raw_args):
    """Parses JSON or key=value arguments from CLI."""
    if not raw_args:
        return {}
    joined = " ".join(raw_args).strip()
    if joined.startswith("{") and joined.endswith("}"):
        try:
            return json.loads(joined)
        except Exception:
            pass
    
    parsed = {}
    for arg in raw_args:
        if "=" in arg:
            k, v = arg.split("=", 1)
            # Try boolean / float / int conversion
            if v.lower() == "true":
                parsed[k] = True
            elif v.lower() == "false":
                parsed[k] = False
            else:
                try:
                    if "." in v:
                        parsed[k] = float(v)
                    else:
                        parsed[k] = int(v)
                except ValueError:
                    parsed[k] = v
        else:
            if "query" not in parsed:
                parsed["query"] = arg
    return parsed

def main():
    raw_args = sys.argv[1:]
    if not raw_args or raw_args[0] in ("-h", "--help", "help"):
        print("Ohmic Autonomous EDA Command-Line Tool\n")
        print("Usage:")
        print("  ohmic <tool_name> [key=value ...] [JSON_STRING]")
        print("  ohmic --sch <path_to_kicad_sch> <tool_name> [...]")
        print("  ohmic list-tools\n")
        print("Common Tools:")
        print("  inspect_schematic_summary   Summarize components, nets, power symbols, wires")
        print("  search_kicad_library        Search 25,988 KiCad symbols (query=ESP32)")
        print("  search_schematic            Find parts/pins in active schematic (query=...)")
        print("  inspect_components          List components with optional filter_ref=U")
        print("  inspect_netlist             List all electrical nets & connected pins")
        print("  run_health_check            DRC check: detect open stubs & dangling power flags")
        print("  render_schematic_preview    Compile vector preview (format=svg or format=pdf)")
        print("  capture_multimodal_crop     Visual inspection PNG crop (center_x=... center_y=...)")
        print("  place_component             Add part (lib_id=Device:R ref=R1 value=10k x=100 y=100)")
        print("  connect_pins                Orthogonally route (ref1=U1 pin1=1 ref2=R1 pin2=2)")
        print("  change_component_value      Update part value (ref=R1 new_value=4.7k)")
        print("  attach-label                Attach net label to pin (comp pin name [dir])")
        print("  audit-footprints            Verify footprint assignments")
        sys.exit(0)

    # Check for global --sch flag
    sch_override = None
    filtered_args = []
    i = 0
    while i < len(raw_args):
        if raw_args[i] == "--sch" and i + 1 < len(raw_args):
            sch_override = raw_args[i + 1]
            i += 2
        elif raw_args[i].startswith("--sch="):
            sch_override = raw_args[i].split("=", 1)[1]
            i += 1
        else:
            filtered_args.append(raw_args[i])
            i += 1

    if sch_override:
        load_schematic(sch_override)
    elif not CTX.schematic.components:
        CTX._auto_discover_schematic()

    if not filtered_args:
        print(json.dumps({"error": "No tool or command specified."}, indent=2))
        sys.exit(1)

    cmd = filtered_args[0]

    # Special command: list-tools
    if cmd in ("list-tools", "list_tools", "tools"):
        print(json.dumps({
            "active_schematic": CTX.active_file_path or "None (will auto-create on save)",
            "available_tools": list(TOOL_REGISTRY.keys())
        }, indent=2))
        sys.exit(0)

    # 1. Check if cmd is in TOOL_REGISTRY directly
    if cmd in TOOL_REGISTRY:
        tool_args = parse_kv_or_json(filtered_args[1:])
        result = execute_tool_call(cmd, tool_args)
        if cmd in MUTATING_TOOLS and isinstance(result, dict) and "error" not in result:
            save_path = CTX.save()
            result["saved_to"] = save_path
        print(json.dumps(result, indent=2))
        return

    # 2. Check for hyphenated aliases (e.g. inspect-net -> inspect_net)
    underscored_cmd = cmd.replace("-", "_")
    if underscored_cmd in TOOL_REGISTRY:
        tool_args = parse_kv_or_json(filtered_args[1:])
        result = execute_tool_call(underscored_cmd, tool_args)
        if underscored_cmd in MUTATING_TOOLS and isinstance(result, dict) and "error" not in result:
            save_path = CTX.save()
            result["saved_to"] = save_path
        print(json.dumps(result, indent=2))
        return

    # 3. Fallback to classic argparse subcommands
    parser = argparse.ArgumentParser(description="Ohmic EDA Command-Line Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # inspect-net
    p_net = subparsers.add_parser("inspect-net", help="Inspect electrical net or pin")
    p_net.add_argument("query", help="Net name or pin")

    # search-schematic
    p_search = subparsers.add_parser("search-schematic", help="Search components, pins, labels")
    p_search.add_argument("query", help="Search keyword")
    p_search.add_argument("--type", default="all", choices=["all", "components", "labels", "power"])

    # attach-label
    p_label = subparsers.add_parser("attach-label", help="Attach net label to a component pin")
    p_label.add_argument("comp", help="Component reference (e.g. J7, U4)")
    p_label.add_argument("pin", help="Pin number (e.g. 5, 25)")
    p_label.add_argument("name", help="Net label name (e.g. ESP_EN)")
    p_label.add_argument("--dir", default="auto", choices=["auto", "left", "right", "up", "down"])
    p_label.add_argument("--len", type=float, default=5.08, help="Stub length in mm")

    # health-check
    subparsers.add_parser("health-check", help="Run DRC health check")

    # crop
    p_crop = subparsers.add_parser("crop", help="Capture visual inspection crop")
    p_crop.add_argument("--x", type=float, required=True, help="Center X mm")
    p_crop.add_argument("--y", type=float, required=True, help="Center Y mm")
    p_crop.add_argument("--w", type=float, default=50.0, help="Width mm")
    p_crop.add_argument("--h", type=float, default=40.0, help="Height mm")
    p_crop.add_argument("--out", default="multimodal_crop.png", help="Output filename")
    p_crop.add_argument("--zoom", type=float, default=4.0, help="Raster zoom factor")

    # lint-clearance
    subparsers.add_parser("lint-clearance", help="Check and auto-resolve text collisions")

    # preview
    p_prev = subparsers.add_parser("preview", help="Render SVG or PDF preview")
    p_prev.add_argument("--format", default="svg", choices=["svg", "pdf"])

    # search-lib
    p_lib = subparsers.add_parser("search-lib", help="Search official KiCad library")
    p_lib.add_argument("query", help="Part query")
    p_lib.add_argument("--limit", type=int, default=10)

    # audit-footprints
    subparsers.add_parser("audit-footprints", help="Audit footprint assignments")

    try:
        parsed = parser.parse_args(filtered_args)
    except SystemExit:
        sys.exit(1)

    res = None
    if parsed.command == "inspect-net":
        res = inspect_net(parsed.query)
    elif parsed.command == "search-schematic":
        res = search_schematic(parsed.query, parsed.type)
    elif parsed.command == "attach-label":
        res = attach_net_label(parsed.comp, parsed.pin, parsed.name, parsed.dir, parsed.len)
        if CTX.active_file_path:
            CTX.save()
    elif parsed.command == "health-check":
        res = run_health_check()
    elif parsed.command == "crop":
        res = capture_multimodal_crop(parsed.x, parsed.y, parsed.w, parsed.h, parsed.out, parsed.zoom)
    elif parsed.command == "lint-clearance":
        res = auto_clearance_lint()
        if CTX.active_file_path:
            CTX.save()
    elif parsed.command == "preview":
        res = render_schematic_preview(parsed.format)
    elif parsed.command == "search-lib":
        res = search_kicad_library(parsed.query, parsed.limit)
    elif parsed.command == "audit-footprints":
        from ohmic.tools import audit_footprints
        res = audit_footprints()

    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
