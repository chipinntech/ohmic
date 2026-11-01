"""
Ohmic CLI Micro-Tool Runner.
Enables Antigravity (and developer shell scripts) to invoke any Ohmic tool
directly from the terminal with JSON input/output.

Usage:
  python ohmic/run_tool.py <tool_name> [args_json_or_key_values]

Examples:
  python ohmic/run_tool.py search_kicad_library '{"query": "ATM90E32"}'
  python ohmic/run_tool.py load_schematic file_path=unitycircuit/unity_meters.kicad_sch
  python ohmic/run_tool.py inspect_schematic_summary
  python ohmic/run_tool.py inspect_components filter_ref=U
  python ohmic/run_tool.py render_schematic_preview
  python ohmic/run_tool.py run_health_check
"""

import sys
import json
import os

# Add ohmic root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ohmic.tools import TOOL_REGISTRY, execute_tool_call, CTX

def parse_args(raw_args):
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
            # Try parsing numbers / booleans
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
            # Single unnamed argument fallback
            parsed["query"] = arg
    return parsed

def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Missing tool name.",
            "available_tools": list(TOOL_REGISTRY.keys())
        }, indent=2))
        sys.exit(1)

    tool_name = sys.argv[1]
    args = parse_args(sys.argv[2:])

    if tool_name not in TOOL_REGISTRY:
        print(json.dumps({
            "error": f"Tool '{tool_name}' not found.",
            "available_tools": list(TOOL_REGISTRY.keys())
        }, indent=2))
        sys.exit(1)

    mutating_tools = {
        "change_component_value", "delete_component", "place_component",
        "place_power_symbol", "place_net_label", "connect_pins", "connect_pin_to_net",
        "add_wire", "auto_junctions", "move_component", "remove_component_and_dangling_wires",
        "replace_component_preserving_nets", "assign_footprint"
    }

    result = execute_tool_call(tool_name, args)
    if tool_name in mutating_tools and isinstance(result, dict) and "error" not in result:
        CTX.save()
        result["saved_to"] = CTX.active_file_path
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
