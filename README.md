# Ohmic ⚡

**Autonomous AI Hardware Engineering Copilot & Programmatic KiCad Schematic Engine**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![KiCad v7/v8/v9/v10](https://img.shields.io/badge/KiCad-v7%20|%20v8%20|%20v9%20|%20v10-brightgreen.svg)](https://kicad.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Open Source](https://img.shields.io/badge/Open%20Source-❤️-red.svg)](https://github.com/chipinntech/ohmic)

**Ohmic** is an open-source, deterministic hardware design engine and agentic toolsuite that enables developers and AI agents (such as Antigravity, Claude Code, LangGraph, and AutoGen) to inspect, design, wire, verify, and modify production-ready KiCad schematics (`.kicad_sch`) programmatically.

---

## 📑 Table of Contents
1. [The Problem: Why Traditional LLMs Fail at Circuit Design](#-the-problem-why-traditional-llms-fail-at-circuit-design)
2. [How Ohmic Solves Token Exhaustion (95%+ Reduction)](#-how-ohmic-solves-token-exhaustion-95-reduction)
3. [The 7-Phase Autonomous Cognitive Loop](#-the-7-phase-autonomous-cognitive-loop)
4. [Installation](#-installation)
5. [Quickstart: CLI Usage](#-quickstart-cli-usage)
6. [Comprehensive Micro-Tool Reference](#-comprehensive-micro-tool-reference)
7. [Python SDK Usage](#-python-sdk-usage)
8. [Integrating with AI Agent Frameworks](#-integrating-with-ai-agent-frameworks)
9. [How to Extend & Add New Tools](#-how-to-extend--add-new-tools)
10. [Roadmap & Contributing](#-roadmap--contributing)
11. [License](#-license)

---

## 🛑 The Problem: Why Traditional LLMs Fail at Circuit Design

When modern LLMs are tasked with modifying or designing electronic schematics, developers typically dump the raw schematic into the prompt context. This approach consistently fails:

* **Catastrophic Token Exhaustion**: A real-world multi-sheet or sub-metering schematic easily exceeds **50,000 to 100,000 lines of balanced S-expressions** (over 200,000 tokens!). Ingesting this on every turn exhausts context windows and makes agent execution prohibitively slow and expensive.
* **Coordinate & Geometry Hallucination**: LLMs lack spatial awareness in 2D coordinate spaces. When asked to place a resistor and connect it to an MCU, models guess arbitrary coordinates, creating diagonal wires, component overlaps, shorted power rails, and unreadable "wiring spaghetti."
* **Syntax & Structural Corruption**: Generating monolithic `.kicad_sch` text often drops closing parentheses or breaks UUID references, rendering the file unopenable in KiCad.
* **Lack of Deterministic Electrical Feedback**: S-expression parsers only check text grammar, not electrical rules. An agent has no way to know whether an IC pin is floating, open, or shorted until a human runs DRC in KiCad.

---

## ⚡ How Ohmic Solves Token Exhaustion (95%+ Reduction)

Ohmic fundamentally shifts the paradigm from **monolithic text generation** to **granular, deterministic micro-tool execution**:

```
Traditional Approach (Monolithic Dump):
  Prompt: "Add pull-up resistor to pin 5"
  LLM Context: [ 50,000 lines of raw .kicad_sch S-expressions ]  <-- ~180,000 Tokens!
  LLM Output:  [ 50,050 lines of re-written .kicad_sch ]         <-- High latency, syntax errors

Ohmic Approach (Granular Micro-Tools):
  1. inspect_net(query="RESET")          --> Returns connected pins (~60 tokens)
  2. place_component(Device:R, ...)      --> Placed deterministically (~40 tokens)
  3. connect_pins(U1.5, R1.1)            --> Manhattan 90° router (~35 tokens)
  4. run_health_check()                  --> Local host DRC (~50 tokens)
  Total Token Cost: < 300 Tokens (99.8% reduction!)
```

### Key Optimizations:
1. **Atomic Micro-Inspections**: Agents query exact components (`inspect_components filter_ref=U`), specific electrical nets (`inspect_net query=SPI_CLK`), or pin coordinates without reading the entire sheet.
2. **Offline 25,988 KiCad Symbol Index**: Ohmic ships with an indexed, fast-lookup disk cache of all official KiCad 8/9 symbols. Symbols are resolved in `<20ms` locally without spending tokens guessing pinouts or fetching web data.
3. **Local Disjoint-Set Union (DSU) Netlist Engine**: Electrical connectivity, open wire detection, and bus tracing are calculated deterministically on the host CPU in milliseconds with zero LLM tokens.
4. **Targeted Multimodal Crops**: Instead of dumping large raster diagrams or full PDFs into vision models, Ohmic captures crisp, targeted PNG bounding-box crops (`ohmic crop --x 120 --y 90 --w 40 --h 30`) for instant visual clearance verification.

---

## 🔄 The 7-Phase Autonomous Cognitive Loop

Ohmic structures circuit design into an engineering state machine:

```
       [ 1. Circuit Mathematics & Specification Analysis ]
                               │
                               ▼
             [ 2. Spatial Query & Canvas Discovery ]
         (Find target IC coordinates, free clearance zones)
                               │
                               ▼
          [ 3. Parametric Component Placement & Routing ]
        (get_next_reference -> place_component -> connect_pins)
                               │
                               ▼
        [ 4. Algorithmic Health Check (run_health_check) ]
       --> Detects open pins, floating power flags, dangling stubs
                               │
                               ▼
         [ 5. Visual Multimodal Inspection (capture_multimodal_crop) ]
       --> Re-reads raster PNG: catches symbol overlaps & text crowding
                               │
                               ▼
           [ 6. Spatial Refactoring & Auto-Clearance Lint ]
       --> auto_clearance_lint or shift_block for breathing room
                               │
                               ▼
              [ 7. Final Netlist Audit (inspect_netlist) ]
       --> Confirms closed electrical loops and correct net names
```

---

## 📦 Installation

### Prerequisites
* **Python**: `3.9` or higher
* **KiCad** (Optional, for vector rendering): KiCad v7, v8, or v9 installed (`kicad-cli` on PATH).

### Install via pip (Development Mode)
```bash
git clone https://github.com/chipinntech/ohmic.git
cd ohmic
pip install -e .
```

Verify installation:
```bash
ohmic --help
```

---

## 🚀 Quickstart: CLI Usage

Ohmic automatically discovers any `.kicad_sch` file in your current working directory, or you can specify a file with `--sch <path>`.

### 1. Inspect a Schematic
```bash
# Summarize the active schematic (components, nets, wires)
ohmic inspect_schematic_summary

# List components with filter
ohmic inspect_components filter_ref=U

# Deep-dive into an electrical net
ohmic inspect_net query=ESP_EN
```

### 2. Search Symbols in KiCad Official Library
```bash
# Search across 25,988 indexed symbols
ohmic search_kicad_library query=ATM90E36

# Inspect pinout and electrical types
ohmic get_part_pinout lib_id=Sensor_Energy:ATM90E26-YU
```

### 3. Place & Route Components
```bash
# Place a 10k 0805 pull-up resistor
ohmic place_component lib_id="Device:R" ref="R1" value="10k" x=120.0 y=95.0 footprint="Resistor_SMD:R_0805_2012Metric"

# Place a +3V3 power flag
ohmic place_power_symbol name="+3V3" x=120.0 y=85.0

# Connect pins using orthogonal 90° Manhattan router
ohmic connect_pins ref1="U1" pin1="5" ref2="R1" pin2="1"

# Attach a net label stub directly to an IC pin
ohmic attach_net_label comp="U1" pin="14" name="LORA_DIO0" dir="left"

# Detect and insert T-junction dots
ohmic auto_junctions
```

### 4. Run DRC Health Check
```bash
# Detect open pins, dangling wire stubs, and orphaned power flags
ohmic run_health_check
```

### 5. Visual Inspection Crop
```bash
# Capture a high-res PNG centered at (X=120mm, Y=95mm)
ohmic crop --x 120.0 --y 95.0 --w 40 --h 30 --out crop.png
```

---

## 🛠️ Comprehensive Micro-Tool Reference

Ohmic exposes over 40 granular tools categorized into 4 core functional domains:

### A. Schematic Inspection & Spatial Discovery
| Command | Parameters | Description |
| :--- | :--- | :--- |
| `inspect_schematic_summary` | None | Returns component count, total wires, nets, and active file |
| `search_schematic` | `query`, `type` | Searches active canvas for components, pins, or net labels |
| `inspect_components` | `filter_ref` | Lists placed components with values, footprints, and coordinates |
| `inspect_component_positions`| None | Exact `(X, Y)` coordinates of all parts and pin connection tips |
| `inspect_netlist` | None | Full electrical netlist mapping nets to connected pins |
| `inspect_net` | `query` | Detailed connectivity trace for a net or pin |
| `find_open_canvas_zone` | `width`, `height` | Finds collision-free `(X, Y)` coordinates on sheet |

### B. Library & Datasheet Intelligence
| Command | Parameters | Description |
| :--- | :--- | :--- |
| `search_kicad_library` | `query`, `limit` | Searches 25,988 official KiCad symbols in `<20ms` |
| `get_part_pinout` | `lib_id` | Returns pin numbers, names, and electrical types |
| `synthesize_custom_symbol` | `spec` | Synthesizes a valid 4-sided KiCad symbol from JSON pin table |
| `search_datasheet` | `part_number` | Extracts pin tables and electrical ratings from PDF datasheets |

### C. Placement, Wiring & Parametric Editing
| Command | Parameters | Description |
| :--- | :--- | :--- |
| `place_component` | `lib_id`, `ref`, `value`, `x`, `y`, `footprint` | Places part at coordinates with optional rotation |
| `place_power_symbol` | `name`, `x`, `y` | Places power/ground symbol (`+3V3`, `+5V`, `GND`, `AGND`) |
| `place_net_label` | `text`, `x`, `y`, `orientation` | Places net label on wire or coordinate |
| `attach_net_label` | `comp`, `pin`, `name`, `dir`, `len` | Draws wire stub from pin and attaches label cleanly |
| `connect_pins` | `ref1`, `pin1`, `ref2`, `pin2` | Generates 90° orthogonal Manhattan route between pins |
| `add_wire` | `start_x`, `start_y`, `end_x`, `end_y` | Places a single orthogonal wire segment |
| `auto_junctions` | None | Evaluates T-junctions and places junction dots |
| `change_component_value` | `ref`, `new_value` | Updates part value in place |
| `assign_footprint` | `ref`, `footprint` | Assigns or modifies PCB footprint |
| `move_component` | `ref`, `new_x`, `new_y` | Translates component to new coordinates |
| `delete_component` | `ref` | Deletes component from canvas |
| `remove_component_and_dangling_wires` | `ref` | Deletes part and associated open wire stubs |

### D. Verification, DRC & Exporters
| Command | Parameters | Description |
| :--- | :--- | :--- |
| `run_health_check` | None | Algorithmic DRC: catches open stubs, ungrounded pins, orphans |
| `auto_clearance_lint` | None | Auto-shifts colliding component designators and labels |
| `capture_multimodal_crop` | `center_x`, `center_y`, `w`, `h`, `out` | Generates high-res PNG crop for multimodal visual check |
| `render_schematic_preview` | `format` | Compiles full vector SVG or PDF via `kicad-cli` |

---

## 🐍 Python SDK Usage

You can embed Ohmic directly into your Python automation workflows or custom agents:

```python
from ohmic import OhmicSchematic, Point

# 1. Initialize or load a schematic
sch = OhmicSchematic(name="SensorNode", paper="A4")

# 2. Add components from the official library
mcu = sch.add_component("MCU_Module:ESP32-WROOM-32E", ref="U1", value="ESP32-WROOM-32E", x=120.0, y=90.0)
r_pullup = sch.add_component("Device:R", ref="R1", value="10k", x=95.0, y=80.0)
c_bypass = sch.add_component("Device:C", ref="C1", value="100nF", x=95.0, y=105.0)

# 3. Add Power Symbols
vcc = sch.add_power_symbol("+3V3", x=95.0, y=70.0)
gnd = sch.add_power_symbol("GND", x=95.0, y=115.0)

# 4. Orthogonally connect pins
sch.connect_pins("U1", "2", "R1", "2")  # ESP32 EN to Pull-up
sch.connect_pins("R1", "1", "+3V3", "1")
sch.connect_pins("C1", "2", "GND", "1")

# 5. Resolve junctions and run DRC
sch.auto_junctions()
drc_results = sch.run_health_check()
print("DRC Status:", drc_results["status"])

# 6. Save directly to KiCad format
sch.save("SensorNode.kicad_sch")
```

---

## 🤖 Integrating with AI Agent Frameworks

### LangGraph / LangChain
Ohmic tools map directly to LangChain/LangGraph tools:

```python
from langchain.tools import tool
from ohmic.tools import TOOL_REGISTRY, execute_tool_call

@tool
def ohmic_tool(tool_name: str, arguments: dict):
    """Execute an atomic Ohmic EDA tool on the active KiCad schematic."""
    return execute_tool_call(tool_name, arguments)
```

### Antigravity & Claude Code
Ohmic is packaged with a ready-to-use Antigravity skill located in:
`plugins/ohmic/skills/ohmic/SKILL.md`

Any assistant with shell access (`run_command`) can invoke `ohmic <tool_name>` directly with zero prompt engineering overhead.

---

## 💡 How to Extend & Add New Tools

Adding custom tools to Ohmic is simple and modular:

1. **Define Your Tool Function** in `ohmic/tools.py`:
```python
def my_custom_circuit_block(mcu_ref: str, rail_voltage: str = "3.3V") -> Dict[str, Any]:
    """Places a standard decoupling and reset supervisor block."""
    # Your logic using CTX.schematic ...
    CTX.save()
    return {"status": "SUCCESS", "placed": ["R_boot", "C_decouple"]}
```

2. **Register in `TOOL_REGISTRY`**:
```python
TOOL_REGISTRY["my_custom_circuit_block"] = my_custom_circuit_block
```

3. **Declare Function Schema**:
Add the Gemini/OpenAI function schema to `TOOL_DECLARATIONS` in `ohmic/tools.py` so agents receive structured parameters.

---

## 🗺️ Roadmap & Contributing

We welcome contributions from electrical engineers, software developers, and AI researchers!

- [x] Full KiCad v7, v8, v9 `.kicad_sch` reading and writing
- [x] Fast local indexing of 25,988 KiCad symbols
- [x] Orthogonal Manhattan auto-router with automatic T-junctions
- [x] Disjoint-Set Union (DSU) electrical netlist tracer
- [x] Headless SVG and multimodal PNG crop generation
- [ ] **Hierarchical Sheet Multi-Page Routing**: Automatic inter-sheet pin and hierarchical label synchronization
- [ ] **Autorouted Bus Bundles**: Multi-line parallel bus routing (I2C, SPI, 8-bit parallel)
- [ ] **SPICE Netlist Export & Headless Ngspice Simulation**: Automated simulation loop with automated resistor/capacitor tuning

### Contributing
1. Fork the repo: `https://github.com/chipinntech/ohmic`
2. Create your branch: `git checkout -b feature/my-new-tool`
3. Commit your changes: `git commit -m "Add my-new-tool"`
4. Push to branch: `git push origin feature/my-new-tool`
5. Open a Pull Request!

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

Developed with ❤️ by **Chipinn Technologies Ltd** for the open hardware and AI community.
