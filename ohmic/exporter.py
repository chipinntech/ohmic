"""
Ohmic Headless KiCad CLI Exporter.
Wraps kicad-cli to render PDF/SVG previews and run DRC checks headlessly.
"""

import os
import shutil
import subprocess
from typing import Optional

DEFAULT_KICAD_CLI_PATHS = [
    r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe",
    r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe",
    r"C:\Program Files\KiCad\8.0\bin\kicad-cli.exe",
    r"C:\Program Files\KiCad\7.0\bin\kicad-cli.exe",
    "kicad-cli"
]

class KiCadCliExporter:
    def __init__(self, cli_path: Optional[str] = None):
        self.cli_path = cli_path or self._find_cli()

    def _find_cli(self) -> str:
        for p in DEFAULT_KICAD_CLI_PATHS:
            if os.path.isabs(p) and os.path.exists(p):
                return p
        return "kicad-cli"

    def export_pdf(self, sch_path: str, output_pdf_path: str) -> bool:
        """Exports a .kicad_sch file to a vector PDF."""
        # Ensure parent directory exists
        parent_dir = os.path.dirname(output_pdf_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        cmd = [self.cli_path, "sch", "export", "pdf", "-o", output_pdf_path, sch_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res.returncode == 0 and os.path.exists(output_pdf_path)

    def export_svg(self, sch_path: str, output_path: str) -> bool:
        """Exports a .kicad_sch file to SVG vector graphics."""
        if output_path.lower().endswith(".svg"):
            out_dir = os.path.dirname(output_path) or "."
            sch_base = os.path.basename(sch_path)
            if sch_base.endswith(".kicad_sch"):
                sch_base = sch_base[:-10]
            expected_file = os.path.join(out_dir, f"{sch_base}.svg")
            target_file = output_path
        else:
            out_dir = output_path
            expected_file = os.path.join(out_dir, os.path.basename(sch_path).replace(".kicad_sch", ".svg"))
            target_file = expected_file

        os.makedirs(out_dir, exist_ok=True)
        # If a directory with target_file name exists accidentally, remove it
        if os.path.isdir(target_file):
            shutil.rmtree(target_file, ignore_errors=True)

        cmd = [self.cli_path, "sch", "export", "svg", "-o", out_dir, sch_path]
        res = subprocess.run(cmd, capture_output=True, text=True)

        if res.returncode == 0:
            if os.path.exists(expected_file) and expected_file != target_file:
                try:
                    shutil.copyfile(expected_file, target_file)
                    os.remove(expected_file)
                except Exception:
                    pass
            return os.path.exists(target_file) and os.path.isfile(target_file)
        return False

    def run_erc(self, sch_path: str, report_json_path: Optional[str] = None) -> dict:
        """Runs KiCad ERC in headless JSON mode and parses violations."""
        import json
        if not report_json_path:
            os.makedirs("scratch", exist_ok=True)
            report_json_path = os.path.abspath("scratch/erc_report.json")

        cmd = [
            self.cli_path, "sch", "erc",
            "--format", "json",
            "--severity-all",
            "-o", report_json_path,
            sch_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        violations = []
        if os.path.exists(report_json_path):
            try:
                with open(report_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    violations = data.get("sheets", [{}])[0].get("violations", []) if "sheets" in data else data.get("violations", [])
            except Exception:
                pass
        return {
            "exit_code": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "violations_count": len(violations),
            "violations": violations
        }
