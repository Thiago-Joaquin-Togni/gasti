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
    ) -> tuple[ExtractedData, int]:
        log.info(
            f"(Processer) Procesando mensaje tipo={tipo} de usuario={id_telegram}"
        )

        await asyncio.to_thread(
            self.dao.registrar_usuario, id_telegram, username
        )

        try:
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
        except Exception as e:
            log.error(
                f"(Processer) Fallo en extracción IA ({tipo}): {e}"
            )
            registro_id = await asyncio.to_thread(
                self.dao.insertar_registro,
                id_telegram,
                0,
                contenido,
                "DESCONOCIDO",
                None,
            )
            await asyncio.to_thread(
                self.dao.actualizar_estado_registro, registro_id, "FALLIDO"
            )
            raise

        log.info(
            f"(Processer) Extracción completada: {data.tipo} ${data.monto} "
            f"— {data.concepto} [{data.categoria}]"
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

        log.info(
            f"(Processer) Registro creado con estado PENDIENTE: id={registro_id}"
        )
        return data, registro_id

    async def confirmar_guardado(self, registro_id: int) -> None:
        log.info(
            f"(Processer) Confirmando registro id={registro_id}"
        )
        await asyncio.to_thread(
            self.dao.actualizar_estado_registro, registro_id, "COMPLETADO"
        )
        log.info(f"(Processer) Registro {registro_id} confirmado")

    async def cancelar_registro(self, registro_id: int) -> None:
        log.info(
            f"(Processer) Cancelando registro id={registro_id}"
        )
        await asyncio.to_thread(
            self.dao.actualizar_estado_registro, registro_id, "CANCELADO"
        )
        log.info(f"(Processer) Registro {registro_id} cancelado")

    async def marcar_fallido(self, registro_id: int) -> None:
        log.info(
            f"(Processer) Marcando registro id={registro_id} como FALLIDO"
        )
        await asyncio.to_thread(
            self.dao.actualizar_estado_registro, registro_id, "FALLIDO"
        )
        log.info(f"(Processer) Registro {registro_id} marcado como FALLIDO")
