import asyncio
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from config import TELEGRAM_BOT_TOKEN, ALLOWED_EXTENSIONS, ALLOWED_MIME_TYPES, MAX_FILE_SIZE
from core.LoggerManagger import log
from core.Processer import Processer
from ia.base import ExtractedData, RegistroRechazadoError


class TelegramReceiver:
    def __init__(self, processer: Processer):
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN no está configurado en el archivo .env "
                "o variables de entorno."
            )

        self.processer = processer
        self.temp_dir = Path("temp_downloads")
        self.temp_dir.mkdir(exist_ok=True)

        self.app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        self._register_handlers()

    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("pendientes", self.handle_pendientes))
        self.app.add_handler(CommandHandler("limite", self.handle_limite))

        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text)
        )
        self.app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.app.add_handler(
            MessageHandler(filters.Document.ALL, self.handle_document)
        )
        self.app.add_handler(
            MessageHandler(filters.VOICE | filters.AUDIO, self.handle_audio)
        )
        self.app.add_handler(
            CallbackQueryHandler(self.handle_callback_query)
        )

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        await update.message.reply_text(
            "👋 **¡Hola! Soy Gasti, tu asistente para el control de tus finanzas.**\n\n"
            "Envíame la información de tus ingresos o gastos en cualquier formato:\n\n"
            "✍️ **Texto:** 'Fui a merendar y gaste $20000'\n"
            "📸 **Foto:** Envía una imagen de tu comprobante.\n"
            "📄 **Documento:** Envía una factura en formato PDF.\n"
            "🎙️ **Audio:** Dicta el gasto diciendo algo como 'Cargué nafta por $80000'.\n\n",
            parse_mode="Markdown",
        )

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        await update.message.reply_text(
            "📋 **Formatos y archivos soportados:**\n\n"
            "• **Imágenes:** JPG, JPEG, PNG (enviadas como foto o archivo).\n"
            "• **Documentos:** Facturas en formato PDF.\n"
            "• **Audio:** Notas de voz de Telegram o audios MP3, WAV, OGG, M4A.\n\n"
            "Cualquier otro formato será rechazado.",
            parse_mode="Markdown",
        )

    async def handle_pendientes(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        id_telegram, _ = self._user_info(update)
        pendientes = await asyncio.to_thread(
            self.processer.dao.listar_registros_pendientes, id_telegram
        )

        if not pendientes:
            await update.message.reply_text(
                "📋 No tenés registros pendientes."
            )
            return

        for reg in pendientes:
            emoji = "📈" if reg["tipo"] == "INGRESO" else "💸"
            fecha = reg["fecha_hora"].strftime("%d/%m %H:%M")
            mensaje = (
                f"{emoji} **{reg['tipo']}** — ${reg['monto']:,.2f}\n"
                f"📝 {reg['descripcion']}\n"
                f"🕐 {fecha}"
            )
            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ Confirmar",
                        callback_data=f"pendiente_confirmar_{reg['id']}",
                    ),
                    InlineKeyboardButton(
                        "❌ Cancelar",
                        callback_data=f"pendiente_cancelar_{reg['id']}",
                    ),
                ]
            ]
            await update.message.reply_text(
                mensaje,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )

    def _user_info(self, update: Update):
        user = update.effective_user
        return str(user.id), user.username

    def _parsear_monto(self, texto: str) -> float | None:
        t = (
            texto.strip()
            .replace("$", "")
            .replace(" ", "")
            .replace(".", "")
            .replace(",", ".")
        )
        try:
            return float(t)
        except ValueError:
            return None

    async def handle_limite(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        id_telegram, _ = self._user_info(update)
        estado = await self.processer.consultar_limite(id_telegram)
        if estado:
            mensaje = (
                f"💳 **Límite mensual actual:** ${estado['limite']:,.2f}\n\n"
                f"📉 Gastado este mes: ${estado['gastado']:,.2f}\n"
                f"📉 Restante: ${estado['restante']:,.2f}"
            )
        else:
            mensaje = "💳 **No tenés un límite mensual configurado.**"

        await update.message.reply_text(
            mensaje
            + "\n\nEnviá el monto del límite mensual (ej: 500000).\n"
            "Enviá **0** para desactivarlo.",
            parse_mode="Markdown",
        )
        context.user_data["esperando_limite"] = True

    async def _procesar_limite_recibido(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str
    ):
        id_telegram, _ = self._user_info(update)
        monto = self._parsear_monto(texto)
        if monto is None or monto < 0:
            await update.message.reply_text(
                "❌ No entendí ese monto. Enviá un número (ej: 500000) o "
                "**0** para desactivar el límite.",
                parse_mode="Markdown",
            )
            return

        limite = None if monto == 0 else monto
        try:
            await self.processer.configurar_limite_mensual(id_telegram, limite)
            context.user_data.pop("esperando_limite", None)

            if limite is None:
                await update.message.reply_text(
                    "✅ **Límite mensual desactivado.**", parse_mode="Markdown"
                )
                return

            estado = await self.processer.consultar_limite(id_telegram)
            if estado:
                await update.message.reply_text(
                    f"✅ **Límite mensual configurado:** ${limite:,.2f}\n\n"
                    f"📉 Gastado este mes: ${estado['gastado']:,.2f}\n"
                    f"📉 Restante: ${estado['restante']:,.2f}",
                    parse_mode="Markdown",
                )
            else:
                await update.message.reply_text(
                    f"✅ **Límite mensual configurado:** ${limite:,.2f}",
                    parse_mode="Markdown",
                )
        except Exception as e:
            log.error(
                f"(TelegramReceiver) Error al procesar límite de "
                f"{id_telegram}: {e}"
            )
            context.user_data.pop("esperando_limite", None)
            await update.message.reply_text(
                "❌ No pude guardar el límite. Intentalo de nuevo."
            )

    async def _procesar_y_mostrar(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        tipo: str,
        contenido: str,
    ):
        id_telegram, username = self._user_info(update)

        try:
            data, registro_id = await self.processer.procesar_mensaje(
                tipo, contenido, id_telegram, username
            )
        except RegistroRechazadoError as e:
            log.warning(
                f"(TelegramReceiver) Registro rechazado ({tipo}): {e.razon}"
            )
            await update.message.reply_text(
                "❌ No pude registrar eso como un gasto o ingreso.\n\n"
                f"Motivo: {e.razon}\n\n"
                "Enviame la información de otra forma (texto, foto del "
                "comprobante, PDF o nota de voz)."
            )
            return
        except Exception as e:
            log.error(
                f"(TelegramReceiver) Error en procesar_mensaje ({tipo}): {e}"
            )
            await update.message.reply_text(
                "❌ Ocurrió un error al procesar tu mensaje. Intentalo de nuevo."
            )
            return

        context.user_data["pending"] = data
        context.user_data["registro_id"] = registro_id
        await self._ask_for_confirmation(update, data, id_telegram)

    async def handle_text(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        text = update.message.text

        if context.user_data.get("esperando_limite"):
            log.info(
                f"(TelegramReceiver -> handle_text) Respuesta de límite de "
                f"@{update.effective_user.username}: {text}"
            )
            await self._procesar_limite_recibido(update, context, text)
            return

        log.info(
            f"(TelegramReceiver -> handle_text) Texto recibido de "
            f"@{update.effective_user.username}: {text}"
        )
        await self._procesar_y_mostrar(update, context, "texto", text)

    async def handle_photo(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        log.info(
            f"(TelegramReceiver -> handle_photo) Foto recibida de "
            f"@{update.effective_user.username}"
        )

        photo = update.message.photo[-1]

        if photo.file_size > MAX_FILE_SIZE:
            await update.message.reply_text(
                f"❌ La imagen supera los {MAX_FILE_SIZE // (1024*1024)} MB. "
                "Enviá un archivo más liviano."
            )
            return

        telegram_file = await context.bot.get_file(photo.file_id)
        file_path = self.temp_dir / f"{photo.file_id}.jpg"
        await telegram_file.download_to_drive(file_path)

        log.info(
            f"(TelegramReceiver -> handle_photo) Foto descargada en {file_path}"
        )
        await self._procesar_y_mostrar(update, context, "imagen", str(file_path))

    async def handle_document(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        doc = update.message.document
        file_name = doc.file_name
        mime_type = doc.mime_type

        log.info(
            f"(TelegramReceiver -> handle_document) Documento recibido de "
            f"@{update.effective_user.username}: {file_name} ({mime_type})"
        )

        ext = (
            file_name.split(".")[-1].lower()
            if file_name and "." in file_name
            else ""
        )
        is_valid = ext in ALLOWED_EXTENSIONS or mime_type in ALLOWED_MIME_TYPES
        if not is_valid:
            await update.message.reply_text(
                f"❌ El archivo **'{file_name}'** no está permitido.\n\n"
                "Por favor, envía imágenes (JPG, PNG) o documentos en PDF.",
                parse_mode="Markdown",
            )
            return

        if doc.file_size > MAX_FILE_SIZE:
            await update.message.reply_text(
                f"❌ El archivo supera los {MAX_FILE_SIZE // (1024*1024)} MB. "
                "Enviá un archivo más liviano."
            )
            return

        telegram_file = await context.bot.get_file(doc.file_id)
        file_path = self.temp_dir / f"{doc.file_id}_{file_name}"
        await telegram_file.download_to_drive(file_path)

        log.info(
            f"(TelegramReceiver -> handle_document) Documento descargado en "
            f"{file_path}"
        )
        await self._procesar_y_mostrar(
            update, context, "documento", str(file_path)
        )

    async def handle_audio(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        is_voice = update.message.voice is not None
        audio_obj = update.message.voice if is_voice else update.message.audio

        log.info(
            f"(TelegramReceiver -> handle_audio) Audio recibido de "
            f"@{update.effective_user.username} (Nota de voz: {is_voice})"
        )

        if hasattr(audio_obj, "mime_type") and audio_obj.mime_type:
            if audio_obj.mime_type not in ALLOWED_MIME_TYPES:
                file_name = getattr(audio_obj, "file_name", "")
                ext = (
                    file_name.split(".")[-1].lower()
                    if file_name and "." in file_name
                    else ""
                )
                if ext not in ALLOWED_EXTENSIONS:
                    await update.message.reply_text(
                        "❌ Formato de audio no soportado.\n"
                        "Por favor envía notas de voz directas de Telegram o "
                        "audios en formato MP3, WAV, OGG o M4A."
                    )
                    return

        if audio_obj.file_size > MAX_FILE_SIZE:
            await update.message.reply_text(
                f"❌ El archivo de audio supera los {MAX_FILE_SIZE // (1024*1024)} MB. "
                "Enviá un archivo más liviano."
            )
            return

        ext = "ogg" if is_voice else "mp3"
        file_name = getattr(audio_obj, "file_name", f"{audio_obj.file_id}.{ext}")

        telegram_file = await context.bot.get_file(audio_obj.file_id)
        file_path = self.temp_dir / f"{audio_obj.file_id}_{file_name}"
        await telegram_file.download_to_drive(file_path)

        log.info(
            f"(TelegramReceiver -> handle_audio) Audio descargado en "
            f"{file_path}"
        )
        await self._procesar_y_mostrar(
            update, context, "audio", str(file_path)
        )

    async def _ask_for_confirmation(
        self, update: Update, data: ExtractedData, id_telegram: str
    ):
        emoji_tipo = "📈" if data.tipo == "INGRESO" else "💸"
        mensaje = (
            "🔍 **Datos extraídos:**\n\n"
            f"{emoji_tipo} **Tipo:** {data.tipo}\n"
            f"📝 **Concepto:** {data.concepto}\n"
            f"💵 **Monto:** ${data.monto:,.2f}\n"
            f"🏷️ **Categoría:** {data.categoria}\n\n"
            "¿La información es correcta para guardarla?"
        )

        if data.tipo == "GASTO":
            estado = await self.processer.consultar_limite(
                id_telegram, data.monto
            )
            if estado and estado["supera"]:
                mensaje += (
                    f"\n\n⚠️ **Con este gasto superás tu límite mensual "
                    f"de ${estado['limite']:,.2f}.**\n"
                    f"Ya gastaste ${estado['gastado']:,.2f} este mes."
                )

        keyboard = [
            [
                InlineKeyboardButton(
                    "Sí, es correcto ✅", callback_data="gasto_confirmado"
                ),
                InlineKeyboardButton(
                    "No, cancelar ❌", callback_data="gasto_cancelado"
                ),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            mensaje, reply_markup=reply_markup, parse_mode="Markdown"
        )

    async def _aviso_supero_limite(
        self, query, id_telegram: str, registro_id: int
    ):
        try:
            if await self.processer.detectar_cruce_limite(
                id_telegram, registro_id
            ):
                estado = await self.processer.consultar_limite(id_telegram)
                if estado:
                    await query.message.reply_text(
                        f"⚠️ **¡Superaste tu límite mensual!**\n\n"
                        f"Límite: ${estado['limite']:,.2f}\n"
                        f"Gastado este mes: ${estado['gastado']:,.2f}",
                        parse_mode="Markdown",
                    )
        except Exception as e:
            log.error(
                f"(TelegramReceiver) Error al enviar alerta de límite: {e}"
            )

    async def handle_callback_query(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        query = update.callback_query
        await query.answer()
        id_telegram = str(query.from_user.id)

        # Flujo desde /pendientes: registro_id viene en el callback_data
        if query.data.startswith("pendiente_confirmar_"):
            registro_id = int(query.data.split("_")[-1])
            try:
                await self.processer.confirmar_guardado(registro_id)
                await query.edit_message_text(
                    f"✅ **¡Gasto guardado con éxito!** (ID: {registro_id}) 🎉",
                    parse_mode="Markdown",
                )
                await self._aviso_supero_limite(
                    query, id_telegram, registro_id
                )
            except Exception as e:
                log.error(
                    f"(TelegramReceiver) Error al confirmar desde /pendientes: {e}"
                )
                try:
                    await self.processer.marcar_fallido(registro_id)
                except Exception:
                    pass
                await query.edit_message_text(
                    "❌ Ocurrió un error al guardar. Intentalo de nuevo."
                )
            return

        if query.data.startswith("pendiente_cancelar_"):
            registro_id = int(query.data.split("_")[-1])
            try:
                await self.processer.cancelar_registro(registro_id)
                await query.edit_message_text(
                    "❌ **Operación cancelada. Si los datos eran incorrectos, intenta enviarlos de otra forma.**", parse_mode="Markdown"
                )
            except Exception as e:
                log.error(
                    f"(TelegramReceiver) Error al cancelar desde /pendientes: {e}"
                )
                try:
                    await self.processer.marcar_fallido(registro_id)
                except Exception:
                    pass
                await query.edit_message_text(
                    "❌ Ocurrió un error al cancelar. Intentalo de nuevo."
                )
            return

        # Flujo inline: usar context.user_data
        data: ExtractedData = context.user_data.get("pending")
        registro_id: int = context.user_data.get("registro_id")
        if not data or not registro_id:
            await query.edit_message_text(
                "❌ No hay datos pendientes para confirmar. "
                "Enviá el gasto nuevamente."
            )
            return

        if query.data == "gasto_confirmado":
            try:
                await self.processer.confirmar_guardado(registro_id)
                await query.edit_message_text(
                    f"✅ **¡Gasto guardado con éxito!** (ID: {registro_id}) 🎉",
                    parse_mode="Markdown",
                )
                await self._aviso_supero_limite(
                    query, id_telegram, registro_id
                )
            except Exception as e:
                log.error(
                    f"(TelegramReceiver) Error al confirmar guardado: {e}"
                )
                try:
                    await self.processer.marcar_fallido(registro_id)
                except Exception:
                    pass
                await query.edit_message_text(
                    "❌ Ocurrió un error al guardar. Intentalo de nuevo."
                )

        elif query.data == "gasto_cancelado":
            try:
                await self.processer.cancelar_registro(registro_id)
                await query.edit_message_text(
                    "❌ **Operación cancelada. Si los datos eran incorrectos, intenta enviarlos de otra forma.**", parse_mode="Markdown"
                )
            except Exception as e:
                log.error(
                    f"(TelegramReceiver) Error al cancelar registro: {e}"
                )
                try:
                    await self.processer.marcar_fallido(registro_id)
                except Exception:
                    pass
                await query.edit_message_text(
                    "❌ Ocurrió un error al cancelar. Intentalo de nuevo."
                )

        context.user_data.pop("pending", None)
        context.user_data.pop("registro_id", None)

    def run(self):
        log.info(
            "(TelegramReceiver -> run) Iniciando el bot de Telegram..."
        )
        self.app.run_polling()
