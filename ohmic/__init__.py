"""
Ohmic - Autonomous Hardware Engineering & KiCad Schematic Engine.
"""

from .engine import OhmicSchematic
from .models import Point, Pin, Component, Wire, Label, Junction, PowerSymbol
from .reader import SchematicReader
from .writer import SchematicWriter
from .router import Router
from .netlist import NetlistTracer
from .exporter import KiCadCliExporter
from .diagnostics import SchematicDiagnostics
from .library import KiCadLibraryManager, SymbolDefinition
from .datasheet import DatasheetExtractor
from .fetcher import CloudFetcher
from .builder import SymbolBuilder, PinSpec

__version__ = "0.2.0"
__all__ = [
    "OhmicSchematic",
    "Point",
    "Pin",
    "Component",
    "Wire",
    "Label",
    "Junction",
    "PowerSymbol",
    "SchematicReader",
    "SchematicWriter",
    "Router",
    "NetlistTracer",
    "KiCadCliExporter",
    "SchematicDiagnostics",
    "KiCadLibraryManager",
    "SymbolDefinition",
    "DatasheetExtractor",
    "CloudFetcher",
    "SymbolBuilder",
    "PinSpec"
]
