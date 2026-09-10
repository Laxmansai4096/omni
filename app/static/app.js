let currentDocumentData = null;
let currentPageIndex = 0;
let currentFilter = 'all';
let zoomScale = 1.0;
let userZoomLocked = false;
let activeElementId = null;
let pendingSelectedFile = null;
let currentTargetLanguage = 'none';
let elementTranslationsCache = {};

// Interactive Pan Mode State
let isPanToolActive = false;
let isMouseDownPan = false;
let panStartX = 0, panStartY = 0;
let panStartScrollLeft = 0, panStartScrollTop = 0;

// Initialize Studio on DOM Load
document.addEventListener("DOMContentLoaded", () => {
    loadSampleDocument("sample-expense-001");
    loadHistoryDropdown();

    window.addEventListener("resize", () => {
        if (!userZoomLocked && zoomScale <= 1.0) fitImageToViewport(false);
    });

    // Keyboard Shortcuts (ESC to close modal or exit pan/fullscreen)
    window.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            const pane = document.getElementById("canvasViewport");
            if (pane && pane.classList.contains("fullscreen-pane")) {
                toggleFullscreenCanvas();
            } else if (activeElementId !== null) {
                selectElement(null);
            }
        }
    });

    const wrapper = document.getElementById("canvasWrapper");
    if (wrapper) {
        // Native Mouse Drag-to-Pan on Canvas Viewport
        wrapper.addEventListener("mousedown", (e) => {
            // Initiate drag-to-pan if clicking on wrapper, stage, or canvas background (not on interactive svg polygons)
            if (e.target.tagName === 'CANVAS' || e.target.classList.contains('canvas-wrapper') || e.target.classList.contains('image-stage-container')) {
                isMouseDownPan = true;
                panStartX = e.clientX;
                panStartY = e.clientY;
                panStartScrollLeft = wrapper.scrollLeft;
                panStartScrollTop = wrapper.scrollTop;
                wrapper.style.cursor = "grabbing";
            }
        });

        window.addEventListener("mousemove", (e) => {
            if (isMouseDownPan && wrapper) {
                const dx = e.clientX - panStartX;
                const dy = e.clientY - panStartY;
                wrapper.scrollLeft = panStartScrollLeft - dx;
                wrapper.scrollTop = panStartScrollTop - dy;
            }
        });

        window.addEventListener("mouseup", () => {
            isMouseDownPan = false;
            if (wrapper) wrapper.style.cursor = "";
        });

        // Direct Smooth Mouse Wheel Pointer-Centered Zooming
        wrapper.addEventListener("wheel", (e) => {
            e.preventDefault();
            userZoomLocked = true;
            const delta = e.deltaY < 0 ? 0.06 : -0.06;
            zoomCanvas(delta, e.clientX, e.clientY);
        }, { passive: false });
    }
});

// Safe DOM text updater
function setElementText(id, text) {
    const el = document.getElementById(id);
    if (el) {
        el.innerText = text;
    }
}

// Load Document History from SQLite Database
async function loadHistoryDropdown() {
    try {
        const resp = await fetch("/api/v1/documents/history");
        if (!resp.ok) return;
        const history = await resp.json();
        
        const select = document.getElementById("historySelect");
        if (!select) return;
        
        select.innerHTML = '<option value="">-- Previously Processed Docs --</option>';
        history.forEach(item => {
            const opt = document.createElement("option");
            opt.value = item.document_id;
            opt.textContent = `${item.file_name} (${new Date(item.created_at * 1000).toLocaleDateString()})`;
            select.appendChild(opt);
        });
    } catch (e) {
        console.warn("Could not load document history:", e);
    }
}

// Load Document from API / DB
async function loadSampleDocument(docId) {
    if (!docId) return;
    try {
        const response = await fetch(`/api/v1/documents/${docId}`);
        if (!response.ok) throw new Error("Failed to load document");
        currentDocumentData = await response.json();
        currentPageIndex = 0;
        activeElementId = null;
        setElementText("currentFileName", currentDocumentData.file_name || currentDocumentData.filename || docId);
        userZoomLocked = false;
        renderDocumentState();
        setTimeout(() => fitImageToViewport(true), 100);
    } catch (err) {
        console.error("Error loading document:", err);
    }
}

// Handle File Selection (Staging File for Processing)
function handleFileSelected(file) {
    if (!file) return;
    pendingSelectedFile = file;

    const card = document.getElementById("fileStatusCard");
    if (card) card.style.display = "block";

    setElementText("selectedFileName", file.name);
    setElementText("selectedFileSize", `${(file.size / 1024).toFixed(1)} KB`);

    const btn = document.getElementById("processBtn");
    if (btn) {
        btn.disabled = false;
        btn.innerHTML = `<i class="fa-solid fa-bolt"></i> PROCESS IMAGE (${file.name.slice(0, 14)}...)`;
    }
}

// Clear Selected File
function clearSelectedFile() {
    pendingSelectedFile = null;
    const fileInput = document.getElementById("fileInput");
    if (fileInput) fileInput.value = "";

    const card = document.getElementById("fileStatusCard");
    if (card) card.style.display = "none";

    const btn = document.getElementById("processBtn");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-bolt"></i> PROCESS IMAGE`;
    }
}

let currentIngestionMode = 'sync';
let activeEventSource = null;

// Switch between Direct Interactive (Sync) and Enterprise Service Bus (Async)
function setIngestionMode(mode) {
    currentIngestionMode = mode;
    const syncBtn = document.getElementById("modeSyncBtn");
    const asyncBtn = document.getElementById("modeAsyncBtn");
    const hint = document.getElementById("modeHintText");

    if (syncBtn) syncBtn.classList.toggle("active", mode === 'sync');
    if (asyncBtn) asyncBtn.classList.toggle("active", mode === 'async');

    if (hint) {
        if (mode === 'sync') {
            hint.textContent = "Direct mode: Instant interactive analysis for single pages";
        } else {
            hint.textContent = "Azure Service Bus mode: Decoupled queue, Blob persistence & KEDA autoscaling";
        }
    }
}

// Start Processing Selected Image (Direct Sync or Enterprise Async Service Bus)
async function startProcessing() {
    if (!pendingSelectedFile) {
        alert("Please select or drop an image file first.");
        return;
    }

    if (currentIngestionMode === 'async') {
        startAsyncServiceBusPipeline(pendingSelectedFile);
        return;
    }

    // DIRECT INTERACTIVE (SYNC) MODE
    const btn = document.getElementById("processBtn");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> ANALYZING WITH AZURE AI...`;
    }

    const formData = new FormData();
    formData.append("file", pendingSelectedFile);

    try {
        const resp = await fetch("/api/v1/documents/upload", {
            method: "POST",
            body: formData
        });

        if (!resp.ok) {
            const errData = await resp.json().catch(() => ({}));
            throw new Error(errData.detail || "Image processing failed");
        }

        currentDocumentData = await resp.json();
        currentPageIndex = 0;
        activeElementId = null;
        setElementText("currentFileName", currentDocumentData.file_name || pendingSelectedFile.name);
        userZoomLocked = false;
        renderDocumentState();
        setTimeout(() => fitImageToViewport(true), 100);
        loadHistoryDropdown();

        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-check"></i> PROCESSED & SAVED TO DB!`;
            setTimeout(() => {
                btn.innerHTML = `<i class="fa-solid fa-bolt"></i> PROCESS IMAGE`;
            }, 2500);
        }
    } catch (e) {
        alert(`Processing Error: ${e.message}`);
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-bolt"></i> RETRY PROCESS IMAGE`;
        }
    }
}

// ENTERPRISE ASYNCHRONOUS AZURE SERVICE BUS PIPELINE (SSE STREAMING)
async function startAsyncServiceBusPipeline(file) {
    const btn = document.getElementById("processBtn");
    const banner = document.getElementById("asyncProgressBanner");
    const bar = document.getElementById("asyncProgressBar");
    const label = document.getElementById("asyncStageLabel");
    const badge = document.getElementById("asyncJobBadge");

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-satellite-dish fa-spin"></i> ENQUEUEING IN SERVICE BUS...`;
    }

    if (banner) banner.style.display = "block";
    if (bar) bar.style.width = "10%";
    if (label) label.textContent = "Uploading to Azure Blob & Service Bus...";
    resetStageStepper();
    setStageActive("step-queued");

    const formData = new FormData();
    formData.append("file", file);

    try {
        const resp = await fetch("/api/v1/jobs/submit", {
            method: "POST",
            body: formData
        });

        if (!resp.ok) {
            const errData = await resp.json().catch(() => ({}));
            throw new Error(errData.detail || "Async job submission failed");
        }

        const jobInfo = await resp.json();
        const jobId = jobInfo.job_id;
        if (badge) badge.textContent = jobId;
        if (label) label.textContent = `Job Enqueued in 'ai-jobs-queue'`;

        // Connect SSE for real-time progress stream
        if (activeEventSource) activeEventSource.close();
        activeEventSource = new EventSource(`/api/v1/jobs/${jobId}/stream`);

        activeEventSource.onmessage = (event) => {
            try {
                const job = JSON.parse(event.data);
                updateAsyncProgressUI(job);

                if (job.status === "COMPLETED") {
                    activeEventSource.close();
                    if (btn) {
                        btn.disabled = false;
                        btn.innerHTML = `<i class="fa-solid fa-check-double"></i> ASYNC JOB COMPLETED!`;
                        setTimeout(() => {
                            btn.innerHTML = `<i class="fa-solid fa-bolt"></i> PROCESS IMAGE`;
                        }, 3000);
                    }
                    // Load completed document directly
                    loadSampleDocument(job.job_id);
                    loadHistoryDropdown();
                } else if (job.status === "FAILED") {
                    activeEventSource.close();
                    if (label) label.textContent = `Processing Failed: ${job.error_message || 'Unknown'}`;
                    if (btn) {
                        btn.disabled = false;
                        btn.innerHTML = `<i class="fa-solid fa-bolt"></i> RETRY ASYNC JOB`;
                    }
                }
            } catch (err) {
                console.warn("SSE parse error:", err);
            }
        };

        activeEventSource.onerror = () => {
            if (activeEventSource) activeEventSource.close();
        };

    } catch (e) {
        alert(`Service Bus Error: ${e.message}`);
        if (banner) banner.style.display = "none";
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-bolt"></i> PROCESS IMAGE`;
        }
    }
}

function updateAsyncProgressUI(job) {
    const bar = document.getElementById("asyncProgressBar");
    const label = document.getElementById("asyncStageLabel");
    if (bar && job.progress_pct) bar.style.width = `${job.progress_pct}%`;

    const stage = job.current_stage || "";
    if (label) {
        const humanStage = stage.replace(/_/g, " ").toLowerCase();
        label.textContent = `Worker: ${humanStage} (${job.progress_pct || 0}%)`;
    }

    if (stage.includes("QUEUED")) {
        setStageActive("step-queued");
    } else if (stage.includes("BLOB") || stage.includes("FETCHING")) {
        setStageCompleted("step-queued");
        setStageActive("step-storage");
    } else if (stage.includes("DOCUMENT_INTELLIGENCE") || stage.includes("OCR")) {
        setStageCompleted("step-queued");
        setStageCompleted("step-storage");
        setStageActive("step-ocr");
    } else if (stage.includes("OPENAI") || stage.includes("VISION")) {
        setStageCompleted("step-queued");
        setStageCompleted("step-storage");
        setStageCompleted("step-ocr");
        setStageActive("step-vision");
    } else if (job.status === "COMPLETED") {
        setStageCompleted("step-queued");
        setStageCompleted("step-storage");
        setStageCompleted("step-ocr");
        setStageCompleted("step-vision");
        setStageCompleted("step-done");
    }
}

function resetStageStepper() {
    ["step-queued", "step-storage", "step-ocr", "step-vision", "step-done"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.className = "stage-step";
    });
}

function setStageActive(id) {
    const el = document.getElementById(id);
    if (el) el.className = "stage-step active";
}

function setStageCompleted(id) {
    const el = document.getElementById(id);
    if (el) el.className = "stage-step completed";
}

// Process Document from URL
async function submitUrlDocument() {
    const urlInput = document.getElementById("urlInput");
    if (!urlInput) return;
    const url = urlInput.value.trim();
    if (!url) return;

    const formData = new FormData();
    formData.append("url", url);

    try {
        const resp = await fetch("/api/v1/documents/url", {
            method: "POST",
            body: formData
        });
        if (!resp.ok) {
            const errData = await resp.json().catch(() => ({}));
            throw new Error(errData.detail || "Failed to process document URL");
        }
        currentDocumentData = await resp.json();
        currentPageIndex = 0;
        activeElementId = null;
        setElementText("currentFileName", currentDocumentData.file_name || "remote_image.png");
        userZoomLocked = false;
        renderDocumentState();
        setTimeout(() => fitImageToViewport(true), 100);
        loadHistoryDropdown();
    } catch (e) {
        alert(`URL Processing Error: ${e.message}`);
    }
}

// Viewport Zoom & Scaling Suite (Fit Page, Fit Width, Zoom In/Out, Presets)
function applyZoomScale(focalX = null, focalY = null) {
    const stage = document.getElementById("imageStageContainer");
    if (!stage || !currentDocumentData || !currentDocumentData.pages) return;

    const page = currentDocumentData.pages[currentPageIndex];
    if (!page) return;

    const pageW = page.width || 1000;
    const pageH = page.height || 1300;

    const scaledW = Math.round(pageW * zoomScale);
    const scaledH = Math.round(pageH * zoomScale);

    stage.style.width = `${scaledW}px`;
    stage.style.height = `${scaledH}px`;

    const badge = document.getElementById("zoomLevelBadge");
    if (badge) {
        badge.innerText = `${Math.round(zoomScale * 100)}%`;
    }
}

function zoomCanvas(delta, mouseX = null, mouseY = null) {
    userZoomLocked = true;
    const oldScale = zoomScale;
    const wrapper = document.getElementById("canvasWrapper");

    let maxAllowedScale = 1.50;
    if (wrapper && currentDocumentData && currentDocumentData.pages) {
        const page = currentDocumentData.pages[currentPageIndex];
        if (page && page.width) {
            const fitW = (wrapper.clientWidth - 48) / page.width;
            maxAllowedScale = Math.max(fitW * 1.35, 1.35);
        }
    }

    zoomScale = Math.min(Math.max(0.15, zoomScale + delta), maxAllowedScale);
    applyZoomScale();

    // Pointer-centered zooming: preserve cursor location
    if (mouseX !== null && mouseY !== null && wrapper) {
        const rect = wrapper.getBoundingClientRect();
        const relX = mouseX - rect.left + wrapper.scrollLeft;
        const relY = mouseY - rect.top + wrapper.scrollTop;
        const ratio = zoomScale / oldScale;
        wrapper.scrollLeft = relX * ratio - (mouseX - rect.left);
        wrapper.scrollTop = relY * ratio - (mouseY - rect.top);
    }
}

function fitImageToViewport(force = false) {
    if (userZoomLocked && !force) {
        applyZoomScale();
        return;
    }
    if (force) {
        userZoomLocked = false;
    }

    const wrapper = document.getElementById("canvasWrapper");
    if (!wrapper || !currentDocumentData || !currentDocumentData.pages) return;

    const page = currentDocumentData.pages[currentPageIndex];
    if (!page) return;

    const availW = wrapper.clientWidth;
    const availH = wrapper.clientHeight;
    const pageW = page.width || 1000;
    const pageH = page.height || 1300;

    if (availW > 0 && availH > 0 && pageW > 0 && pageH > 0) {
        const scaleX = availW / pageW;
        const scaleY = availH / pageH;
        // Exact fit: scale such that at least 2 borders (vertical or horizontal or both) touch the edges of the zoom workspace
        zoomScale = Math.min(scaleX, scaleY);
        applyZoomScale();
        wrapper.scrollLeft = 0;
        wrapper.scrollTop = 0;
    }
}

function fitWidthToViewport() {
    userZoomLocked = true;
    const wrapper = document.getElementById("canvasWrapper");
    if (!wrapper || !currentDocumentData || !currentDocumentData.pages) return;

    const page = currentDocumentData.pages[currentPageIndex];
    if (!page) return;

    const availW = wrapper.clientWidth;
    const pageW = page.width || 1000;

    if (availW > 0 && pageW > 0) {
        zoomScale = availW / pageW;
        applyZoomScale();
    }
}

function handleZoomPresetChange(val) {
    if (val === "fit") {
        fitImageToViewport(true);
    } else if (val === "fit-width") {
        fitWidthToViewport();
    } else {
        userZoomLocked = true;
        zoomScale = parseFloat(val);
        applyZoomScale();
    }
}

function togglePanTool() {
    isPanToolActive = !isPanToolActive;
    const btn = document.getElementById("panToolBtn");
    const wrapper = document.getElementById("canvasWrapper");
    if (btn) {
        btn.classList.toggle("btn-secondary", !isPanToolActive);
        btn.classList.toggle("active", isPanToolActive);
        if (isPanToolActive) {
            btn.style.background = "#2563eb";
            btn.style.color = "#ffffff";
        } else {
            btn.style.background = "#334155";
            btn.style.color = "";
        }
    }
    if (wrapper) {
        wrapper.classList.toggle("pan-mode", isPanToolActive);
    }
}

function toggleFullscreenCanvas() {
    const pane = document.getElementById("canvasViewport");
    if (!pane) return;
    pane.classList.toggle("fullscreen-pane");
    setTimeout(() => fitImageToViewport(true), 150);
}

function resetZoom() {
    userZoomLocked = true;
    zoomScale = 1.0;
    applyZoomScale();
}

// Main Render Function
function renderDocumentState() {
    if (!currentDocumentData || !currentDocumentData.pages) return;

    const page = currentDocumentData.pages[currentPageIndex];
    setElementText("pageIndicator", `Page ${page.page_number} of ${currentDocumentData.pages.length}`);

    // Update Counts & Pills
    updateFilterCounts();

    // Render Canvas & SVG Overlay below
    renderCanvasPage(page);

    // Render Right-Pane Extracted Inspector List
    renderExtractedElementsList();

    // Render AI Observability Telemetry Panel
    renderAIObservabilityPanel();

    // Update JSON Viewer Tab
    setElementText("jsonViewer", JSON.stringify(currentDocumentData, null, 2));
}

// Render Document Canvas & Highlight Selected Requirement without Cluttered Text Tags
function renderCanvasPage(page) {
    const canvas = document.getElementById("documentCanvas");
    const ctx = canvas.getContext("2d");
    const overlay = document.getElementById("boundingOverlay");
    
    // Page Dimensions
    const width = page.width || 1000;
    const height = page.height || 1300;
    
    canvas.width = width;
    canvas.height = height;

    // Draw Document Canvas Background or Base64 Image
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, width, height);

    if (page.image_url) {
        const bgImg = new Image();
        bgImg.onload = function() {
            ctx.drawImage(bgImg, 0, 0, width, height);
            requestAnimationFrame(() => applyZoomScale());
        };
        bgImg.src = page.image_url;
    } else {
        ctx.strokeStyle = "#e2e8f0";
        ctx.lineWidth = 1;
        for (let y = 40; y < height; y += 30) {
            ctx.beginPath();
            ctx.moveTo(30, y);
            ctx.lineTo(width - 30, y);
            ctx.stroke();
        }
        ctx.fillStyle = "#94a3b8";
        ctx.font = "bold 20px Inter, sans-serif";
        ctx.fillText(`OMNIDOC AI ANALYZED DOCUMENT - PAGE ${page.page_number}`, 40, 50);
        requestAnimationFrame(() => applyZoomScale());
    }

    const pageElements = page.elements || [];

    // Clear SVG overlay
    overlay.setAttribute("viewBox", `0 0 ${width} ${height}`);
    overlay.innerHTML = "";

    // Reverse Reference Highlighting Logic:
    // If activeElementId is selected, ONLY that element is active while others dim!
    pageElements.forEach(elem => {
        const isMatchingCategory = (currentFilter === 'all' || elem.category === currentFilter);
        const isActive = (activeElementId === elem.id);

        // If an individual item is selected (activeElementId != null), dim everything else!
        let isDimmed = !isMatchingCategory;
        if (activeElementId !== null) {
            isDimmed = !isActive;
        }
        
        const gSvg = document.createElementNS("http://www.w3.org/2000/svg", "g");
        gSvg.setAttribute("class", `polygon-group ${isDimmed ? 'dimmed-cat' : 'visible-cat'}`);
        gSvg.setAttribute("data-id", elem.id);
        gSvg.setAttribute("data-category", elem.category);

        let pointsStr = "";
        let minX = width, minY = height;
        if (elem.bounding_box && elem.bounding_box.polygon && elem.bounding_box.polygon.length >= 8) {
            const p = elem.bounding_box.polygon;
            pointsStr = `${p[0]*width},${p[1]*height} ${p[2]*width},${p[3]*height} ${p[4]*width},${p[5]*height} ${p[6]*width},${p[7]*height}`;
            minX = Math.min(p[0]*width, p[2]*width, p[4]*width, p[6]*width);
            minY = Math.min(p[1]*height, p[3]*height, p[5]*height, p[7]*height);
        } else {
            const bbox = elem.bounding_box;
            const x1 = bbox.x * width;
            const y1 = bbox.y * height;
            const w = bbox.width * width;
            const h = bbox.height * height;
            pointsStr = `${x1},${y1} ${x1+w},${y1} ${x1+w},${y1+h} ${x1},${y1+h}`;
            minX = x1;
            minY = y1;
        }

        gSvg.setAttribute("data-minx", minX);
        gSvg.setAttribute("data-miny", minY);
        gSvg.setAttribute("data-label", elem.label || elem.category.toUpperCase());

        const polySvg = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
        polySvg.setAttribute("points", pointsStr);
        polySvg.setAttribute("class", `bounding-polygon poly-${elem.category} ${isActive ? 'active-target' : ''} ${isDimmed ? 'dimmed' : 'highlighted-cat'}`);
        polySvg.setAttribute("data-id", elem.id);

        if (isActive) {
            const textSvg = document.createElementNS("http://www.w3.org/2000/svg", "text");
            textSvg.setAttribute("x", Math.max(10, minX + 4));
            textSvg.setAttribute("y", Math.max(24, minY - 6));
            textSvg.setAttribute("class", "active-focus-tag");
            textSvg.textContent = `▶ SELECTED: ${elem.label || elem.category.toUpperCase()}`;
            gSvg.appendChild(textSvg);
        }

        polySvg.addEventListener("click", () => selectElement(elem.id));
        gSvg.appendChild(polySvg);
        overlay.appendChild(gSvg);
    });
}

// Lightweight SVG overlay updater: Changes highlights instantly WITHOUT redrawing canvas or resetting zoom!
function updateSvgOverlayHighlights() {
    const overlay = document.getElementById("boundingOverlay");
    if (!overlay) return;

    const groups = overlay.querySelectorAll(".polygon-group");
    groups.forEach(g => {
        const elemId = g.getAttribute("data-id");
        const category = g.getAttribute("data-category");
        const isMatchCat = (currentFilter === 'all' || category === currentFilter);
        const isActive = (activeElementId === elemId);

        let isDimmed = !isMatchCat;
        if (activeElementId !== null) {
            isDimmed = !isActive;
        }

        g.setAttribute("class", `polygon-group ${isDimmed ? 'dimmed-cat' : 'visible-cat'}`);

        const poly = g.querySelector(".bounding-polygon");
        if (poly) {
            poly.setAttribute("class", `bounding-polygon poly-${category} ${isActive ? 'active-target' : ''} ${isDimmed ? 'dimmed' : 'highlighted-cat'}`);
        }

        let tag = g.querySelector(".active-focus-tag");
        if (isActive) {
            const page = currentDocumentData ? currentDocumentData.pages[currentPageIndex] : null;
            const elemObj = page ? (page.elements || []).find(e => e.id === elemId) : null;
            let tagLabel = elemObj ? (elemObj.text_content || elemObj.label) : (g.getAttribute("data-label") || category.toUpperCase());

            if (currentTargetLanguage !== 'none') {
                const cacheKey = `${elemId}_${currentTargetLanguage}`;
                if (elementTranslationsCache[cacheKey]) {
                    const trans = elementTranslationsCache[cacheKey];
                    tagLabel = `[${trans.target_language_name}] ${trans.translated_text}`;
                }
            }

            const formattedTag = `▶ ${tagLabel.slice(0, 45)}${tagLabel.length > 45 ? '...' : ''}`;

            if (tag) {
                tag.textContent = formattedTag;
            } else {
                const textSvg = document.createElementNS("http://www.w3.org/2000/svg", "text");
                const minX = parseFloat(g.getAttribute("data-minx") || "10");
                const minY = parseFloat(g.getAttribute("data-miny") || "30");
                textSvg.setAttribute("x", Math.max(10, minX + 4));
                textSvg.setAttribute("y", Math.max(24, minY - 6));
                textSvg.setAttribute("class", "active-focus-tag");
                textSvg.textContent = formattedTag;
                g.appendChild(textSvg);
            }
        } else if (tag) {
            tag.remove();
        }
    });
}

// Toggle Inline Edit Panel for an Element Card
function toggleEditElement(elemId, event) {
    if (event) event.stopPropagation();
    const panel = document.getElementById(`edit-panel-${elemId}`);
    if (panel) {
        const isHidden = panel.style.display === "none" || !panel.style.display;
        panel.style.display = isHidden ? "block" : "none";
        if (isHidden) {
            const input = document.getElementById(`edit-text-${elemId}`);
            if (input) input.focus();
        }
    }
}

// Save Edited Element Text Content, Re-trigger Azure Translation & Reflect on Image Canvas
async function saveElementText(elemId, event) {
    if (event) event.stopPropagation();
    const input = document.getElementById(`edit-text-${elemId}`);
    if (!input) return;

    const newText = input.value.trim();
    if (!newText) {
        alert("Text content cannot be empty.");
        return;
    }

    if (!currentDocumentData || !currentDocumentData.pages) return;
    const page = currentDocumentData.pages[currentPageIndex];
    if (!page || !page.elements) return;

    const elem = page.elements.find(e => e.id === elemId);
    if (!elem) return;

    const payload = { text_content: newText };

    // Structured data updating per category
    if (elem.category === 'table') {
        if (!elem.table_data) {
            elem.table_data = { markdown_table: newText, csv_content: newText, row_count: 0, column_count: 0, cells: [] };
        } else {
            elem.table_data.markdown_table = newText;
        }
        elem.text_content = newText;
        payload.table_data = { markdown_table: newText };
    } else if (elem.category === 'key_value') {
        const newKv = {};
        newText.split("\n").forEach(line => {
            const idx = line.indexOf(":");
            if (idx !== -1) {
                const k = line.slice(0, idx).trim();
                const v = line.slice(idx + 1).trim();
                if (k) newKv[k] = v;
            }
        });
        elem.key_value_pair = newKv;
        elem.text_content = newText;
        payload.key_value_pair = newKv;
    } else if (elem.category === 'chart' || elem.category === 'figure') {
        const lines = newText.split("\n");
        const title = lines[0] || "Chart Element";
        const note = lines.slice(1).join("\n");
        if (!elem.chart_summary) {
            elem.chart_summary = { title: title, note: note };
        } else {
            elem.chart_summary.title = title;
            elem.chart_summary.note = note;
        }
        elem.text_content = newText;
        payload.chart_summary = elem.chart_summary;
    } else {
        elem.text_content = newText;
    }

    // Hide edit panel
    const panel = document.getElementById(`edit-panel-${elemId}`);
    if (panel) panel.style.display = "none";

    // Update card body display text in DOM
    const displayContainer = document.getElementById(`card-text-display-${elemId}`);
    if (displayContainer) {
        if (elem.category === 'table' && elem.table_data) {
            displayContainer.innerHTML = formatMarkdownTableToHtml(elem.table_data.markdown_table);
        } else if (elem.category === 'key_value' && elem.key_value_pair) {
            displayContainer.innerHTML = `
                <div class="kv-grid" style="display:grid; grid-template-columns: 180px 1fr; gap: 8px; font-size:0.8rem;">
                    ${Object.entries(elem.key_value_pair).map(([k, v]) => `<div><strong style="color:#f97316;">${escapeHtml(k)}:</strong></div><div>${escapeHtml(v)}</div>`).join("")}
                </div>
            `;
        } else if ((elem.category === 'chart' || elem.category === 'figure') && elem.chart_summary) {
            const c = elem.chart_summary;
            displayContainer.innerHTML = `
                <div class="chart-box" style="font-size:0.8rem;">
                    <strong>Visual Region Title:</strong> ${escapeHtml(c.title || 'Chart Element')}<br>
                    <span style="color:var(--text-muted);">${escapeHtml(c.note || '')}</span>
                </div>
            `;
        } else {
            displayContainer.innerHTML = `<p style="font-size:0.85rem; color: var(--text-main); line-height:1.5;">${escapeHtml(newText)}</p>`;
        }
    }

    // Clear translation cache for all languages for this element
    ['hi', 'te', 'fr', 'de', 'kn'].forEach(lang => {
        delete elementTranslationsCache[`${elemId}_${lang}`];
    });

    // Re-fetch translation from Azure Translator API if target language is selected
    if (currentTargetLanguage !== 'none') {
        const transContainer = document.getElementById(`trans-container-${elemId}`);
        if (transContainer) {
            transContainer.innerHTML = `
                <div class="translated-card-section" style="border-left-color: #60a5fa;">
                    <div class="translated-card-header" style="color: #60a5fa;">
                        <span><i class="fa-solid fa-circle-notch fa-spin"></i> Re-translating updated data with Azure Translator...</span>
                    </div>
                </div>
            `;
        }
        await fetchElementTranslation(elem, currentTargetLanguage);
    }

    // Re-render SVG overlay highlights to reflect updated text on image canvas
    updateSvgOverlayHighlights();

    // Persist changes to backend SQLite DB & Cache
    const docId = currentDocumentData.document_id || "active-doc";
    try {
        await fetch(`/api/v1/documents/${docId}/elements/${elemId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
    } catch (err) {
        console.warn("Could not persist element edit to DB:", err);
    }
}

// Azure AI Translator Language Dropdown Handler
function handleLanguageChange(lang) {
    currentTargetLanguage = lang;
    renderExtractedElementsList();
    if (activeElementId !== null && lang !== 'none') {
        const page = currentDocumentData ? currentDocumentData.pages[currentPageIndex] : null;
        const elem = page ? (page.elements || []).find(e => e.id === activeElementId) : null;
        if (elem) {
            fetchElementTranslation(elem, currentTargetLanguage);
        }
    }
}

// Fetch Translation for an Extracted Element from Azure AI Translator API
async function fetchElementTranslation(elem, targetLang) {
    if (!elem || targetLang === 'none') return;
    const cacheKey = `${elem.id}_${targetLang}`;
    
    if (elementTranslationsCache[cacheKey]) {
        updateElementTranslationUI(elem.id, elementTranslationsCache[cacheKey]);
        return;
    }

    let textToTranslate = elem.text_content || "";
    if (elem.category === 'table' && elem.table_data && elem.table_data.markdown_table) {
        textToTranslate = elem.table_data.markdown_table;
    } else if (elem.category === 'key_value' && elem.key_value_pair) {
        textToTranslate = Object.entries(elem.key_value_pair).map(([k, v]) => `${k}: ${v}`).join("\n");
    } else if (elem.category === 'chart' || elem.category === 'figure') {
        if (elem.chart_summary) {
            textToTranslate = `${elem.chart_summary.title || ''}\n${elem.chart_summary.note || ''}`.trim() || textToTranslate;
        }
    }

    if (!textToTranslate.trim()) return;

    try {
        const resp = await fetch("/api/v1/translate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: textToTranslate, target_language: targetLang, source_language: "en" })
        });

        if (!resp.ok) {
            const errData = await resp.json().catch(() => ({}));
            throw new Error(errData.detail || "Translation request failed");
        }

        const result = await resp.json();
        elementTranslationsCache[cacheKey] = result;
        updateElementTranslationUI(elem.id, result);
    } catch (e) {
        console.error("Translation error:", e);
        const errResult = {
            translated_text: `Error translating: ${e.message}`,
            target_language_name: targetLang.toUpperCase(),
            is_fallback: true,
            status: "error"
        };
        updateElementTranslationUI(elem.id, errResult);
    }
}

// Dynamically Update Translation Container inside Element Card
function updateElementTranslationUI(elemId, transResult) {
    const container = document.getElementById(`trans-container-${elemId}`);
    if (!container) return;

    const isFallback = transResult.is_fallback;
    const langName = transResult.target_language_name || "Translated";

    container.innerHTML = `
        <div class="translated-card-section">
            <div class="translated-card-header">
                <span><i class="fa-solid fa-language"></i> Azure Translator (${langName})</span>
                <span class="translate-badge-chip">${isFallback ? '<i class="fa-solid fa-triangle-exclamation"></i> Fallback' : '<i class="fa-solid fa-bolt"></i> Live Azure AI'}</span>
            </div>
            <div class="translated-card-text">${escapeHtml(transResult.translated_text)}</div>
        </div>
    `;
}

// Render Extracted Elements on Bottom Inspector Panel with Reverse Reference Click Handlers
function renderExtractedElementsList() {
    const listContainer = document.getElementById("elementsList");
    if (!listContainer) return;
    listContainer.innerHTML = "";

    if (!currentDocumentData) return;

    const page = currentDocumentData.pages[currentPageIndex];
    const visibleElements = (page.elements || []).filter(e => currentFilter === 'all' || e.category === currentFilter);

    if (visibleElements.length === 0) {
        listContainer.innerHTML = `
            <div style="text-align: center; padding: 20px; color: var(--text-muted);">
                <i class="fa-solid fa-filter-circle-xmark" style="font-size: 1.5rem; margin-bottom: 6px;"></i>
                <p>No extracted elements match category '${currentFilter.toUpperCase()}' on this page.</p>
            </div>
        `;
        return;
    }

    visibleElements.forEach(elem => {
        const card = document.createElement("div");
        const isSelected = (activeElementId === elem.id);
        card.setAttribute("class", `element-card ${isSelected ? 'highlight-sync' : ''}`);
        card.setAttribute("id", `card-${elem.id}`);
        
        // Reverse Reference Selection: Click card to highlight ONLY this item on image!
        card.addEventListener("click", () => selectElement(elem.id));

        let detailsHtml = "";
        
        if (elem.category === 'table' && elem.table_data) {
            detailsHtml = formatMarkdownTableToHtml(elem.table_data.markdown_table);
        }
        else if (elem.category === 'key_value' && elem.key_value_pair) {
            detailsHtml = `
                <div class="kv-grid" style="display:grid; grid-template-columns: 180px 1fr; gap: 8px; font-size:0.8rem;">
                    ${Object.entries(elem.key_value_pair).map(([k, v]) => `<div><strong style="color:#f97316;">${escapeHtml(k)}:</strong></div><div>${escapeHtml(v)}</div>`).join("")}
                </div>
            `;
        }
        else if ((elem.category === 'chart' || elem.category === 'figure') && elem.chart_summary) {
            const c = elem.chart_summary;
            detailsHtml = `
                <div class="chart-box" style="font-size:0.8rem;">
                    <strong>Visual Region Title:</strong> ${escapeHtml(c.title || 'Chart Element')}<br>
                    <span style="color:var(--text-muted);">${escapeHtml(c.note || '')}</span>
                </div>
            `;
        }
        else {
            detailsHtml = `<p style="font-size:0.85rem; color: var(--text-main); line-height:1.5;">${escapeHtml(elem.text_content)}</p>`;
        }

        // Translation container placeholder
        let transHtml = "";
        if (currentTargetLanguage !== 'none') {
            const cacheKey = `${elem.id}_${currentTargetLanguage}`;
            if (elementTranslationsCache[cacheKey]) {
                const res = elementTranslationsCache[cacheKey];
                transHtml = `
                    <div class="trans-container" id="trans-container-${elem.id}">
                        <div class="translated-card-section">
                            <div class="translated-card-header">
                                <span><i class="fa-solid fa-language"></i> Azure Translator (${res.target_language_name})</span>
                                <span class="translate-badge-chip">${res.is_fallback ? 'Fallback' : '<i class="fa-solid fa-bolt"></i> Live Azure AI'}</span>
                            </div>
                            <div class="translated-card-text">${escapeHtml(res.translated_text)}</div>
                        </div>
                    </div>
                `;
            } else {
                transHtml = `
                    <div class="trans-container" id="trans-container-${elem.id}">
                        <div class="translated-card-section" style="border-left-color: #60a5fa;">
                            <div class="translated-card-header" style="color: #60a5fa;">
                                <span><i class="fa-solid fa-circle-notch fa-spin"></i> Azure Translator processing...</span>
                            </div>
                        </div>
                    </div>
                `;
                // Trigger background fetch
                fetchElementTranslation(elem, currentTargetLanguage);
            }
        } else {
            transHtml = `<div class="trans-container" id="trans-container-${elem.id}"></div>`;
        }

        let textToEdit = elem.text_content || "";
        let editLabel = "Edit Extracted Text:";
        let editIcon = "fa-pen-to-square";

        if (elem.category === 'table') {
            editLabel = "Edit Table Data (Markdown / Rows & Columns):";
            editIcon = "fa-table";
            if (elem.table_data && elem.table_data.markdown_table) {
                textToEdit = elem.table_data.markdown_table;
            }
        } else if (elem.category === 'key_value') {
            editLabel = "Edit Key-Value Pairs (Key: Value per line):";
            editIcon = "fa-key";
            if (elem.key_value_pair) {
                textToEdit = Object.entries(elem.key_value_pair).map(([k, v]) => `${k}: ${v}`).join("\n");
            }
        } else if (elem.category === 'chart' || elem.category === 'figure') {
            editLabel = "Edit Chart / Graph Data & Title:";
            editIcon = "fa-chart-column";
            if (elem.chart_summary) {
                textToEdit = `${elem.chart_summary.title || ''}\n${elem.chart_summary.note || ''}`.trim() || textToEdit;
            }
        }

        card.innerHTML = `
            <div class="card-header">
                <div class="card-title-group" style="display:flex; align-items:center; gap:8px;">
                    <span class="category-tag tag-${elem.category}">${elem.category}</span>
                    <span class="card-label" style="font-weight:600; font-size:0.85rem;">${escapeHtml(elem.label)}</span>
                </div>
                <div style="display:flex; align-items:center; gap:6px;">
                    <button class="btn-card-action btn-edit-elem" onclick="toggleEditElement('${elem.id}', event)" title="Edit extracted content"><i class="fa-solid ${editIcon}"></i> Edit</button>
                    <span class="confidence-badge" style="font-size:0.75rem; color:var(--text-muted);">${Math.round(elem.confidence * 100)}% Match</span>
                </div>
            </div>
            <div class="card-body">
                <div id="card-text-display-${elem.id}">
                    ${detailsHtml}
                </div>
                <div class="edit-panel" id="edit-panel-${elem.id}" style="display:none;" onclick="event.stopPropagation()">
                    <label style="font-size:0.75rem; font-weight:700; color:#38bdf8; display:block; margin-bottom:4px;"><i class="fa-solid ${editIcon}"></i> ${editLabel}</label>
                    <textarea class="edit-textarea" id="edit-text-${elem.id}">${escapeHtml(textToEdit)}</textarea>
                    <div style="display:flex; gap:6px; margin-top:6px;">
                        <button class="btn btn-primary btn-sm" onclick="saveElementText('${elem.id}', event)"><i class="fa-solid fa-check"></i> Save & Translate</button>
                        <button class="btn btn-secondary btn-sm" onclick="toggleEditElement('${elem.id}', event)">Cancel</button>
                    </div>
                </div>
                ${transHtml}
            </div>
        `;

        listContainer.appendChild(card);
    });
}

// Synchronized Selection & Auto-scroll: Click card/polygon -> Highlight & scroll canvas to target box!
function selectElement(elemId) {
    if (activeElementId === elemId) {
        activeElementId = null;
    } else {
        activeElementId = elemId;
    }

    updateSvgOverlayHighlights();

    const allCards = document.querySelectorAll(".element-card");
    allCards.forEach(c => c.classList.remove("highlight-sync"));

    if (activeElementId) {
        const targetCard = document.getElementById(`card-${activeElementId}`);
        if (targetCard) {
            targetCard.classList.add("highlight-sync");
            targetCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }

        // Auto-scroll Canvas Viewport smoothly to center the selected text box / bounding polygon!
        scrollToCanvasElement(activeElementId);

        // Trigger translation for selected element if target language is selected
        if (currentTargetLanguage !== 'none') {
            const page = currentDocumentData ? currentDocumentData.pages[currentPageIndex] : null;
            const elem = page ? (page.elements || []).find(e => e.id === activeElementId) : null;
            if (elem) {
                fetchElementTranslation(elem, currentTargetLanguage);
            }
        }
    } else {
        // When element is unselected, smoothly fit the whole page image back in view
        fitImageToViewport(true);
    }
}

// Enterprise Target-Centric Focus: Smoothly zooms into the selected text box within the zooming area in a bold RED frame
function scrollToCanvasElement(elemId) {
    if (!currentDocumentData || !currentDocumentData.pages) return;
    const page = currentDocumentData.pages[currentPageIndex];
    if (!page || !page.elements) return;

    const elem = page.elements.find(e => e.id === elemId);
    if (!elem || !elem.bounding_box) return;

    const wrapper = document.getElementById("canvasWrapper");
    if (!wrapper) return;

    const pageW = page.width || 1000;
    const pageH = page.height || 1300;

    let minX = 0, maxX = 0, minY = 0, maxY = 0;

    if (elem.bounding_box.polygon && elem.bounding_box.polygon.length >= 8) {
        const p = elem.bounding_box.polygon;
        const xs = [p[0], p[2], p[4], p[6]];
        const ys = [p[1], p[3], p[5], p[7]];
        minX = Math.min(...xs) * pageW;
        maxX = Math.max(...xs) * pageW;
        minY = Math.min(...ys) * pageH;
        maxY = Math.max(...ys) * pageH;
    } else {
        const bbox = elem.bounding_box;
        minX = bbox.x * pageW;
        maxX = (bbox.x + bbox.width) * pageW;
        minY = bbox.y * pageH;
        maxY = (bbox.y + bbox.height) * pageH;
    }

    const boxW = Math.max(30, maxX - minX);
    const boxH = Math.max(20, maxY - minY);
    const centerX = minX + boxW / 2;
    const centerY = minY + boxH / 2;

    // Calculate base fit scale for full page image inside viewport
    const availW = wrapper.clientWidth;
    const availH = wrapper.clientHeight;
    const fitScale = Math.min(availW / pageW, availH / pageH);

    // Controlled target scale boost strictly limited so image never goes beyond the zoom workspace
    let targetScale = fitScale * 1.25;
    const maxAllowedScale = Math.max(fitScale * 1.35, 1.35);
    targetScale = Math.min(targetScale, maxAllowedScale);

    userZoomLocked = true;
    zoomScale = targetScale;
    applyZoomScale();

    // Center viewport scroll smoothly on the selected text box
    setTimeout(() => {
        const stage = document.getElementById("imageStageContainer");
        const stageLeft = stage ? stage.offsetLeft : 0;
        const stageTop = stage ? stage.offsetTop : 0;

        const scaledCenterX = centerX * zoomScale;
        const scaledCenterY = centerY * zoomScale;

        const targetScrollLeft = stageLeft + scaledCenterX - (wrapper.clientWidth / 2);
        const targetScrollTop = stageTop + scaledCenterY - (wrapper.clientHeight / 2);

        wrapper.scrollTo({
            left: Math.max(0, targetScrollLeft),
            top: Math.max(0, targetScrollTop),
            behavior: "smooth"
        });
    }, 30);
}

// Requirement Filter Selector Toolbar
function setCategoryFilter(category) {
    currentFilter = category;
    activeElementId = null; // Reset single element focus when category filter changes
    
    document.querySelectorAll(".filter-pills .pill").forEach(p => {
        if (p.getAttribute("data-category") === category) {
            p.classList.add("active");
        } else {
            p.classList.remove("active");
        }
    });

    // Instant SVG update and list update without touching zoom!
    updateSvgOverlayHighlights();
    renderExtractedElementsList();
}

// Update Requirement Counts
function updateFilterCounts() {
    if (!currentDocumentData) return;
    const page = currentDocumentData.pages[currentPageIndex];
    const elems = page.elements || [];

    const counts = {
        all: elems.length,
        table: elems.filter(e => e.category === 'table').length,
        text: elems.filter(e => e.category === 'text').length,
        chart: elems.filter(e => e.category === 'chart').length,
        figure: elems.filter(e => e.category === 'figure').length,
        key_value: elems.filter(e => e.category === 'key_value').length
    };

    for (const [k, v] of Object.entries(counts)) {
        setElementText(`count-${k}`, v);
    }
}

// Right Inspector Tab Switching
function switchInspectorTab(tabName) {
    document.querySelectorAll(".inspector-tabs .tab-btn").forEach(b => {
        b.classList.toggle("active", b.getAttribute("onclick").includes(tabName));
    });
    document.querySelectorAll(".inspector-content .tab-panel").forEach(p => {
        p.classList.toggle("active", p.id === `panel-${tabName}`);
    });
}

// Toggle AI Observability & Traces Modal
function toggleObservabilityModal() {
    const modal = document.getElementById("observabilityModal");
    if (!modal) return;
    if (modal.style.display === "none" || !modal.style.display) {
        modal.style.display = "flex";
        renderAIObservabilityPanel();
    } else {
        modal.style.display = "none";
    }
}

// Render AI Observability & Microservices Telemetry Panel
function renderAIObservabilityPanel() {
    const container = document.getElementById("observabilityContainer");
    const modalContainer = document.getElementById("observabilityContainerModal");

    const fdeArchitectureBannerHtml = `
        <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 12px 14px; margin-bottom: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-size: 0.85rem; font-weight: 700; color: #34d399;"><i class="fa-solid fa-cloud-bolt"></i> Azure Enterprise FDE Architecture Status: ACTIVE</span>
                <span class="badge badge-servicebus"><i class="fa-solid fa-satellite-dish"></i> Service Bus Enqueue Ready</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.78rem; color: var(--text-muted);">
                <div><i class="fa-solid fa-inbox" style="color:#60a5fa;"></i> <strong>Service Bus:</strong> <code>sb-explore-ai/ai-jobs-queue</code></div>
                <div><i class="fa-solid fa-database" style="color:#f59e0b;"></i> <strong>Blob Storage:</strong> <code>stexploreai65064/raw-documents</code></div>
                <div><i class="fa-solid fa-chart-line" style="color:#ec4899;"></i> <strong>App Insights:</strong> <code>func-ai-microservice-65064</code></div>
                <div><i class="fa-solid fa-shield-halved" style="color:#a78bfa;"></i> <strong>Distributed Trace:</strong> <code>W3C traceparent injected</code></div>
            </div>
        </div>
    `;

    if (!currentDocumentData || !currentDocumentData.observability) {
        const initialHtml = `
            ${fdeArchitectureBannerHtml}
            <div style="text-align: center; padding: 25px 20px; color: var(--text-muted); background: #111827; border-radius: 8px; border: 1px solid var(--border-color); margin-bottom: 14px;">
                <i class="fa-solid fa-microchip" style="font-size: 1.8rem; margin-bottom: 8px; color: #60a5fa;"></i>
                <h4 style="color: var(--text-main); font-size: 0.95rem; margin-bottom: 4px;">Telemetry Engine Ready</h4>
                <p style="font-size: 0.8rem;">Select a preset image, upload a file, or submit via Azure Service Bus to view end-to-end latency waterfall, token consumption, and cost telemetry.</p>
            </div>
            <div class="portal-links-box">
                <span style="font-size:0.78rem; font-weight:600; color:var(--text-muted);"><i class="fa-solid fa-chart-area"></i> <strong>Live Azure Portal Observability Paths:</strong></span>
                <div class="portal-btn-group" style="display:flex; flex-wrap:wrap; gap:8px; margin-top:6px;">
                    <a href="https://portal.azure.com/#@/resource/subscriptions/6fb67c72-73dc-4767-a210-0ea6b6c99feb/resourceGroups/rg-explore-ai/providers/Microsoft.ServiceBus/namespaces/sb-explore-ai/queues/ai-jobs-queue" target="_blank" class="btn btn-secondary btn-sm"><i class="fa-solid fa-satellite-dish"></i> Service Bus Queues (rg-explore-ai)</a>
                    <a href="https://portal.azure.com/#@/resource/subscriptions/6fb67c72-73dc-4767-a210-0ea6b6c99feb/resourceGroups/rg-explore-ai/providers/microsoft.insights/components/func-ai-microservice-65064" target="_blank" class="btn btn-secondary btn-sm"><i class="fa-solid fa-chart-line"></i> App Insights Live Metrics (rg-explore-ai)</a>
                    <a href="https://portal.azure.com/#@/resource/subscriptions/6fb67c72-73dc-4767-a210-0ea6b6c99feb/resourceGroups/rg-shipment-automation-poc/providers/Microsoft.CognitiveServices/accounts/aiservice-shipment-poc" target="_blank" class="btn btn-secondary btn-sm"><i class="fa-solid fa-chart-pie"></i> OpenAI Token Tracing (rg-shipment-automation-poc)</a>
                </div>
            </div>
        `;
        if (container) container.innerHTML = initialHtml;
        if (modalContainer) modalContainer.innerHTML = initialHtml;
        return;
    }

    const obs = currentDocumentData.observability;
    const traces = obs.traces || [];

    // Update Top Navbar Chip
    const topChip = document.getElementById("topObsChip");
    if (topChip) {
        topChip.innerHTML = `<i class="fa-solid fa-stopwatch"></i> ${obs.total_pipeline_latency_ms.toLocaleString()} ms | <i class="fa-solid fa-brain"></i> ${obs.total_tokens_consumed.toLocaleString()} Tok | <i class="fa-solid fa-tag"></i> $${obs.total_estimated_cost_usd.toFixed(4)}`;
    }

    let html = `
        ${fdeArchitectureBannerHtml}
        <div class="telemetry-kpi-grid">
            <div class="kpi-card">
                <span class="kpi-label"><i class="fa-solid fa-stopwatch"></i> Pipeline Latency</span>
                <span class="kpi-value highlight-blue">${obs.total_pipeline_latency_ms.toLocaleString()} ms</span>
            </div>
            <div class="kpi-card">
                <span class="kpi-label"><i class="fa-solid fa-brain"></i> Tokens Consumed</span>
                <span class="kpi-value highlight-purple">${obs.total_tokens_consumed.toLocaleString()}</span>
            </div>
            <div class="kpi-card">
                <span class="kpi-label"><i class="fa-solid fa-dollar-sign"></i> Execution Cost</span>
                <span class="kpi-value highlight-green">$${obs.total_estimated_cost_usd.toFixed(4)} USD</span>
            </div>
            <div class="kpi-card">
                <span class="kpi-label"><i class="fa-solid fa-cubes"></i> Microservices</span>
                <span class="kpi-value highlight-orange">${obs.microservices_called_count} Services</span>
            </div>
        </div>

        <div class="section-heading"><i class="fa-solid fa-diagram-next"></i> Microservice Execution Trace Call Chain:</div>
        <div class="microservice-timeline">
    `;

    traces.forEach((trace, idx) => {
        const isDocIntel = trace.service_name.includes("doc-intel");
        const isOpenAI = trace.service_name.includes("openai");
        const badgeColor = isDocIntel ? "#3b82f6" : isOpenAI ? "#10b981" : "#8b5cf6";

        html += `
            <div class="trace-card">
                <div class="trace-header">
                    <div class="trace-service-title">
                        <span class="trace-step-badge">${idx + 1}</span>
                        <strong style="color: ${badgeColor}; font-size: 0.85rem;">${escapeHtml(trace.service_name)}</strong>
                        <span class="service-type-tag">${escapeHtml(trace.service_type)}</span>
                    </div>
                    <div class="trace-metrics">
                        <span class="metric-badge badge-latency"><i class="fa-solid fa-clock"></i> ${trace.latency_ms} ms</span>
                        <span class="metric-badge badge-status"><i class="fa-solid fa-check"></i> ${trace.status_code}</span>
                    </div>
                </div>
                <div class="trace-body">
                    <div class="trace-detail-row">
                        <span><i class="fa-solid fa-link"></i> <strong>Endpoint:</strong> <code style="font-size:0.75rem;">${escapeHtml(trace.endpoint_url)}</code></span>
                        <span><i class="fa-solid fa-microchip"></i> <strong>Model/Resource:</strong> <code style="color: #60a5fa; font-size:0.75rem;">${escapeHtml(trace.model_or_resource)}</code></span>
                    </div>
                    ${trace.total_tokens > 0 ? `
                        <div class="token-breakdown-bar">
                            <span><i class="fa-solid fa-brain"></i> <strong>Tokens:</strong> ${trace.prompt_tokens.toLocaleString()} Prompt + ${trace.completion_tokens.toLocaleString()} Completion = <strong>${trace.total_tokens.toLocaleString()} Total Tokens</strong></span>
                            <span class="cost-tag"><i class="fa-solid fa-tag"></i> Cost: $${trace.estimated_cost_usd.toFixed(4)} USD</span>
                        </div>
                    ` : `
                        <div class="token-breakdown-bar" style="background: rgba(255,255,255,0.03);">
                            <span><i class="fa-solid fa-bolt"></i> <strong>Operation:</strong> Direct REST API / Database Query</span>
                            <span class="cost-tag"><i class="fa-solid fa-tag"></i> Cost: $0.00 USD</span>
                        </div>
                    `}
                </div>
            </div>
        `;
    });

    html += `
        </div>

        <div class="portal-links-box">
            <span style="font-size:0.78rem; font-weight:600; color:var(--text-muted);"><i class="fa-solid fa-chart-area"></i> <strong>Live Azure Portal Observability Paths:</strong></span>
            <div class="portal-btn-group" style="display:flex; flex-wrap:wrap; gap:8px; margin-top:6px;">
                <a href="https://portal.azure.com/#@/resource/subscriptions/6fb67c72-73dc-4767-a210-0ea6b6c99feb/resourceGroups/rg-explore-ai/providers/Microsoft.ServiceBus/namespaces/sb-explore-ai/queues/ai-jobs-queue" target="_blank" class="btn btn-secondary btn-sm"><i class="fa-solid fa-satellite-dish"></i> Service Bus Queues (rg-explore-ai)</a>
                <a href="https://portal.azure.com/#@/resource/subscriptions/6fb67c72-73dc-4767-a210-0ea6b6c99feb/resourceGroups/rg-explore-ai/providers/microsoft.insights/components/func-ai-microservice-65064" target="_blank" class="btn btn-secondary btn-sm"><i class="fa-solid fa-chart-line"></i> App Insights Live Metrics (rg-explore-ai)</a>
                <a href="https://portal.azure.com/#@/resource/subscriptions/6fb67c72-73dc-4767-a210-0ea6b6c99feb/resourceGroups/rg-shipment-automation-poc/providers/Microsoft.CognitiveServices/accounts/aiservice-shipment-poc" target="_blank" class="btn btn-secondary btn-sm"><i class="fa-solid fa-chart-pie"></i> OpenAI Token Tracing (rg-shipment-automation-poc)</a>
            </div>
        </div>
    `;

    if (container) container.innerHTML = html;
    if (modalContainer) modalContainer.innerHTML = html;
}

// Export CSV/JSON Data
function exportData(format) {
    if (!currentDocumentData) return;
    window.open(`/api/v1/documents/${currentDocumentData.document_id}/export/${format}`, '_blank');
}

// Helper: Convert Markdown Table string to HTML table
function formatMarkdownTableToHtml(md) {
    if (!md) return '';
    const lines = md.trim().split("\n").filter(l => l.trim().startsWith("|"));
    if (lines.length === 0) return md;

    let html = '<table class="data-table"><thead>';
    const headerCols = lines[0].split("|").filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
    
    html += '<tr>';
    headerCols.forEach(c => { html += `<th>${escapeHtml(c.trim())}</th>`; });
    html += '</tr></thead><tbody>';

    for (let i = 2; i < lines.length; i++) {
        const cols = lines[i].split("|").filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
        html += '<tr>';
        cols.forEach(c => { html += `<td>${escapeHtml(c.trim())}</td>`; });
        html += '</tr>';
    }

    html += 'tbody></table>';
    return html;
}

// Helper: HTML Escaping
function escapeHtml(str) {
    if (!str) return '';
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
