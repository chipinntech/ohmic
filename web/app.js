/* -------------------------------------------------------------
   Ohmic Web Platform Client Logic
   Manages API calls, Gemini agent tool feed, and SVG canvas zoom/pan
   ------------------------------------------------------------- */

document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const promptInput = document.getElementById("prompt-input");
    const generatorForm = document.getElementById("generator-form");
    const generateBtn = document.getElementById("generate-btn");
    const sampleChips = document.querySelectorAll(".sample-chip");
    
    // API Key Elements
    const apiKeyToggleBtn = document.getElementById("api-key-toggle-btn");
    const apiCard = document.getElementById("api-card");
    const closeApiCard = document.getElementById("close-api-card");
    const geminiKeyInput = document.getElementById("gemini-key-input");
    const saveKeyBtn = document.getElementById("save-key-btn");
    
    // Feed & Status
    const agentStatus = document.getElementById("agent-status");
    const feedLog = document.getElementById("feed-log");
    
    // Canvas & Toolbar Elements
    const schematicTitle = document.getElementById("schematic-title");
    const drcBadge = document.getElementById("drc-badge");
    const statParts = document.getElementById("stat-parts");
    const statWires = document.getElementById("stat-wires");
    const statNets = document.getElementById("stat-nets");
    const emptyState = document.getElementById("empty-state");
    const svgRenderArea = document.getElementById("svg-render-area");
    const canvasViewport = document.getElementById("canvas-viewport");
    const canvasWrapper = document.getElementById("canvas-wrapper");
    
    // Zoom Controls
    const zoomInBtn = document.getElementById("zoom-in");
    const zoomOutBtn = document.getElementById("zoom-out");
    const zoomResetBtn = document.getElementById("zoom-reset");

    // State
    let currentZoom = 1.0;
    let isPanning = false;
    let startX = 0;
    let startY = 0;
    let translateX = 0;
    let translateY = 0;

    // Load saved API Key from localStorage
    const savedKey = localStorage.getItem("ohmic_gemini_key") || "";
    if (savedKey) {
        geminiKeyInput.value = savedKey;
    }

    // Toggle API Key settings card
    apiKeyToggleBtn.addEventListener("click", () => {
        apiCard.classList.toggle("hidden");
    });

    closeApiCard.addEventListener("click", () => {
        apiCard.classList.add("hidden");
    });

    saveKeyBtn.addEventListener("click", () => {
        const key = geminiKeyInput.value.trim();
        localStorage.setItem("ohmic_gemini_key", key);
        apiCard.classList.add("hidden");
        addLogMessage("API Key saved securely in browser storage.");
    });

    // Sample Prompt Chips
    sampleChips.forEach(chip => {
        chip.addEventListener("click", () => {
            promptInput.value = chip.getAttribute("data-prompt");
            promptInput.focus();
        });
    });

    // Form Submission
    generatorForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const prompt = promptInput.value.trim();
        if (!prompt) return;

        const apiKey = localStorage.getItem("ohmic_gemini_key") || geminiKeyInput.value.trim();

        // Set Loading State
        generateBtn.disabled = true;
        agentStatus.textContent = apiKey ? "Gemini Agent Designing..." : "Ohmic Autonomous Engine Running...";
        agentStatus.className = "status-indicator running";
        feedLog.innerHTML = "";
        addLogMessage(`Specification Received: "${prompt}"`);
        if (!apiKey) {
            addLogMessage("Note: No Gemini API Key provided. Running in Demo Mode with Ohmic Autonomous Micro-Tools.");
            addLogMessage("To unlock unconstrained AI generation from any custom prompt, add your API key in settings.");
        } else {
            addLogMessage("Engaging Gemini Function Calling with 19 Ohmic micro-tools...");
        }

        try {
            const response = await fetch("/api/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    prompt: prompt,
                    api_key: apiKey,
                    model: "gemini-1.5-flash"
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "Generation failed.");
            }

            // Render execution steps in feed
            if (data.steps && data.steps.length > 0) {
                data.steps.forEach(step => {
                    renderStep(step);
                });
            }

            // Final explanation
            if (data.explanation) {
                addLogMessage(`[Ohmic]: ${data.explanation}`);
            }

            // Update stats
            if (data.summary) {
                statParts.textContent = data.summary.components || 0;
                statWires.textContent = data.summary.wires || 0;
                statNets.textContent = data.summary.distinct_nets || 0;
            }

            // Update DRC badge
            if (data.health) {
                drcBadge.classList.remove("hidden");
                if (data.health.status === "PASS") {
                    drcBadge.textContent = "DRC: PASS (0 Errors)";
                    drcBadge.className = "drc-badge pass";
                } else {
                    drcBadge.textContent = "DRC: WARNINGS";
                    drcBadge.className = "drc-badge warning";
                }
            }

            // Render SVG preview
            if (data.svg_preview) {
                renderSvg(data.svg_preview);
            } else {
                // Fetch preview SVG endpoint
                fetchSvgPreview();
            }

            schematicTitle.textContent = "Generated Schematic";
            agentStatus.textContent = "Completed";
            agentStatus.className = "status-indicator";

        } catch (err) {
            addLogMessage(`ERROR: ${err.message}`, true);
            agentStatus.textContent = "Failed";
            agentStatus.className = "status-indicator";
        } finally {
            generateBtn.disabled = false;
        }
    });

    async function fetchSvgPreview() {
        try {
            const resp = await fetch("/api/preview/svg");
            if (resp.ok) {
                const svgText = await resp.text();
                renderSvg(svgText);
            }
        } catch (e) {}
    }

    function renderSvg(svgString) {
        emptyState.classList.add("hidden");
        svgRenderArea.classList.remove("hidden");
        svgRenderArea.innerHTML = svgString;
        resetZoom();
    }

    function renderStep(step) {
        const stepDiv = document.createElement("div");
        stepDiv.className = "feed-step";

        const toolName = document.createElement("div");
        toolName.className = "step-tool";
        toolName.textContent = `[Step ${step.step}] ${step.tool}`;

        const details = document.createElement("div");
        details.className = "step-details";
        
        let argsSummary = JSON.stringify(step.args || {});
        let resultSummary = JSON.stringify(step.result || {});
        details.textContent = `Args: ${argsSummary.substring(0, 80)} -> Result: ${resultSummary.substring(0, 100)}`;

        stepDiv.appendChild(toolName);
        stepDiv.appendChild(details);
        feedLog.appendChild(stepDiv);
        feedLog.scrollTop = feedLog.scrollHeight;
    }

    function addLogMessage(msg, isError = false) {
        const line = document.createElement("div");
        line.style.color = isError ? "var(--rose-error)" : "var(--cyan-glow)";
        line.textContent = `> ${msg}`;
        feedLog.appendChild(line);
        feedLog.scrollTop = feedLog.scrollHeight;
    }

    // --- Canvas Zoom & Pan Logic ---
    function updateTransform() {
        canvasWrapper.style.transform = `translate(${translateX}px, ${translateY}px) scale(${currentZoom})`;
    }

    function resetZoom() {
        currentZoom = 1.0;
        translateX = 0;
        translateY = 0;
        updateTransform();
    }

    zoomInBtn.addEventListener("click", () => {
        currentZoom = Math.min(currentZoom * 1.25, 4.0);
        updateTransform();
    });

    zoomOutBtn.addEventListener("click", () => {
        currentZoom = Math.max(currentZoom * 0.8, 0.25);
        updateTransform();
    });

    zoomResetBtn.addEventListener("click", resetZoom);

    // Mouse Wheel Zoom
    canvasViewport.addEventListener("wheel", (e) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        currentZoom = Math.min(Math.max(currentZoom * delta, 0.25), 4.0);
        updateTransform();
    }, { passive: false });

    // Drag Pan
    canvasViewport.addEventListener("mousedown", (e) => {
        if (e.target.closest(".toolbar-actions")) return;
        isPanning = true;
        startX = e.clientX - translateX;
        startY = e.clientY - translateY;
    });

    window.addEventListener("mousemove", (e) => {
        if (!isPanning) return;
        translateX = e.clientX - startX;
        translateY = e.clientY - startY;
        updateTransform();
    });

    window.addEventListener("mouseup", () => {
        isPanning = false;
    });
});
