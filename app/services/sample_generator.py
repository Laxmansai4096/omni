import uuid
import time
from typing import Dict, List
from app.models.schema import (
    DocumentAnalysisResult, DocumentPage, ExtractedElement, 
    ElementCategory, BoundingBox, TableData, TableCell, AnalysisSummary,
    MicroserviceTrace, AIObservabilitySummary
)

def build_sample_expense_report() -> DocumentAnalysisResult:
    """Sample 1: Expense Report with Invoice Tables, KV Pairs, and Approvals."""
    doc_id = "sample-expense-001"
    
    # Page 1 Elements
    p1_elements = [
        ExtractedElement(
            id="elem-101",
            page_number=1,
            category=ElementCategory.HEADER_FOOTER,
            label="Header Title",
            confidence=0.99,
            bounding_box=BoundingBox(x=0.08, y=0.05, width=0.84, height=0.08, polygon=[0.08, 0.05, 0.92, 0.05, 0.92, 0.13, 0.08, 0.13]),
            text_content="GLOBAL ENTERPRISE CORP - QUARTERLY EXPENSE & TRAVEL REPORT"
        ),
        ExtractedElement(
            id="elem-102",
            page_number=1,
            category=ElementCategory.KEY_VALUE,
            label="Metadata Fields",
            confidence=0.97,
            bounding_box=BoundingBox(x=0.08, y=0.15, width=0.84, height=0.12, polygon=[0.08, 0.15, 0.92, 0.15, 0.92, 0.27, 0.08, 0.27]),
            text_content="Employee Name: Sarah Jenkins | Dept: AI Engineering | Report ID: EXP-2026-8891 | Date: Aug 28, 2026",
            key_value_pair={
                "Employee Name": "Sarah Jenkins",
                "Department": "AI Engineering",
                "Report ID": "EXP-2026-8891",
                "Submission Date": "Aug 28, 2026",
                "Status": "Approved",
                "Total Reimbursable": "$4,850.50"
            }
        ),
        ExtractedElement(
            id="elem-103",
            page_number=1,
            category=ElementCategory.TABLE,
            label="Itemized Travel Expenses Table",
            confidence=0.98,
            bounding_box=BoundingBox(x=0.08, y=0.30, width=0.84, height=0.35, polygon=[0.08, 0.30, 0.92, 0.30, 0.92, 0.65, 0.08, 0.65]),
            text_content="Itemized Expenses Table containing Flight, Hotel, Meals and Transport details.",
            table_data=TableData(
                row_count=5,
                column_count=5,
                markdown_table="""| Date | Expense Description | Category | Vendor | Amount ($) |
|---|---|---|---|---|
| 08/12/2026 | Flight JFK to SEA | Airfare | Delta Airlines | 1,240.00 |
| 08/13/2026 | Hotel Accommodation 3 Nights | Lodging | Hyatt Regency | 1,850.50 |
| 08/14/2026 | Client Dinner & Conference | Meals | Ocean Prime | 460.00 |
| 08/15/2026 | Azure Cloud Training Workshop | Education | Microsoft | 1,300.00 |""",
                csv_content="Date,Expense Description,Category,Vendor,Amount ($)\n08/12/2026,Flight JFK to SEA,Airfare,Delta Airlines,1240.00\n08/13/2026,Hotel Accommodation 3 Nights,Lodging,Hyatt Regency,1850.50\n08/14/2026,Client Dinner & Conference,Meals,Ocean Prime,460.00\n08/15/2026,Azure Cloud Training Workshop,Education,Microsoft,1300.00",
                cells=[
                    TableCell(row_index=0, column_index=0, row_span=1, column_span=1, content="Date", is_header=True),
                    TableCell(row_index=0, column_index=1, row_span=1, column_span=1, content="Expense Description", is_header=True),
                    TableCell(row_index=0, column_index=2, row_span=1, column_span=1, content="Category", is_header=True),
                    TableCell(row_index=0, column_index=3, row_span=1, column_span=1, content="Vendor", is_header=True),
                    TableCell(row_index=0, column_index=4, row_span=1, column_span=1, content="Amount ($)", is_header=True),
                    TableCell(row_index=1, column_index=0, row_span=1, column_span=1, content="08/12/2026"),
                    TableCell(row_index=1, column_index=1, row_span=1, column_span=1, content="Flight JFK to SEA"),
                    TableCell(row_index=1, column_index=2, row_span=1, column_span=1, content="Airfare"),
                    TableCell(row_index=1, column_index=3, row_span=1, column_span=1, content="Delta Airlines"),
                    TableCell(row_index=1, column_index=4, row_span=1, column_span=1, content="1,240.00"),
                    TableCell(row_index=2, column_index=0, row_span=1, column_span=1, content="08/13/2026"),
                    TableCell(row_index=2, column_index=1, row_span=1, column_span=1, content="Hotel Accommodation 3 Nights"),
                    TableCell(row_index=2, column_index=2, row_span=1, column_span=1, content="Lodging"),
                    TableCell(row_index=2, column_index=3, row_span=1, column_span=1, content="Hyatt Regency"),
                    TableCell(row_index=2, column_index=4, row_span=1, column_span=1, content="1,850.50"),
                    TableCell(row_index=3, column_index=0, row_span=1, column_span=1, content="08/14/2026"),
                    TableCell(row_index=3, column_index=1, row_span=1, column_span=1, content="Client Dinner & Conference"),
                    TableCell(row_index=3, column_index=2, row_span=1, column_span=1, content="Meals"),
                    TableCell(row_index=3, column_index=3, row_span=1, column_span=1, content="Ocean Prime"),
                    TableCell(row_index=3, column_index=4, row_span=1, column_span=1, content="460.00"),
                    TableCell(row_index=4, column_index=0, row_span=1, column_span=1, content="08/15/2026"),
                    TableCell(row_index=4, column_index=1, row_span=1, column_span=1, content="Azure Cloud Training Workshop"),
                    TableCell(row_index=4, column_index=2, row_span=1, column_span=1, content="Education"),
                    TableCell(row_index=4, column_index=3, row_span=1, column_span=1, content="Microsoft"),
                    TableCell(row_index=4, column_index=4, row_span=1, column_span=1, content="1,300.00"),
                ]
            )
        ),
        ExtractedElement(
            id="elem-104",
            page_number=1,
            category=ElementCategory.CHART,
            label="Expense Category Allocation Breakdown Chart",
            confidence=0.96,
            bounding_box=BoundingBox(x=0.08, y=0.68, width=0.40, height=0.25, polygon=[0.08, 0.68, 0.48, 0.68, 0.48, 0.93, 0.08, 0.93]),
            text_content="Pie chart showing category share: Lodging (38.1%), Education (26.8%), Airfare (25.6%), Meals (9.5%).",
            chart_summary={
                "chart_type": "Donut / Pie Chart",
                "title": "Expense Distribution by Category",
                "metrics": {
                    "Lodging": "$1,850.50 (38.1%)",
                    "Education": "$1,300.00 (26.8%)",
                    "Airfare": "$1,240.00 (25.6%)",
                    "Meals": "$460.00 (9.5%)"
                },
                "key_takeaway": "Lodging and Education represent over 64% of total quarter expenses."
            }
        ),
        ExtractedElement(
            id="elem-105",
            page_number=1,
            category=ElementCategory.TEXT,
            label="Manager Approval Notes",
            confidence=0.99,
            bounding_box=BoundingBox(x=0.52, y=0.68, width=0.40, height=0.25, polygon=[0.52, 0.68, 0.92, 0.68, 0.92, 0.93, 0.52, 0.93]),
            text_content="APPROVAL MEMO:\nReport audited and approved by Finance VP Mark Stevens on 08/29/2026. Reimbursable funds scheduled for direct deposit via Azure Payroll Service."
        )
    ]
    
    pages = [
        DocumentPage(page_number=1, width=1000, height=1300, unit="pixel", elements=p1_elements)
    ]
    
    summary = AnalysisSummary(
        total_pages=1,
        total_elements=len(p1_elements),
        counts_by_category={
            "table": 1,
            "text": 1,
            "key_value": 1,
            "chart": 1,
            "header_footer": 1
        },
        processing_time_ms=2490.5
    )

    observability = AIObservabilitySummary(
        total_pipeline_latency_ms=2490.5,
        total_tokens_consumed=1930,
        total_estimated_cost_usd=0.0020,
        microservices_called_count=4,
        azure_resources_used=[
            "omnidoc-docintel-k62z7k46ybsbm (Azure AI Document Intelligence)",
            "aiservice-shipment-poc (Azure OpenAI Service - gpt-5-mini)",
            "FastAPI Gateway Service",
            "SQLite Local Store Service"
        ],
        traces=[
            MicroserviceTrace(
                service_name="fastapi-gateway-service",
                service_type="Ingestion & Payload Validation",
                endpoint_url="http://localhost:8000/api/v1/documents/upload",
                model_or_resource="FastAPI uvicorn v1.0.0",
                status_code=200,
                status_text="SUCCESS",
                latency_ms=18.5,
                estimated_cost_usd=0.0,
                timestamp="2026-09-07T09:48:12Z",
                details={"file_name": "Expense_Travel_Report_Q3_2026.pdf", "size_bytes": 425100}
            ),
            MicroserviceTrace(
                service_name="azure-doc-intel-microservice",
                service_type="AI OCR & Bounding Box Layout Engine",
                endpoint_url="https://omnidoc-docintel-k62z7k46ybsbm.cognitiveservices.azure.com/",
                model_or_resource="prebuilt-layout",
                status_code=200,
                status_text="SUCCESS",
                latency_ms=1840.0,
                estimated_cost_usd=0.0015,
                timestamp="2026-09-07T09:48:13Z",
                details={"processed_pages": 1, "tables_found": 1, "lines_extracted": 42}
            ),
            MicroserviceTrace(
                service_name="azure-openai-vision-microservice",
                service_type="Multimodal Vision LLM Intelligence",
                endpoint_url="https://aiservice-shipment-poc.openai.azure.com/",
                model_or_resource="gpt-5-mini",
                status_code=200,
                status_text="SUCCESS",
                latency_ms=620.0,
                prompt_tokens=1450,
                completion_tokens=480,
                total_tokens=1930,
                estimated_cost_usd=0.0005,
                timestamp="2026-09-07T09:48:14Z",
                details={"categorization": "Expense Report", "key_values_extracted": 6, "confidence": 0.98}
            ),
            MicroserviceTrace(
                service_name="sqlite-document-store-microservice",
                service_type="Database Persistence Engine",
                endpoint_url="sqlite:///app/database/omnidoc_store.db",
                model_or_resource="omnidoc_store.db",
                status_code=200,
                status_text="SUCCESS",
                latency_ms=12.0,
                estimated_cost_usd=0.0,
                timestamp="2026-09-07T09:48:15Z",
                details={"db_table": "documents", "record_id": doc_id}
            )
        ]
    )
    
    return DocumentAnalysisResult(
        document_id=doc_id,
        file_name="Expense_Travel_Report_Q3_2026.pdf",
        source_type="sample",
        file_size_bytes=425100,
        pages=pages,
        summary=summary,
        observability=observability
    )


def build_sample_financial_report() -> DocumentAnalysisResult:
    """Sample 2: Financial Performance with Bar Charts, Growth Figures, & Revenue Tables."""
    doc_id = "sample-financial-002"
    
    p1_elements = [
        ExtractedElement(
            id="fin-201",
            page_number=1,
            category=ElementCategory.HEADER_FOOTER,
            label="Report Header",
            confidence=0.99,
            bounding_box=BoundingBox(x=0.05, y=0.04, width=0.90, height=0.07, polygon=[0.05, 0.04, 0.95, 0.04, 0.95, 0.11, 0.05, 0.11]),
            text_content="AZURE CLOUD ENTERPRISE - ANNUAL REVENUE & MARGIN FORECAST 2026-2027"
        ),
        ExtractedElement(
            id="fin-202",
            page_number=1,
            category=ElementCategory.CHART,
            label="Quarterly Revenue Growth Bar Chart",
            confidence=0.97,
            bounding_box=BoundingBox(x=0.05, y=0.13, width=0.43, height=0.32, polygon=[0.05, 0.13, 0.48, 0.13, 0.48, 0.45, 0.05, 0.45]),
            text_content="Bar chart detailing Quarterly Revenue ($ Millions) for Q1 ($42.5M), Q2 ($51.2M), Q3 ($64.8M), Q4 ($78.0M).",
            chart_summary={
                "chart_type": "Grouped Bar Chart",
                "title": "2026 Quarterly Revenue ($M)",
                "data_points": {
                    "Q1 2026": "$42.5M",
                    "Q2 2026": "$51.2M",
                    "Q3 2026": "$64.8M",
                    "Q4 2026 (Est)": "$78.0M"
                },
                "trend": "Positive upward trajectory driven by AI Service adoption (+83.5% YoY)."
            }
        ),
        ExtractedElement(
            id="fin-203",
            page_number=1,
            category=ElementCategory.FIGURE,
            label="Architecture Diagram: Multi-Region Azure Cluster",
            confidence=0.95,
            bounding_box=BoundingBox(x=0.52, y=0.13, width=0.43, height=0.32, polygon=[0.52, 0.13, 0.95, 0.13, 0.95, 0.45, 0.52, 0.45]),
            text_content="System architecture diagram showcasing active-active multi-region load balancing with Azure Front Door, Container Apps, and Azure Cosmos DB.",
            chart_summary={
                "figure_type": "Cloud Architecture Topology",
                "components": ["Azure Front Door", "FastAPI Container Apps", "Azure AI Document Intelligence", "Blob Storage", "Key Vault"],
                "resilience": "99.99% SLA across East US & West Europe regions"
            }
        ),
        ExtractedElement(
            id="fin-204",
            page_number=1,
            category=ElementCategory.TABLE,
            label="Financial Metrics Comparison Table",
            confidence=0.99,
            bounding_box=BoundingBox(x=0.05, y=0.48, width=0.90, height=0.45, polygon=[0.05, 0.48, 0.95, 0.48, 0.95, 0.93, 0.05, 0.93]),
            text_content="Detailed breakdown of operational expenses, gross profit, R&D allocation, and net margin.",
            table_data=TableData(
                row_count=6,
                column_count=5,
                markdown_table="""| Business Segment | FY2025 Revenue ($M) | FY2026 Target ($M) | Growth YoY (%) | Operating Margin |
|---|---|---|---|---|
| AI & Document Intelligence | $18.4M | $48.2M | +161.9% | 42.5% |
| Infrastructure Container Apps | $62.0M | $89.5M | +44.3% | 36.0% |
| Data & Analytics Pipelines | $34.1M | $52.0M | +52.4% | 29.8% |
| Security & Key Management | $12.5M | $18.0M | +44.0% | 51.2% |
| Total Enterprise Portfolio | $127.0M | $207.7M | +63.5% | 38.6% |""",
                csv_content="Business Segment,FY2025 Revenue ($M),FY2026 Target ($M),Growth YoY (%),Operating Margin\nAI & Document Intelligence,18.4,48.2,+161.9%,42.5%\nInfrastructure Container Apps,62.0,89.5,+44.3%,36.0%\nData & Analytics Pipelines,34.1,52.0,+52.4%,29.8%\nSecurity & Key Management,12.5,18.0,+44.0%,51.2%\nTotal Enterprise Portfolio,127.0,207.7,+63.5%,38.6%",
                cells=[]
            )
        )
    ]
    
    pages = [
        DocumentPage(page_number=1, width=1000, height=1300, unit="pixel", elements=p1_elements)
    ]
    
    summary = AnalysisSummary(
        total_pages=1,
        total_elements=len(p1_elements),
        counts_by_category={
            "table": 1,
            "chart": 1,
            "figure": 1,
            "header_footer": 1
        },
        processing_time_ms=3150.0
    )

    observability = AIObservabilitySummary(
        total_pipeline_latency_ms=3150.0,
        total_tokens_consumed=2450,
        total_estimated_cost_usd=0.0028,
        microservices_called_count=4,
        azure_resources_used=[
            "omnidoc-docintel-k62z7k46ybsbm (Azure AI Document Intelligence)",
            "aiservice-shipment-poc (Azure OpenAI Service - gpt-5-mini)",
            "FastAPI Gateway Service",
            "SQLite Local Store Service"
        ],
        traces=[
            MicroserviceTrace(
                service_name="fastapi-gateway-service",
                service_type="Ingestion & Payload Validation",
                endpoint_url="http://localhost:8000/api/v1/documents/upload",
                model_or_resource="FastAPI uvicorn v1.0.0",
                status_code=200,
                status_text="SUCCESS",
                latency_ms=22.0,
                estimated_cost_usd=0.0,
                timestamp="2026-09-07T09:49:01Z",
                details={"file_name": "Azure_Enterprise_Financial_Forecast_2026.pdf", "size_bytes": 891000}
            ),
            MicroserviceTrace(
                service_name="azure-doc-intel-microservice",
                service_type="AI OCR & Bounding Box Layout Engine",
                endpoint_url="https://omnidoc-docintel-k62z7k46ybsbm.cognitiveservices.azure.com/",
                model_or_resource="prebuilt-layout",
                status_code=200,
                status_text="SUCCESS",
                latency_ms=2150.0,
                estimated_cost_usd=0.0015,
                timestamp="2026-09-07T09:49:02Z",
                details={"processed_pages": 1, "tables_found": 1, "charts_detected": 1, "figures_detected": 1}
            ),
            MicroserviceTrace(
                service_name="azure-openai-vision-microservice",
                service_type="Multimodal Vision LLM Intelligence",
                endpoint_url="https://aiservice-shipment-poc.openai.azure.com/",
                model_or_resource="gpt-5-mini",
                status_code=200,
                status_text="SUCCESS",
                latency_ms=960.0,
                prompt_tokens=1820,
                completion_tokens=630,
                total_tokens=2450,
                estimated_cost_usd=0.0013,
                timestamp="2026-09-07T09:49:04Z",
                details={"categorization": "Financial Report", "chart_analysis": "Grouped Bar Chart", "confidence": 0.97}
            ),
            MicroserviceTrace(
                service_name="sqlite-document-store-microservice",
                service_type="Database Persistence Engine",
                endpoint_url="sqlite:///app/database/omnidoc_store.db",
                model_or_resource="omnidoc_store.db",
                status_code=200,
                status_text="SUCCESS",
                latency_ms=18.0,
                estimated_cost_usd=0.0,
                timestamp="2026-09-07T09:49:05Z",
                details={"db_table": "documents", "record_id": doc_id}
            )
        ]
    )
    
    return DocumentAnalysisResult(
        document_id=doc_id,
        file_name="Azure_Enterprise_Financial_Forecast_2026.pdf",
        source_type="sample",
        file_size_bytes=891000,
        pages=pages,
        summary=summary,
        observability=observability
    )


def get_sample_document(sample_id: str) -> DocumentAnalysisResult:
    if "financial" in sample_id.lower():
        return build_sample_financial_report()
    return build_sample_expense_report()
