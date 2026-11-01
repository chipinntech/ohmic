"""
Ohmic Gemini Agent Orchestrator.
Manages the autonomous tool loop between Google Gemini and Ohmic micro-tools.
Works via standard REST requests (urllib) with zero extra SDK dependencies.
"""

import json
import os
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Any, Generator

from .tools import (
    GEMINI_TOOL_DECLARATIONS,
    execute_tool_call,
    CTX
)

GEMINI_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

SYSTEM_INSTRUCTION = """You are Ohmic, an elite autonomous electronic hardware design engineer.
Your job is to convert natural language circuit specifications into verified, production-ready KiCad schematics using your granular micro-tools.

ENGINEERING DESIGN RULES:
1. Always search the library first (using search_kicad_library) if you need the exact lib_id of microcontrollers, ICs, or sensors.
2. Space components with at least 25mm to 35mm between them on the canvas to maintain professional visual clarity.
3. Decoupling: Always add decoupling capacitors (typically 100nF) between VDD/VCC and GND close to each IC power pin.
4. Clean Wiring: Connect pins using connect_pins or attach net labels using connect_pin_to_net for busses (SPI, I2C, UART).
5. Always call auto_junctions() after routing to place standard KiCad junction dots at all T-intersections.
6. Before finishing, ALWAYS call run_health_check(). If any dangling wire stubs or orphaned power symbols are reported, fix them immediately.
7. Finally, call render_schematic_preview(format='svg') so the user can inspect the vector schematic.
"""

class OhmicGeminiAgent:
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model
        self.history: List[Dict[str, Any]] = []

    def set_api_key(self, api_key: str):
        self.api_key = api_key.strip()

    def run_prompt(self, user_prompt: str, max_turns: int = 15) -> Dict[str, Any]:
        """
        Executes a multi-turn autonomous tool loop with Gemini.
        Returns the final engineering response, step-by-step tool log, and SVG preview.
        """
        if not self.api_key:
            return {
                "status": "ERROR",
                "message": "Missing Gemini API Key. Please provide an API key in settings or set the GEMINI_API_KEY environment variable."
            }

        # Initialize conversation contents
        messages: List[Dict[str, Any]] = [
            {"role": "user", "parts": [{"text": user_prompt}]}
        ]

        steps_log: List[Dict[str, Any]] = []
        final_text = ""
        svg_preview = ""

        # Format Gemini tools payload
        tools_payload = [
            {
                "functionDeclarations": [
                    {
                        "name": decl["name"],
                        "description": decl["description"],
                        "parameters": decl["parameters"]
                    }
                    for decl in GEMINI_TOOL_DECLARATIONS
                ]
            }
        ]

        for turn in range(max_turns):
            req_body = {
                "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
                "contents": messages,
                "tools": tools_payload
            }

            resp_data = self._call_gemini_api(req_body)
            if "error" in resp_data:
                return {
                    "status": "ERROR",
                    "message": f"Gemini API error: {resp_data['error'].get('message', str(resp_data['error']))}",
                    "steps": steps_log
                }

            candidates = resp_data.get("candidates", [])
            if not candidates:
                break

            candidate = candidates[0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])

            # Add model response to history
            messages.append({"role": "model", "parts": parts})

            function_calls = [p["functionCall"] for p in parts if "functionCall" in p]
            text_parts = [p["text"] for p in parts if "text" in p]

            if text_parts:
                final_text = "\n".join(text_parts)

            # If model didn't call any tools, it is finished!
            if not function_calls:
                break

            # Execute all requested function calls
            function_response_parts = []
            for fc in function_calls:
                fn_name = fc["name"]
                fn_args = fc.get("args", {})

                # Execute Ohmic micro-tool
                tool_result = execute_tool_call(fn_name, fn_args)

                # Log step for user UI
                steps_log.append({
                    "step": len(steps_log) + 1,
                    "tool": fn_name,
                    "args": fn_args,
                    "result": tool_result
                })

                function_response_parts.append({
                    "functionResponse": {
                        "name": fn_name,
                        "response": {"output": tool_result}
                    }
                })

            # Send tool responses back to Gemini
            messages.append({"role": "function", "parts": function_response_parts})

        # Check if preview SVG was generated
        preview_svg_path = "scratch/active_preview.svg"
        if os.path.exists(preview_svg_path):
            try:
                with open(preview_svg_path, "r", encoding="utf-8") as f:
                    svg_preview = f.read()
            except Exception:
                pass

        return {
            "status": "SUCCESS",
            "prompt": user_prompt,
            "explanation": final_text,
            "steps": steps_log,
            "summary": CTX.schematic.get_summary(),
            "svg_preview": svg_preview,
            "health": CTX.schematic.run_health_check()
        }

    def _call_gemini_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Executes direct REST POST request to Google Gemini API."""
        url = GEMINI_API_ENDPOINT.format(model=self.model, api_key=self.api_key)
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "OhmicAgent/1.0"
        }
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                return {"error": err_body}
            except Exception:
                return {"error": {"message": f"HTTP {e.code}: {e.reason}"}}
        except Exception as e:
            return {"error": {"message": str(e)}}
