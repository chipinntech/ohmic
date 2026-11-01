# Ohmic System Architecture: Hierarchical Block-Decomposed Circuit Generation

## 1. Executive Summary & Problem Formulation

### The Monolithic Generation Problem
In traditional LLM-based code generation, an agent can often generate a script or HTML page in a single pass. However, applying a single-pass, monolithic approach to electronic hardware design invariably fails for circuits with more than 4–5 components:
* **Token Overhead & Context Saturation**: Juggling 30+ components with 100+ individual pins, orientation transformations, and 2D coordinates exceeds reliable reasoning limits.
* **Component Clumping & Overlap**: Without spatial partitioning, components overlap or clump unpredictably on the 2D canvas.
* **Wiring Spaghetti**: Routing wires directly across large canvas distances creates chaotic crossings, accidental short circuits, and unreadable schematics.
* **Fragile Modifications**: Asking an agent to "add a battery charger" to an existing flat schematic often leads to accidental deletion or perturbation of unrelated existing nets.

### The Solution: Hierarchical Block Decomposition
Human electrical engineers design systems modularly using **Functional Sub-Circuits (Blocks)**. This architecture formalizes that exact engineering methodology into a 5-phase deterministic pipeline for autonomous agents.

---

## 2. High-Level Architecture Pipeline

```
                              ┌──────────────────────────────────────────────┐
                              │            NATURAL LANGUAGE PROMPT           │
                              │     (or Existing KiCad .kicad_sch File)      │
                              └──────────────────────┬───────────────────────┘
                                                     │
                                                     ▼
     ┌───────────────────────────────────────────────────────────────────────────────────────────────┐
     │ PHASE 1: REQUIREMENTS DECONSTRUCTION & BLOCK GRAPH                                            │
     │ - Extract inputs, outputs, operating voltage domains, and functions                           │
     │ - Formulate Directed Graph of CircuitBlocks                                                   │
     │ - Establish Net Contracts (Global Bus Definitions: VCC, GND, I2C, SPI, UART, Control)          │
     └───────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                                     │
                                                     ▼
     ┌───────────────────────────────────────────────────────────────────────────────────────────────┐
     │ PHASE 2: SPATIAL CANVAS FLOORPLANNING                                                         │
     │ - Partition sheet (A4/A3) into standard functional territories:                              │
     │   * Top-Left: Primary Power Ingestion & Regulators                                            │
     │   * Center: Main Microcontroller / Processing Engine                                          │
     │   * Left / Bottom-Left: Inputs, Sensors, Signal Conditioning                                  │
     │   * Right: Actuators, Motor Drivers, Outputs, Terminal Blocks                                 │
     │ - Assign non-overlapping bounding boxes (Rect) to each block                                 │
     └───────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                                     │
                                                     ▼
     ┌───────────────────────────────────────────────────────────────────────────────────────────────┐
     │ PHASE 3: INTRA-BLOCK MICRO-SOLVER (Local Placement & Routing)                                 │
     │ For each block independently (parallelizable or sequential micro-steps):                      │
     │   - Place ICs, passives, and discrete components strictly within assigned block bounds       │
     │   - Inject mandatory "hygiene" passives (100nF decoupling <5mm from pins, pull-ups, filters)   │
     │   - Draw local orthogonal Manhattan wires between intra-block pins                            │
     │   - Terminate external connections with standard Net Labels                                   │
     │   - Draw visual dashed boundary & block title text                                            │
     └───────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                                     │
                                                     ▼
     ┌───────────────────────────────────────────────────────────────────────────────────────────────┐
     │ PHASE 4: GLOBAL BUS INTEGRATION & ROUTING                                                     │
     │ - Reconcile Net Contracts across all blocks                                                   │
     │ - Verify power supply rails match downstream block requirements                               │
     │ - Place global highway trunks or net labels matching inter-block contracts                    │
     │ - Run auto-junction detection to place KiCad connection dots at T-intersections               │
     └───────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                                     │
                                                     ▼
     ┌───────────────────────────────────────────────────────────────────────────────────────────────┐
     │ PHASE 5: ELECTRICAL HEALTH & DRC VERIFICATION                                                 │
     │ - Disjoint-Set Union (DSU) Electrical Netlist Trace                                           │
     │ - Voltage Domain Compatibility Check (prevent 5V driving 3.3V inputs without shifting)        │
     │ - Diagnostics for open/dangling wire stubs, unpowered IC pins, or floating power flags        │
     │ - Final Vector SVG & PDF Compilation via kicad-cli                                            │
     └───────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Data Abstractions

### 3.1 The `CircuitBlock` Model
The fundamental building block in the Ohmic engine is the `CircuitBlock`, representing an isolated, self-contained functional subsystem:

```python
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum

class BlockCategory(str, Enum):
    POWER = "POWER"                 # Regulators, battery chargers, DC-DC buck/boost
    CONTROLLER = "CONTROLLER"       # MCU, SoC, crystals, reset circuits
    SENSOR_INPUT = "SENSOR_INPUT"   # Sensors, ADCs, voltage dividers, analog front-ends
    OUTPUT_DRIVER = "OUTPUT_DRIVER" # Relays, MOSFET switches, motor drivers, LEDs
    COMMUNICATION = "COMMUNICATION" # USB, RS485, CAN bus, transceiver headers
    PROTECTION = "PROTECTION"       # TVS diodes, PTC fuses, reverse polarity P-MOS

@dataclass
class Rect:
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x_min + self.x_max) / 2.0, (self.y_min + self.y_max) / 2.0)

@dataclass
class NetPort:
    port_name: str          # e.g., "SDA", "VCC_3V3", "EN"
    net_name: str           # Global net label to connect to: "I2C_SDA"
    direction: str          # "INPUT", "OUTPUT", "BIDIRECTIONAL", "POWER"
    voltage_domain: float   # e.g., 3.3, 5.0, 12.0

@dataclass
class CircuitBlock:
    id: str                                # Unique slug: "power_supply_ldo"
    title: str                             # Display title: "3.3V 500mA LDO Regulator"
    category: BlockCategory                # Functional category
    bounds: Rect                           # Allocated 2D canvas region
    component_refs: List[str] = field(default_factory=list) # ["U1", "C1", "C2"]
    internal_wires: List[str] = field(default_factory=list) # UIDs of internal wires
    exposed_ports: List[NetPort] = field(default_factory=list) # Block I/O interface
    notes: List[str] = field(default_factory=list)
```

---

## 4. Detailed Phased Execution

### Phase 1: Requirements Deconstruction & Net Contracts
When given a user prompt (or modification request), the agent first formulates a **Block Graph Contract** before touching schematic files.

#### Example Prompt:
> *"Design a smart irrigation node powered by a 12V DC barrel jack, with an ESP32-WROOM-32, a capacitive soil moisture sensor on ADC, and a 12V solenoid valve driven by an N-channel MOSFET."*

#### Generated Block Contract:
1. **Block A (`POWER`)**: 12V Ingest $\to$ 3.3V Step-down (Buck or LDO).
   * *Exposes*: `+12V_RAW`, `+3.3V`, `GND`.
2. **Block B (`CONTROLLER`)**: ESP32-WROOM-32 with strapping passives and decoupling.
   * *Consumes*: `+3.3V`, `GND`.
   * *Exposes*: `ADC_SOIL`, `SOLENOID_GATE`.
3. **Block C (`SENSOR_INPUT`)**: 3.3V Soil Sensor Header & RC Low-Pass Filter.
   * *Consumes*: `+3.3V`, `GND`.
   * *Connects To*: `ADC_SOIL`.
4. **Block D (`OUTPUT_DRIVER`)**: N-channel Power MOSFET with gate pull-down & flyback diode.
   * *Consumes*: `+12V_RAW`, `GND`, `SOLENOID_GATE`.

---

### Phase 2: Reverse-Engineering & Block Discovery (For Existing Schematics)
When an existing `.kicad_sch` is loaded for editing or inspection:
1. **Connectivity Clustering via DSU**:
   * All components sharing low-impedance passive paths (resistors, caps, inductors) without crossing digital IC boundaries are clustered together.
2. **Semantic Classification**:
   * Components linked to voltage regulator pin names (`VIN`, `VOUT`, `SW`, `FB`) are automatically assigned to `BlockCategory.POWER`.
   * Multi-pin ICs with `GPIO`, `XTAL`, `VDDA` are assigned to `BlockCategory.CONTROLLER`.
   * Transistors connected to connectors or inductive symbols are assigned to `BlockCategory.OUTPUT_DRIVER`.
3. **Headroom & Resource Analysis**:
   * Evaluates available GPIOs, uncommitted ADC channels, and current capacity of existing voltage rails before deciding where to attach new peripherals.

---

### Phase 3: Spatial Floorplanning & Standard EE Canvas Rules
To guarantee professional aesthetics, the canvas follows standard electrical engineering reading conventions:

| Canvas Region | Assigned Subsystem | Standard Direction of Flow |
| :--- | :--- | :--- |
| **Top-Left** | Primary Power Input, Fuses, DC-DC Regulators | Top to Bottom, Left to Right |
| **Center** | Microcontroller / SoC / Core Logic | Inputs arriving from Left, Outputs leaving to Right |
| **Left / Mid-Left** | Signal Ingestion, Sensor Headers, Op-Amps, ADCs | Signals flow eastward toward MCU |
| **Right / Mid-Right**| Output Drivers, Relays, MOSFETs, Connectors | Control signals flow eastward toward outputs |
| **Top-Right** | Auxiliary Subsystems / Visual Status LEDs | Localized indicators |
| **Bottom** | High-density external interfaces, Debug headers (JTAG/SWD) | Accessible edge placement |

```
┌────────────────────────────────────────────────────────────────────────┐
│ KiCad Canvas (A4 / A3)                                                │
│                                                                        │
│  ┌───────────────────────────┐         ┌────────────────────────────┐  │
│  │   BLOCK: POWER REGULATION │         │   BLOCK: STATUS INDICATORS │  │
│  │   (12V -> 3.3V LDO/Buck)  │         │   (LEDs, Buzzers)          │  │
│  └───────────────────────────┘         └────────────────────────────┘  │
│                                                                        │
│  ┌───────────────────────────┐  Net    ┌────────────────────────────┐  │
│  │   BLOCK: SENSORS & INPUTS │  Labels │   BLOCK: OUTPUT DRIVERS    │  │
│  │   (I2C Temp, Analog In)   ├────────►│   (MOSFET, Relays)         │  │
│  └───────────────────────────┘         └────────────────────────────┘  │
│                │                                     ▲                 │
│                ▼                                     │                 │
│  ┌───────────────────────────────────────────────────┴──────────────┐  │
│  │   BLOCK: CORE MICROCONTROLLER (ESP32 / STM32)                    │  │
│  │   (Decoupling, Bootstrapping, Crystal, Reset RC)                 │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 4: Intra-Block Micro-Solving & Passives Synthesis
Each block is solved inside its local coordinate space:

1. **IC Center Pin Placement**:
   * The primary IC of the block is placed at the center of the assigned bounding box.
2. **Mandatory Hardware Hygiene Rules**:
   * **Decoupling**: A 100nF ceramic capacitor is automatically placed within 5mm of every `VCC`/`VDD` pin, wired directly to `GND`.
   * **I2C Bus Pull-Ups**: If an I2C bus is instantiated, two $4.7\text{k}\Omega$ resistors are placed pull-up to the local $V_{DD}$.
   * **Reset Circuitry**: An active-low reset line receives a $10\text{k}\Omega$ pull-up and a $100\text{nF}$ cap to ground to ensure clean power-on ramping.
   * **Inductive Suppression**: Any relay coil or solenoid driver automatically gets a parallel reverse-biased flyback diode (e.g., 1N4148 or 1N4007).
3. **Visual Frame Annotations**:
   * A rectangular graphic bounding box with dashed styling and a prominent text title (e.g., `--- POWER SUPPLY (3.3V) ---`) is written to KiCad's graphical layer, creating immediately recognizable schematics.

---

### Phase 5: Inter-Block Integration & Health DRC

1. **Net Label Abstraction Over Wires**:
   * Inter-block connections **never** cross the canvas as continuous drawn lines.
   * Instead, short orthogonal stubs (10mm) exit the component pin and terminate in standard KiCad **Local/Global Net Labels** (`+3V3`, `I2C_SDA`, `I2C_SCL`, `VALVE_EN`).
   * This completely prevents visual line intersections, accidental T-junctions, and layout tangling.
2. **Electrical Rule Check (ERC) Gate**:
   * **Floating Pin Scan**: Confirms all passive pins have at least one valid wire attached.
   * **Power Integrity Check**: Ensures every IC $V_{CC}$ pin is topologically connected through the DSU graph to a valid Power Symbol (`+3V3`, `+5V`, etc.).
   * **Single-Driver Bus Enforcement**: Ensures output pins are not shorted directly together.

---

## 5. Incremental Editing & Delta Operations

When an existing circuit needs an update, the block architecture makes modifications safe and deterministic:

### Scenario: "Add an SD card reader to the existing ESP32 meter"
1. **Analyze Existing Schematic**:
   * Agent parses existing schematic $\to$ identifies `PowerBlock`, `MCUBlock`, and `SensorBlock`.
   * Evaluates ESP32 GPIOs $\to$ detects free SPI pins: `GPIO18 (SCK)`, `GPIO19 (MISO)`, `GPIO23 (MOSI)`, `GPIO5 (CS)`.
2. **Allocate Delta Block**:
   * Floorplanner finds vacant space on the bottom canvas $\to$ reserves `Rect(x_min=120, y_min=140, x_max=180, y_max=190)`.
3. **Synthesize `SDCardBlock`**:
   * Places MicroSD socket symbol (`Connector:Micro_SD_Card_Det`).
   * Places local 10µF + 100nF decoupling capacitors.
   * Attaches net labels: `SPI_SCK`, `SPI_MISO`, `SPI_MOSI`, `SD_CS`, `+3.3V`, `GND`.
4. **Connect to Existing MCU**:
   * Adds four short net label stubs to the corresponding ESP32 pins in `MCUBlock`.
   * **Zero lines** in the existing power supply or sensor blocks are modified or moved.

---

## 6. Implementation Map for Ohmic Core

| File | Target Implementation |
| :--- | :--- |
| `ohmic/blocks.py` | Data models: `CircuitBlock`, `NetPort`, `BlockCategory`, `Rect`, and `BlockManager`. |
| `ohmic/floorplanner.py` | Canvas layout allocator: computes non-overlapping bounding boxes based on sheet size. |
| `ohmic/passives.py` | Automatic passives synthesizer: calculates and places decoupling, pull-ups, and dividers. |
| `ohmic/tools.py` | New agent micro-tools: `create_circuit_block`, `auto_floorplan`, `attach_block_ports`. |
| `ohmic/agent.py` | Updated Gemini system instruction enforcing Phase 1 Contract generation before tool calls. |

---

## 7. Summary
By decoupling electronic design into **Contract Definition**, **Spatial Floorplanning**, **Intra-Block Solving**, and **Net Label Interconnection**, Ohmic transforms circuit design from an error-prone monolithic guessing game into a deterministic, production-grade automated engineering engine.
