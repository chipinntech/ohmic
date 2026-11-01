"""
Ohmic Web Platform API Server.
FastAPI server serving the interactive web interface and running autonomous Gemini schematic generation.
"""

import os
import sys
import asyncio
from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

# Ensure ohmic package is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from ohmic.agent import OhmicGeminiAgent
from ohmic.demo_circuits import build_demo_circuit
from ohmic.engine import OhmicSchematic
from ohmic.tools import CTX

app = FastAPI(title="Ohmic - Autonomous Hardware Engineering Platform", version="0.2.0")

# Enable high-performance GZip compression for multi-megabyte SVGs and netlists
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static and Frontend directories
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "frontend", "dist")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "web")
os.makedirs(STATIC_DIR, exist_ok=True)

if os.path.exists(FRONTEND_DIST):
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def find_scratch_file(filename: str) -> Optional[str]:
    """Finds generated scratch artifacts in either local or workspace directories."""
    paths_to_check = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scratch", filename)),
        os.path.abspath(os.path.join("scratch", filename)),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "scratch", filename))
    ]
    for p in paths_to_check:
        if os.path.isfile(p):
            return p
        if os.path.isdir(p):
            sub_file = os.path.join(p, filename)
            if os.path.isfile(sub_file):
                return sub_file
            for item in os.listdir(p):
                full_item = os.path.join(p, item)
                if os.path.isfile(full_item) and (item.endswith(".svg") or item.endswith(".kicad_sch") or item.endswith(".pdf")):
                    return full_item
    return None

class PromptRequest(BaseModel):
    prompt: str
    api_key: Optional[str] = None
    model: Optional[str] = "gemini-1.5-flash"

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    react_index = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.exists(react_index):
        with open(react_index, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Ohmic Web UI loading...</h1>")

@app.post("/api/generate")
async def generate_circuit(req: PromptRequest):
    """Executes the autonomous agent loop to design the requested schematic."""
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    api_key = (req.api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
    
    # If Gemini API key is present and not 'demo', run live LLM agent loop off-thread
    if api_key and api_key.lower() != "demo":
        agent = OhmicGeminiAgent(api_key=api_key, model=req.model or "gemini-1.5-flash")
        result = await asyncio.to_thread(agent.run_prompt, req.prompt)
        if result.get("status") == "ERROR":
            raise HTTPException(status_code=500, detail=result.get("message", "Agent error occurred."))
        return result

    # Otherwise, execute autonomous engine in Demo Mode off-thread
    demo_result = await asyncio.to_thread(build_demo_circuit, req.prompt)
    demo_result["mode"] = "demo"
    demo_result["note"] = (
        "Generated using Ohmic Autonomous Micro-Tools in Demo Mode. "
        "Enter your Google Gemini API key in settings to unlock unconstrained natural-language generation for any circuit."
    )
    return demo_result

@app.api_route("/api/preview/svg", methods=["GET", "HEAD"])
async def get_preview_svg():
    """Returns the vector SVG preview of the currently active canvas with compression."""
    svg_path = find_scratch_file("active_preview.svg")
    if svg_path and os.path.isfile(svg_path):
        mtime = os.path.getmtime(svg_path)
        etag = f'"{int(mtime)}-{os.path.getsize(svg_path)}"'
        return FileResponse(
            svg_path,
            media_type="image/svg+xml",
            headers={
                "Cache-Control": "no-cache, must-revalidate",
                "ETag": etag
            }
        )
    raise HTTPException(status_code=404, detail="No active SVG preview available yet.")

@app.get("/api/download/schematic")
async def download_schematic():
    """Downloads the generated KiCad .kicad_sch file."""
    sch_path = find_scratch_file("active_preview.kicad_sch")
    if sch_path and os.path.isfile(sch_path):
        name = CTX.schematic.name if hasattr(CTX, "schematic") and CTX.schematic.name else "circuit"
        return FileResponse(
            sch_path,
            filename=f"{name}.kicad_sch",
            media_type="application/octet-stream",
            headers={"Cache-Control": "no-cache, must-revalidate"}
        )
    raise HTTPException(status_code=404, detail="No active schematic available for download.")

@app.get("/api/download/pdf")
async def download_pdf():
    """Compiles and downloads the vector PDF version."""
    sch_path = find_scratch_file("active_preview.kicad_sch")
    pdf_path = find_scratch_file("active_preview.pdf")
    if sch_path and os.path.isfile(sch_path):
        await asyncio.to_thread(CTX.exporter.export_pdf, sch_path, pdf_path)
        if os.path.isfile(pdf_path):
            name = CTX.schematic.name if hasattr(CTX, "schematic") and CTX.schematic.name else "circuit"
            return FileResponse(
                pdf_path,
                filename=f"{name}.pdf",
                media_type="application/pdf"
            )
    raise HTTPException(status_code=404, detail="No active PDF available for download.")

@app.post("/api/import")
async def import_schematic(file: UploadFile = File(...)):
    """Uploads an existing .kicad_sch file into the active canvas."""
    if not file.filename.endswith(".kicad_sch"):
        raise HTTPException(status_code=400, detail="Only .kicad_sch files are supported.")

    content = await file.read()
    
    # Target scratch directories
    workspace_scratch = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scratch"))
    local_scratch = os.path.abspath(os.path.join(os.path.dirname(__file__), "scratch"))
    os.makedirs(workspace_scratch, exist_ok=True)
    os.makedirs(local_scratch, exist_ok=True)

    sch_path_ws = os.path.join(workspace_scratch, "active_preview.kicad_sch")
    sch_path_local = os.path.join(local_scratch, "active_preview.kicad_sch")
    svg_path_ws = os.path.join(workspace_scratch, "active_preview.svg")
    svg_path_local = os.path.join(local_scratch, "active_preview.svg")

    def _process_import():
        # Save to both paths for consistency
        for target_path in [sch_path_ws, sch_path_local]:
            with open(target_path, "wb") as f:
                f.write(content)

        # Load into active schematic engine
        base_name = os.path.splitext(file.filename)[0]
        try:
            CTX.schematic = OhmicSchematic.load(sch_path_ws)
            CTX.schematic.name = base_name
        except Exception as e:
            print(f"Warning: Loading into parser fallback: {e}")
            CTX.schematic.name = base_name

        # Export vector preview via headless kicad-cli
        try:
            CTX.exporter.export_svg(sch_path_ws, svg_path_ws)
            import shutil
            if os.path.isfile(svg_path_ws):
                shutil.copy(svg_path_ws, svg_path_local)
        except Exception as e:
            print(f"Warning exporting SVG on import: {e}")

        comp_count = len(CTX.schematic.components) if hasattr(CTX, "schematic") else 0
        wire_count = len(CTX.schematic.wires) if hasattr(CTX, "schematic") else 0
        return base_name, comp_count, wire_count

    base_name, comp_count, wire_count = await asyncio.to_thread(_process_import)

    return {
        "status": "SUCCESS",
        "name": base_name,
        "filename": file.filename,
        "component_count": comp_count,
        "wire_count": wire_count,
        "message": f"Successfully loaded '{file.filename}' with {comp_count} components and {wire_count} nets."
    }

@app.get("/api/status")
async def get_active_status():
    """Returns the metadata of the currently active schematic and preview."""
    sch_path = find_scratch_file("active_preview.kicad_sch")
    svg_path = find_scratch_file("active_preview.svg")
    comp_count = len(CTX.schematic.components) if hasattr(CTX, "schematic") else 0
    wire_count = len(CTX.schematic.wires) if hasattr(CTX, "schematic") else 0
    name = CTX.schematic.name if hasattr(CTX, "schematic") and CTX.schematic.name else "ActiveProject"
    
    return {
        "name": name,
        "has_schematic": sch_path is not None and os.path.isfile(sch_path),
        "has_svg": svg_path is not None and os.path.isfile(svg_path),
        "component_count": comp_count,
        "wire_count": wire_count
    }

if __name__ == "__main__":
    import uvicorn
    print("Starting Ohmic Web Platform at http://127.0.0.1:8000 ...")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
