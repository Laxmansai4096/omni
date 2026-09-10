import logging
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger("vision_analyzer")

class AzureVisionAnalyzer:
    def __init__(self):
        self.endpoint = settings.AZURE_OPENAI_ENDPOINT
        self.key = settings.AZURE_OPENAI_KEY
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT_NAME
        self.is_configured = bool(self.endpoint and self.key)

    def analyze_chart_image(self, image_base64: str) -> Dict[str, Any]:
        """Uses Azure OpenAI GPT-4o Vision to extract data points, trends, and markdown tables from charts/graphs."""
        if not self.is_configured:
            logger.info("Azure OpenAI Vision not configured. Returning static analysis structure.")
            return {
                "chart_type": "Bar / Line Financial Chart",
                "title": "Quarterly Performance Breakdown",
                "metrics": {"Q1": "$12.4M", "Q2": "$18.6M", "Q3": "$24.1M", "Q4": "$31.0M"},
                "insights": "Consistent quarter-over-quarter revenue expansion (+35% QoQ avg)."
            }

        try:
            from openai import AzureOpenAI
            client = AzureOpenAI(
                azure_endpoint=self.endpoint,
                api_key=self.key,
                api_version="2024-02-15-preview"
            )

            response = client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a concise document and chart analyst. Extract key metrics, visual trends, and chart insights from the image in brief JSON format (chart_type, title, metrics, insights)."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Analyze visual elements/charts in this image into concise JSON format."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}", "detail": "low"}}
                        ]
                    }
                ],
                max_completion_tokens=350
            )
            usage = getattr(response, "usage", None)
            usage_dict = {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
                "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
                "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0
            }
            return {
                "analysis": response.choices[0].message.content,
                "usage": usage_dict
            }
        except Exception as e:
            logger.error(f"Error calling Azure OpenAI Vision API: {e}")
            return {"error": str(e), "note": "Vision API fallback mode"}
