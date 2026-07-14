from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ExtractedData:
    concepto: str
    monto: float
    tipo: str  # GASTO | INGRESO
    categoria: str
    descripcion_detallada: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class BaseAIExtractor(ABC):
    """
    Cada proveedor debe implementarestos métodos. 
    Los receptores y el Processer consumen siempre esta interfaz.
    """

    @abstractmethod
    async def extract_from_text(self, text: str) -> ExtractedData:
        """Extrae datos desde texto plano."""
        ...

    @abstractmethod
    async def extract_from_image(self, image_path: str) -> ExtractedData:
        """Extrae datos desde una imagen."""
        ...

    @abstractmethod
    async def extract_from_document(self, document_path: str) -> ExtractedData:
        """Extrae datos desde un documento (PDF)."""
        ...

    @abstractmethod
    async def transcribe_audio(self, audio_path: str) -> str:
        """Transcribe audio a texto. Luego usa extract_from_text sobre el resultado."""
        ...
