/**
 * Standalone Interactive Document Text Highlighter & Bounding Box Zoom Engine
 * Zero external dependencies. Designed for easy integration into any web application.
 */

class DocumentHighlighter {
    constructor(options = {}) {
        this.containerId = options.containerId || 'highlighterApp';
        this.canvasId = options.canvasId || 'docCanvas';
        this.overlayId = options.overlayId || 'svgOverlay';
        this.wrapperId = options.wrapperId || 'canvasWrapper';
        this.stageId = options.stageId || 'imageStage';
        this.cardsContainerId = options.cardsContainerId || 'cardsContainer';
        this.zoomBadgeId = options.zoomBadgeId || 'zoomBadge';

        // State
        this.documentData = null;
        this.currentPageIndex = 0;
        this.activeElementId = null;
        this.currentFilter = 'all';
        this.zoomScale = 1.0;
        this.userZoomLocked = false;

        // Mouse Pan State
        this.isMouseDownPan = false;
        this.panStartX = 0;
        this.panStartY = 0;
        this.panStartScrollLeft = 0;
        this.panStartScrollTop = 0;

        this._initEventListeners();
    }

    /**
     * Loads document JSON payload (containing pages, dimensions, image_url, and bounding_boxes)
     */
    loadDocument(documentData) {
        if (!documentData || !documentData.pages || documentData.pages.length === 0) {
            console.error('[DocumentHighlighter] Invalid document data payload.');
            return;
        }

        this.documentData = documentData;
        this.currentPageIndex = 0;
        this.activeElementId = null;
        this.userZoomLocked = false;

        this.render();
        setTimeout(() => this.fitImageToViewport(true), 100);
    }

    /**
     * Main Render Routine
     */
    render() {
        if (!this.documentData || !this.documentData.pages) return;

        const page = this.documentData.pages[this.currentPageIndex];
        if (!page) return;

        // 1. Draw Canvas Image & SVG Bounding Box Overlay
        this.renderCanvasPage(page);

        // 2. Render Right Inspector Cards
        this.renderInspectorCards(page);
    }

    /**
     * Renders Document Canvas & SVG Polygon Overlays
     */
    renderCanvasPage(page) {
        const canvas = document.getElementById(this.canvasId);
        const overlay = document.getElementById(this.overlayId);
        if (!canvas || !overlay) return;

        const ctx = canvas.getContext('2d');
        const width = page.width || 1000;
        const height = page.height || 1300;

        canvas.width = width;
        canvas.height = height;

        // Draw Canvas Background or Base Image
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, width, height);

        if (page.image_url) {
            const bgImg = new Image();
            bgImg.crossOrigin = 'anonymous';
            bgImg.onload = () => {
                ctx.drawImage(bgImg, 0, 0, width, height);
                requestAnimationFrame(() => this.applyZoomScale());
            };
            bgImg.src = page.image_url;
        } else {
            // Placeholder background pattern
            ctx.strokeStyle = '#e2e8f0';
            ctx.lineWidth = 1;
            for (let y = 40; y < height; y += 35) {
                ctx.beginPath();
                ctx.moveTo(30, y);
                ctx.lineTo(width - 30, y);
                ctx.stroke();
            }
            ctx.fillStyle = '#94a3b8';
            ctx.font = 'bold 22px Inter, sans-serif';
            ctx.fillText(`DOCUMENT PAGE ${page.page_number}`, 40, 50);
            requestAnimationFrame(() => this.applyZoomScale());
        }

        const pageElements = page.elements || [];

        // Configure SVG Overlay ViewBox
        overlay.setAttribute('viewBox', `0 0 ${width} ${height}`);
        overlay.innerHTML = '';

        // Render Bounding Box Polygons
        pageElements.forEach(elem => {
            const isMatchCat = (this.currentFilter === 'all' || elem.category === this.currentFilter);
            const isActive = (this.activeElementId === elem.id);

            // Dimming Logic: Dim all unselected boxes when an element is active!
            let isDimmed = !isMatchCat;
            if (this.activeElementId !== null) {
                isDimmed = !isActive;
            }

            const gSvg = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            gSvg.setAttribute('class', `polygon-group ${isDimmed ? 'dimmed-cat' : 'visible-cat'}`);
            gSvg.setAttribute('data-id', elem.id);
            gSvg.setAttribute('data-category', elem.category);

            let pointsStr = '';
            let minX = width, minY = height, maxX = 0, maxY = 0;

            if (elem.bounding_box && elem.bounding_box.polygon && elem.bounding_box.polygon.length >= 8) {
                const p = elem.bounding_box.polygon;
                const xs = [p[0]*width, p[2]*width, p[4]*width, p[6]*width];
                const ys = [p[1]*height, p[3]*height, p[5]*height, p[7]*height];
                pointsStr = `${p[0]*width},${p[1]*height} ${p[2]*width},${p[3]*height} ${p[4]*width},${p[5]*height} ${p[6]*width},${p[7]*height}`;
                minX = Math.min(...xs);
                maxX = Math.max(...xs);
                minY = Math.min(...ys);
                maxY = Math.max(...ys);
            } else if (elem.bounding_box) {
                const bbox = elem.bounding_box;
                const x1 = bbox.x * width;
                const y1 = bbox.y * height;
                const w = bbox.width * width;
                const h = bbox.height * height;
                pointsStr = `${x1},${y1} ${x1+w},${y1} ${x1+w},${y1+h} ${x1},${y1+h}`;
                minX = x1;
                maxX = x1 + w;
                minY = y1;
                maxY = y1 + h;
            }

            gSvg.setAttribute('data-minx', minX);
            gSvg.setAttribute('data-miny', minY);
            gSvg.setAttribute('data-label', elem.label || elem.category.toUpperCase());

            // Polygon Shape
            const polySvg = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
            polySvg.setAttribute('points', pointsStr);
            polySvg.setAttribute('class', `bounding-polygon poly-${elem.category} ${isActive ? 'active-target' : ''}`);
            polySvg.setAttribute('data-id', elem.id);

            // Active Highlight Tag
            if (isActive) {
                const textSvg = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                textSvg.setAttribute('x', Math.max(10, minX + 4));
                textSvg.setAttribute('y', Math.max(24, minY - 6));
                textSvg.setAttribute('class', 'active-tag-text');
                textSvg.textContent = `▶ SELECTED: ${elem.label || elem.category.toUpperCase()}`;
                gSvg.appendChild(textSvg);
            }

            // Click Handler: Clicking bounding box on canvas selects it
            polySvg.addEventListener('click', (e) => {
                e.stopPropagation();
                this.selectElement(elem.id);
            });

            gSvg.appendChild(polySvg);
            overlay.appendChild(gSvg);
        });
    }

    /**
     * Renders Right Inspector List Cards
     */
    renderInspectorCards(page) {
        const container = document.getElementById(this.cardsContainerId);
        if (!container) return;

        container.innerHTML = '';
        const visibleElements = (page.elements || []).filter(e => this.currentFilter === 'all' || e.category === this.currentFilter);

        if (visibleElements.length === 0) {
            container.innerHTML = `<div style="text-align:center; padding: 20px; color: var(--text-muted);">No elements found for category '${this.currentFilter}'.</div>`;
            return;
        }

        visibleElements.forEach(elem => {
            const isSelected = (this.activeElementId === elem.id);
            const card = document.createElement('div');
            card.setAttribute('class', `element-card ${isSelected ? 'active-card' : ''}`);
            card.setAttribute('id', `card-${elem.id}`);
            card.style.borderLeftColor = `var(--color-${elem.category.replace('key_value', 'keyvalue')})`;

            // Click Handler: Clicking right inspector card highlights box & zooms canvas
            card.addEventListener('click', () => this.selectElement(elem.id));

            card.innerHTML = `
                <div class="card-header">
                    <span class="card-badge tag-${elem.category}">${elem.category}</span>
                    <span style="font-size:0.75rem; color: var(--text-muted); font-family:monospace;">${elem.id}</span>
                </div>
                <div class="card-body-text">${this._escapeHtml(elem.text_content)}</div>
            `;

            container.appendChild(card);
        });
    }

    /**
     * Selects an element by ID, highlights it in RED, dims other elements,
     * and smoothly zooms / scrolls the canvas viewport to center the target box!
     */
    selectElement(elemId) {
        if (this.activeElementId === elemId) {
            this.activeElementId = null; // Toggle off if clicking active element
        } else {
            this.activeElementId = elemId;
        }

        // 1. Update SVG Highlight Classes
        this.updateSvgOverlayHighlights();

        // 2. Update Right Card Highlights
        const cards = document.querySelectorAll('.element-card');
        cards.forEach(c => c.classList.remove('active-card'));

        if (this.activeElementId) {
            const targetCard = document.getElementById(`card-${this.activeElementId}`);
            if (targetCard) {
                targetCard.classList.add('active-card');
                targetCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }

            // 3. Smoothly Zoom & Center Canvas Viewport on Target Box!
            this.scrollToCanvasElement(this.activeElementId);
        } else {
            // Reset to fit whole page when unselected
            this.fitImageToViewport(true);
        }
    }

    /**
     * Target-Centric Zooming & Smooth Centering Engine
     */
    scrollToCanvasElement(elemId) {
        if (!this.documentData || !this.documentData.pages) return;
        const page = this.documentData.pages[this.currentPageIndex];
        if (!page || !page.elements) return;

        const elem = page.elements.find(e => e.id === elemId);
        if (!elem || !elem.bounding_box) return;

        const wrapper = document.getElementById(this.wrapperId);
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

        // Calculate fit scale
        const availW = wrapper.clientWidth;
        const availH = wrapper.clientHeight;
        const fitScale = Math.min(availW / pageW, availH / pageH);

        // Boost scale smoothly to focus target box
        let targetScale = fitScale * 1.30;
        const maxAllowedScale = Math.max(fitScale * 1.5, 1.5);
        targetScale = Math.min(targetScale, maxAllowedScale);

        this.userZoomLocked = true;
        this.zoomScale = targetScale;
        this.applyZoomScale();

        // Center viewport scroll smoothly on target coordinates
        setTimeout(() => {
            const stage = document.getElementById(this.stageId);
            const stageLeft = stage ? stage.offsetLeft : 0;
            const stageTop = stage ? stage.offsetTop : 0;

            const scaledCenterX = centerX * this.zoomScale;
            const scaledCenterY = centerY * this.zoomScale;

            const targetScrollLeft = stageLeft + scaledCenterX - (wrapper.clientWidth / 2);
            const targetScrollTop = stageTop + scaledCenterY - (wrapper.clientHeight / 2);

            wrapper.scrollTo({
                left: Math.max(0, targetScrollLeft),
                top: Math.max(0, targetScrollTop),
                behavior: 'smooth'
            });
        }, 30);
    }

    /**
     * Updates SVG highlights dynamically without full redraw
     */
    updateSvgOverlayHighlights() {
        const overlay = document.getElementById(this.overlayId);
        if (!overlay) return;

        const groups = overlay.querySelectorAll('.polygon-group');
        groups.forEach(g => {
            const elemId = g.getAttribute('data-id');
            const category = g.getAttribute('data-category');
            const isMatchCat = (this.currentFilter === 'all' || category === this.currentFilter);
            const isActive = (this.activeElementId === elemId);

            let isDimmed = !isMatchCat;
            if (this.activeElementId !== null) {
                isDimmed = !isActive;
            }

            g.setAttribute('class', `polygon-group ${isDimmed ? 'dimmed-cat' : 'visible-cat'}`);

            const poly = g.querySelector('.bounding-polygon');
            if (poly) {
                poly.setAttribute('class', `bounding-polygon poly-${category} ${isActive ? 'active-target' : ''}`);
            }

            let tag = g.querySelector('.active-tag-text');
            if (isActive) {
                const label = g.getAttribute('data-label') || category.toUpperCase();
                if (!tag) {
                    const textSvg = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    const minX = parseFloat(g.getAttribute('data-minx') || '10');
                    const minY = parseFloat(g.getAttribute('data-miny') || '30');
                    textSvg.setAttribute('x', Math.max(10, minX + 4));
                    textSvg.setAttribute('y', Math.max(24, minY - 6));
                    textSvg.setAttribute('class', 'active-tag-text');
                    textSvg.textContent = `▶ SELECTED: ${label}`;
                    g.appendChild(textSvg);
                }
            } else if (tag) {
                tag.remove();
            }
        });
    }

    /**
     * Category Filter Pills Handler
     */
    setCategoryFilter(category) {
        this.currentFilter = category;
        this.activeElementId = null;

        document.querySelectorAll('.filter-pills .pill-btn').forEach(b => {
            b.classList.toggle('active', b.getAttribute('data-category') === category);
        });

        this.updateSvgOverlayHighlights();
        const page = this.documentData ? this.documentData.pages[this.currentPageIndex] : null;
        if (page) this.renderInspectorCards(page);
    }

    /**
     * Viewport Scaling Routines
     */
    applyZoomScale() {
        const stage = document.getElementById(this.stageId);
        if (!stage || !this.documentData || !this.documentData.pages) return;

        const page = this.documentData.pages[this.currentPageIndex];
        if (!page) return;

        const pageW = page.width || 1000;
        const pageH = page.height || 1300;

        stage.style.width = `${Math.round(pageW * this.zoomScale)}px`;
        stage.style.height = `${Math.round(pageH * this.zoomScale)}px`;

        const badge = document.getElementById(this.zoomBadgeId);
        if (badge) {
            badge.textContent = `${Math.round(this.zoomScale * 100)}%`;
        }
    }

    zoomCanvas(delta) {
        this.userZoomLocked = true;
        this.zoomScale = Math.min(Math.max(0.2, this.zoomScale + delta), 2.5);
        this.applyZoomScale();
    }

    fitImageToViewport(force = false) {
        if (this.userZoomLocked && !force) {
            this.applyZoomScale();
            return;
        }
        if (force) this.userZoomLocked = false;

        const wrapper = document.getElementById(this.wrapperId);
        if (!wrapper || !this.documentData || !this.documentData.pages) return;

        const page = this.documentData.pages[this.currentPageIndex];
        if (!page) return;

        const availW = wrapper.clientWidth;
        const availH = wrapper.clientHeight;
        const pageW = page.width || 1000;
        const pageH = page.height || 1300;

        if (availW > 0 && availH > 0 && pageW > 0 && pageH > 0) {
            const scaleX = availW / pageW;
            const scaleY = availH / pageH;
            this.zoomScale = Math.min(scaleX, scaleY);
            this.applyZoomScale();
            wrapper.scrollLeft = 0;
            wrapper.scrollTop = 0;
        }
    }

    /**
     * Init Mouse Pan and Wheel Zoom Listeners
     */
    _initEventListeners() {
        document.addEventListener('DOMContentLoaded', () => {
            const wrapper = document.getElementById(this.wrapperId);
            if (!wrapper) return;

            // Drag-to-Pan
            wrapper.addEventListener('mousedown', (e) => {
                if (e.target.tagName === 'CANVAS' || e.target.classList.contains('canvas-wrapper') || e.target.classList.contains('image-stage')) {
                    this.isMouseDownPan = true;
                    this.panStartX = e.clientX;
                    this.panStartY = e.clientY;
                    this.panStartScrollLeft = wrapper.scrollLeft;
                    this.panStartScrollTop = wrapper.scrollTop;
                    wrapper.style.cursor = 'grabbing';
                }
            });

            window.addEventListener('mousemove', (e) => {
                if (this.isMouseDownPan && wrapper) {
                    const dx = e.clientX - this.panStartX;
                    const dy = e.clientY - this.panStartY;
                    wrapper.scrollLeft = this.panStartScrollLeft - dx;
                    wrapper.scrollTop = this.panStartScrollTop - dy;
                }
            });

            window.addEventListener('mouseup', () => {
                this.isMouseDownPan = false;
                if (wrapper) wrapper.style.cursor = '';
            });

            // Wheel Zoom
            wrapper.addEventListener('wheel', (e) => {
                e.preventDefault();
                const delta = e.deltaY < 0 ? 0.08 : -0.08;
                this.zoomCanvas(delta);
            }, { passive: false });

            window.addEventListener('resize', () => {
                if (!this.userZoomLocked) this.fitImageToViewport(false);
            });
        });
    }

    _escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
}
