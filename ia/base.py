from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ExtractedData:
    concepto: str
    monto: float
    tipo: str  # GASTO | INGRESO
    categoria: str
    respuesta: str
    descripcion_detallada: Optional[str] = None
    es_registro_valido: bool = True
    razon_rechazo: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class RegistroRechazadoError(Exception):
    """Se lanza cuando la extracción es válida pero el registro fue rechazado
    por la IA o por las validaciones deterministas de cordura."""

    def __init__(self, razon: str, respuesta: Optional[str] = None):
        self.razon = razon
        self.respuesta = respuesta
        super().__init__(razon)


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
