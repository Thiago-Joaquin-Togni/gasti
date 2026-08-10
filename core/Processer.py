import asyncio

from core.DAO import DAO
from core.LoggerManagger import log
from ia.base import BaseAIExtractor, ExtractedData, RegistroRechazadoError


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

        es_valido = self._validar_registro(data)
        if not es_valido or not data.es_registro_valido:
            razon = data.razon_rechazo or "Registro inválido."
            respuesta = data.respuesta if not data.es_registro_valido else None
            await self._rechazar_registro(
                id_telegram, contenido, razon, respuesta
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

    def _validar_registro(self, data: ExtractedData) -> bool:
        if data.tipo not in ("GASTO", "INGRESO"):
            return False
        if not isinstance(data.monto, (int, float)) or not data.monto > 0:
            return False
        if not data.categoria:
            return False
        return True

    async def _rechazar_registro(
        self,
        id_telegram: str,
        contenido: str,
        razon: str,
        respuesta: str | None = None,
    ) -> None:
        registro_id = await asyncio.to_thread(
            self.dao.insertar_registro,
            id_telegram,
            0,
            razon,
            "DESCONOCIDO",
            None,
        )
        await asyncio.to_thread(
            self.dao.actualizar_estado_registro, registro_id, "RECHAZADO"
        )
        log.warning(
            f"(Processer) Registro rechazado id={registro_id}: {razon}"
        )
        raise RegistroRechazadoError(razon, respuesta=respuesta)

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

    async def configurar_limite_mensual(
        self, id_telegram: str, limite: float | None
    ) -> None:
        log.info(
            f"(Processer) Configurando límite mensual para {id_telegram}: {limite}"
        )
        await asyncio.to_thread(
            self.dao.actualizar_limite_mensual, id_telegram, limite
        )
        log.info(f"(Processer) Límite mensual configurado para {id_telegram}: {limite}")

    async def consultar_limite(
        self, id_telegram: str, monto_extra: float = 0.0
    ) -> dict | None:
        usuario = await asyncio.to_thread(self.dao.obtener_usuario, id_telegram)
        limite = usuario.get("limite_mensual") if usuario else None
        if limite is None:
            return None
        gastado = await asyncio.to_thread(self.dao.gasto_mensual, id_telegram)
        limite = float(limite)
        gastado = float(gastado)
        return {
            "limite": limite,
            "gastado": gastado,
            "restante": limite - gastado,
            "supera": gastado + monto_extra > limite,
        }

    async def detectar_cruce_limite(
        self, id_telegram: str, registro_id: int
    ) -> bool:
        estado = await self.consultar_limite(id_telegram)
        if not estado:
            return False
        registro = await asyncio.to_thread(
            self.dao.obtener_registro_por_id, registro_id
        )
        if not registro or registro.get("tipo") != "GASTO":
            return False
        monto = float(registro.get("monto") or 0)
        antes = estado["gastado"] - monto
        return antes <= estado["limite"] < estado["gastado"]
