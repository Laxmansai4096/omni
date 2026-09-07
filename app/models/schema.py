from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum

class ElementCategory(str, Enum):
    ALL = "all"
    TABLE = "table"
    TEXT = "text"
    FIGURE = "figure"
    CHART = "chart"
    KEY_VALUE = "key_value"
    HEADER_FOOTER = "header_footer"

class BoundingBox(BaseModel):
    # Normalized coordinates (0.0 to 1.0)
    x: float = Field(..., description="Top left X position (normalized 0..1)")
    y: float = Field(..., description="Top left Y position (normalized 0..1)")
    width: float = Field(..., description="Width (normalized 0..1)")
    height: float = Field(..., description="Height (normalized 0..1)")
    polygon: List[float] = Field(default_factory=list, description="Array of [x1, y1, x2, y2, x3, y3, x4, y4]")

class TableCell(BaseModel):
    row_index: int
    column_index: int
    row_span: Optional[int] = 1
    column_span: Optional[int] = 1
    content: str
    is_header: bool = False
    bounding_box: Optional[BoundingBox] = None

class TableData(BaseModel):
    row_count: int
    column_count: int
    cells: List[TableCell]
    markdown_table: str
    csv_content: str

class ExtractedElement(BaseModel):
    id: str
    page_number: int
    category: ElementCategory
    label: str
    confidence: float
    bounding_box: BoundingBox
    text_content: str
    table_data: Optional[TableData] = None
    key_value_pair: Optional[Dict[str, str]] = None
    chart_summary: Optional[Dict[str, Any]] = None
    crop_image_url: Optional[str] = None

class DocumentPage(BaseModel):
    page_number: int
    width: float
    height: float
    unit: str = "pixel"
    image_url: Optional[str] = None
    elements: List[ExtractedElement] = Field(default_factory=list)

class AnalysisSummary(BaseModel):
    total_pages: int
    total_elements: int
    counts_by_category: Dict[str, int]
    processing_time_ms: float

class MicroserviceTrace(BaseModel):
    service_name: str
    service_type: str
    endpoint_url: str
    model_or_resource: str
    status_code: int = 200
    status_text: str = "SUCCESS"
    latency_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    timestamp: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)

class AIObservabilitySummary(BaseModel):
    total_pipeline_latency_ms: float
    total_tokens_consumed: int
    total_estimated_cost_usd: float
    microservices_called_count: int
    azure_resources_used: List[str]
    traces: List[MicroserviceTrace] = Field(default_factory=list)

class DocumentAnalysisResult(BaseModel):
    document_id: str
    file_name: str
    source_type: str  # upload, url, sample
    file_size_bytes: int
    pages: List[DocumentPage]
    summary: AnalysisSummary
    observability: Optional[AIObservabilitySummary] = None
