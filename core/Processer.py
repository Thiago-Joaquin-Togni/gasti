import asyncio

from core.DAO import DAO
from core.LoggerManagger import log
from ia.base import BaseAIExtractor, ExtractedData


class Processer:
    def __init__(self, extractor: BaseAIExtractor, dao: DAO):
        self.extractor = extractor
        self.dao = dao

    async def procesar_mensaje(
        self,
        tipo: str,
        contenido: str,
        id_telegram: str,
        username: str = None,
    ) -> ExtractedData:
        log.info(
            f"(Processer) Procesando mensaje tipo={tipo} de usuario={id_telegram}"
        )

        await asyncio.to_thread(
            self.dao.registrar_usuario, id_telegram, username
        )

        if tipo == "texto":
            data = await self.extractor.extract_from_text(contenido)
        elif tipo == "imagen":
            data = await self.extractor.extract_from_image(contenido)
        elif tipo == "documento":
            data = await self.extractor.extract_from_document(contenido)
        elif tipo == "audio":
            texto = await self.extractor.transcribe_audio(contenido)
            data = await self.extractor.extract_from_text(texto)
        else:
            raise ValueError(f"Tipo de mensaje no soportado: {tipo}")

        log.info(
            f"(Processer) Extracción completada: {data.tipo} ${data.monto} "
            f"— {data.concepto} [{data.categoria}]"
        )
        return data

    async def confirmar_guardado(
        self, data: ExtractedData, id_telegram: str
    ) -> int:
        log.info(
            f"(Processer) Confirmando guardado para usuario={id_telegram}: "
            f"{data.tipo} ${data.monto} — {data.concepto}"
        )

        categoria = await asyncio.to_thread(
            self.dao.obtener_categoria_por_nombre, data.categoria
        )
        categoria_id = categoria["id"] if categoria else None

        descripcion = data.concepto
        if data.descripcion_detallada:
            descripcion = f"{data.concepto} — {data.descripcion_detallada}"

        registro_id = await asyncio.to_thread(
            self.dao.insertar_registro,
            id_telegram,
            data.monto,
            descripcion,
            data.tipo,
            categoria_id,
        )

        log.info(f"(Processer) Registro guardado exitosamente: id={registro_id}")
        return registro_id
