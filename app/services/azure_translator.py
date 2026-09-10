import logging
import requests
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    "hi": "Hindi",
    "te": "Telugu",
    "fr": "French",
    "de": "German",
    "kn": "Kannada"
}

class AzureTranslatorService:
    def __init__(self):
        self.endpoint = settings.AZURE_TRANSLATOR_ENDPOINT.rstrip('/')
        self.key = settings.AZURE_TRANSLATOR_KEY
        self.region = settings.AZURE_TRANSLATOR_REGION

    @property
    def is_configured(self) -> bool:
        return bool(self.key and len(self.key) > 5)

    def translate_text(self, text: str, target_language: str, source_language: Optional[str] = "en") -> Dict[str, Any]:
        """
        Translates text from source language (default English 'en') to one of 5 supported target languages:
        'hi' (Hindi), 'te' (Telugu), 'fr' (French), 'de' (German), 'kn' (Kannada).
        """
        if not text or not text.strip():
            return {
                "original_text": text,
                "translated_text": text,
                "source_language": source_language,
                "target_language": target_language,
                "target_language_name": SUPPORTED_LANGUAGES.get(target_language, target_language),
                "status": "success",
                "is_fallback": False
            }

        target_lang = target_language.lower()
        if target_lang not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported target language '{target_language}'. Supported: {list(SUPPORTED_LANGUAGES.keys())}")

        lang_name = SUPPORTED_LANGUAGES[target_lang]

        if not self.is_configured:
            logger.warning("Azure Translator key not configured. Using fallback translation.")
            return {
                "original_text": text,
                "translated_text": f"[{lang_name} Translation]: {text}",
                "source_language": source_language,
                "target_language": target_lang,
                "target_language_name": lang_name,
                "status": "fallback",
                "is_fallback": True
            }

        url = f"{self.endpoint}/translate"
        params = {
            "api-version": "3.0",
            "to": target_lang
        }
        if source_language:
            params["from"] = source_language

        headers = {
            "Ocp-Apim-Subscription-Key": self.key,
            "Ocp-Apim-Subscription-Region": self.region,
            "Content-Type": "application/json"
        }

        body = [{"Text": text}]

        try:
            response = requests.post(url, params=params, headers=headers, json=body, timeout=10)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                translations = data[0].get("translations", [])
                if translations:
                    translated = translations[0].get("text", text)
                    detected_src = data[0].get("detectedLanguage", {}).get("language", source_language)
                    return {
                        "original_text": text,
                        "translated_text": translated,
                        "source_language": detected_src or source_language,
                        "target_language": target_lang,
                        "target_language_name": lang_name,
                        "status": "success",
                        "is_fallback": False
                    }

            raise RuntimeError(f"Unexpected response format from Azure Translator API: {data}")

        except Exception as e:
            logger.error(f"Error calling Azure Translator API: {str(e)}")
            return {
                "original_text": text,
                "translated_text": f"[{lang_name} Translation]: {text}",
                "source_language": source_language,
                "target_language": target_lang,
                "target_language_name": lang_name,
                "status": "error",
                "error_message": str(e),
                "is_fallback": True
            }

translator_service = AzureTranslatorService()
