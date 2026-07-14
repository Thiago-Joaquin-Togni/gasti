import asyncio
import json
from typing import Optional

from google import genai
from google.genai import types

from config import GEMINI_API_KEY
from core.LoggerManagger import log
from ia.base import BaseAIExtractor, ExtractedData


_FINANCIAL_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "concepto": {"type": "string"},
        "monto": {"type": "number"},
        "tipo": {"type": "string", "enum": ["GASTO", "INGRESO"]},
        "categoria": {"type": "string"}, 
    },
    "required": ["concepto", "monto", "tipo", "categoria"],
}


class GeminiExtractor(BaseAIExtractor):
    def __init__(
        self,
        model_name: str = "gemini-3.1-flash-lite",
        max_retries: int = 5,
        base_delay: float = 5.0,
    ):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY no está configurado en el archivo .env")
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model_name = model_name
        self.max_retries = max_retries
        self.base_delay = base_delay

    def _build_config(self, response_schema: dict) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
        )

    async def _call_with_retry(
        self,
        prompt: str,
        file_path: Optional[str] = None,
        response_schema: Optional[dict] = None,
    ) -> str:
        config = self._build_config(response_schema) if response_schema else None

        for attempt in range(self.max_retries + 1):
            if file_path:
                uploaded_file = self.client.files.upload(file=file_path)
                response = await self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=[prompt, uploaded_file],
                    config=config,
                )
            else:
                response = await self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )

            text = getattr(response, "text", None) or ""
            if text.strip():
                return text.strip()

            if attempt < self.max_retries:
                delay = self.base_delay * (attempt + 1)
                log.warning(
                    f"Gemini no devolvió respuesta. Reintentando en {delay}s "
                    f"(intento {attempt + 1}/{self.max_retries})"
                )
                await asyncio.sleep(delay)

        raise RuntimeError(
            f"Gemini no devolvió respuesta después de {self.max_retries} reintentos"
        )

    async def extract_from_text(self, text: str) -> ExtractedData:
        prompt = (
            "Extraé los datos financieros del siguiente texto. "
            "Respondé únicamente con el JSON especificado en el schema.\n\n"
            f"Texto: {text}"
        )
        result = await self._call_with_retry(
            prompt, response_schema=_FINANCIAL_SCHEMA
        )
        data = json.loads(result)
        return ExtractedData(**data)

    async def extract_from_image(self, image_path: str) -> ExtractedData:
        prompt = (
            "Analizá la siguiente imagen. Si contiene un comprobante, ticket, factura "
            "o cualquier información financiera, extraé los datos correspondientes. "
            "Respondé únicamente con el JSON especificado en el schema."
        )
        result = await self._call_with_retry(
            prompt, file_path=image_path, response_schema=_FINANCIAL_SCHEMA
        )
        data = json.loads(result)
        return ExtractedData(**data)

    async def extract_from_document(self, document_path: str) -> ExtractedData:
        prompt = (
            "Analizá el siguiente documento. Si contiene una factura, recibo "
            "o cualquier información financiera, extraé los datos correspondientes. "
            "Respondé únicamente con el JSON especificado en el schema."
        )
        result = await self._call_with_retry(
            prompt, file_path=document_path, response_schema=_FINANCIAL_SCHEMA
        )
        data = json.loads(result)
        return ExtractedData(**data)

    async def transcribe_audio(self, audio_path: str) -> str:
        prompt = (
            "Transcribí el contenido del siguiente audio de forma literal y detallada."
        )
        result = await self._call_with_retry(prompt, file_path=audio_path)
        return result.strip()
