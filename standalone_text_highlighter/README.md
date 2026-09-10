# Standalone Document Text Highlighter & Bounding Box Zoom Engine

A lightweight, zero-dependency JavaScript & CSS module for rendering document page images with interactive SVG bounding box overlays, synchronized selection highlighting, and target-centric auto-zooming.

---

## 💡 How It Works

### 1. Bounding Box & Polygon Normalization
- Document processing engines (e.g. Azure AI Document Intelligence, OCR, AWS Textract) return coordinates for detected elements either as:
  - **4-point bounding boxes**: `{ x: 0.05, y: 0.12, width: 0.42, height: 0.18 }` (normalized `0.0` to `1.0`).
  - **8-point polygons**: `[x0, y0, x1, y1, x2, y2, x3, y3]` (normalized `0.0` to `1.0`).
- The engine scales these normalized points against the image canvas dimensions (`page.width` × `page.height`) to place SVG `<polygon>` shapes precisely over the original image text.

### 2. Bidirectional Synchronized Highlighting
- **Canvas → Inspector**: Clicking an SVG polygon on the canvas selects it, highlights the polygon in **bold red (`.active-target`)**, dims unselected polygons (`.dimmed-cat`), and highlights the corresponding card on the right-side inspector panel while auto-scrolling it into view.
- **Inspector → Canvas**: Clicking an element card on the right inspector panel triggers `selectElement(id)`, which highlights the matching polygon on the canvas and triggers target-centric smooth auto-zooming.

### 3. Target-Centric Auto-Zooming & Centering (`scrollToCanvasElement`)
When an element card is clicked, `scrollToCanvasElement(id)`:
1. Calculates the element bounding box center coordinates (`centerX`, `centerY`).
2. Scales the canvas viewport zoom level (`targetScale = fitScale * 1.30`).
3. Computes exact viewport scroll offsets:
   $$\text{targetScrollLeft} = \text{scaledCenterX} - \left(\frac{\text{viewportWidth}}{2}\right)$$
   $$\text{targetScrollTop} = \text{scaledCenterY} - \left(\frac{\text{viewportHeight}}{2}\right)$$
4. Calls `wrapper.scrollTo({ left, top, behavior: "smooth" })` to smoothly animate and center the target box right in the middle of the user's screen.

---

## 📁 File Structure

```
standalone_text_highlighter/
├── index.html        # Demo HTML page showcasing the interactive viewer
├── viewer.js         # Zero-dependency DocumentHighlighter JS class
├── viewer.css        # Complete UI styling & polygon highlight stylesheets
├── sample_data.json  # Example document schema payload with bounding boxes
└── README.md         # Integration guide & documentation
```

---

## 🚀 How to Use in Another Project

### Step 1: Include CSS and JS in your HTML
```html
<link rel="stylesheet" href="viewer.css">
<script src="viewer.js"></script>
```

### Step 2: Add Container HTML Structure
```html
<div class="canvas-wrapper" id="canvasWrapper">
    <div class="image-stage" id="imageStage">
        <canvas id="docCanvas"></canvas>
        <svg id="svgOverlay"></svg>
    </div>
</div>
<div class="cards-container" id="cardsContainer"></div>
```

### Step 3: Instantiate and Load Payload in JavaScript
```javascript
const highlighter = new DocumentHighlighter();

// Pass your document JSON payload
highlighter.loadDocument(myDocumentJsonPayload);
```

---

## 🛠 Document Data JSON Schema Format
```json
{
  "pages": [
    {
      "page_number": 1,
      "width": 1000,
      "height": 1300,
      "image_url": "https://example.com/document.png",
      "elements": [
        {
          "id": "elem-01",
          "category": "text",
          "label": "Header",
          "text_content": "Extracted text content goes here...",
          "bounding_box": {
            "x": 0.05,
            "y": 0.12,
            "width": 0.45,
            "height": 0.10,
            "polygon": [0.05, 0.12, 0.50, 0.12, 0.50, 0.22, 0.05, 0.22]
          }
        }
      ]
    }
  ]
}
```
