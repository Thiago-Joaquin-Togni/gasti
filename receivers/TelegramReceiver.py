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
from config import TELEGRAM_BOT_TOKEN, ALLOWED_EXTENSIONS, ALLOWED_MIME_TYPES
from core.LoggerManagger import log

class TelegramReceiver:
    def __init__(self):
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN no está configurado en el archivo .env o variables de entorno.")
        
        # Inicializar la aplicación del bot de Telegram
        self.app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Configurar los manejadores de eventos
        self._register_handlers()

    def _register_handlers(self):
        """Registra los manejadores para los distintos tipos de comandos e inputs"""
        # Comandos
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        
        # Mensajes de texto 
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        
        # Fotos 
        self.app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        
        # Documentos 
        self.app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        
        # Audio
        self.app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self.handle_audio))
        
        # Manejador de botones interactivos (Confirmación / Cancelación)
        self.app.add_handler(CallbackQueryHandler(self.handle_callback_query))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Acción al ejecutar el comando /start"""
        await update.message.reply_text(
            "👋 **¡Hola! Soy Gasti, tu asistente para el control de tus finanzas.**\n\n"
            "Envíame la información de tus ingresos o gastos en cualquier formato:\n\n"
            "✍️ **Texto:** 'Fui a merendar y gaste $20000'\n"
            "📸 **Foto:** Envía una imagen de tu comprobante.\n"
            "📄 **Documento:** Envía una factura en formato PDF.\n"
            "🎙️ **Audio:** Dicta el gasto diciendo algo como 'Cargué nafta por $80000'.\n\n",
            parse_mode="Markdown"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Acción al ejecutar el comando /help"""
        await update.message.reply_text(
            "📋 **Formatos y archivos soportados:**\n\n"
            "• **Imágenes:** JPG, JPEG, PNG (enviadas como foto o archivo).\n"
            "• **Documentos:** Facturas en formato PDF.\n"
            "• **Audio:** Notas de voz de Telegram o audios MP3, WAV, OGG, M4A.\n\n"
            "Cualquier otro formato será rechazado.",
            parse_mode="Markdown"
        )

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejador para mensajes de texto"""
        text = update.message.text
        log.info(f"(TelegramReceiver -> handle_text)Texto recibido de @{update.effective_user.username}: {text}")
        
        # TODO: En la próxima iteración, enviaremos esto a la IA de Gemini para análisis real.
        # Por ahora creamos un mock de la extracción
        gasto_mock = {
            "concepto": text,
            "monto": "Por determinar",
            "categoria": "General"
        }
        
        await self._ask_for_confirmation(update, gasto_mock)

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejador para imágenes enviadas como foto"""
        log.info(f"(TelegramReceiver -> handle_photo) Foto recibida de @{update.effective_user.username}")
        
        # Telegram envía una lista de fotos con distintos tamaños. Obtenemos la más grande (última)
        photo = update.message.photo[-1]
        file_id = photo.file_id
        
        # Descargar la foto 
        telegram_file = await context.bot.get_file(file_id)
        file_path = self.temp_dir / f"{file_id}.jpg"
        await telegram_file.download_to_drive(file_path)
        
        log.info(f"(TelegramReceiver -> handle_photo) Foto descargada exitosamente en {file_path}")
        
        # TODO: Integración con la IA 
        gasto_mock = {
            "concepto": "Compra en Supermercado (desde imagen)",
            "monto": "$14,890.00",
            "categoria": "Alimentos/Supermercado"
        }
        await self._ask_for_confirmation(update, gasto_mock)

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejador para documentos (por ejemplo, PDFs u otras extensiones)"""
        doc = update.message.document
        file_name = doc.file_name
        mime_type = doc.mime_type
        
        log.info(f"(TelegramReceiver -> handle_document) Documento recibido de @{update.effective_user.username}: {file_name} ({mime_type})")
        
        # Obtener extensión
        ext = file_name.split(".")[-1].lower() if file_name and "." in file_name else ""
        
        # Validar tipo de archivo
        is_valid = ext in ALLOWED_EXTENSIONS or mime_type in ALLOWED_MIME_TYPES
        if not is_valid:
            await update.message.reply_text(
                f"❌ El archivo **'{file_name}'** no está permitido.\n\n"
                "Por favor, envía imágenes (JPG, PNG) o documentos en PDF.",
                parse_mode="Markdown"
            )
            return

        # Descargar el documento
        file_id = doc.file_id
        telegram_file = await context.bot.get_file(file_id)
        file_path = self.temp_dir / f"{file_id}_{file_name}"
        await telegram_file.download_to_drive(file_path)
        
        log.info(f"(TelegramReceiver -> handle_document) Documento descargado exitosamente en {file_path}")
        
        # TODO: Integración con la IA 
        gasto_mock = {
            "concepto": f"Factura {file_name}",
            "monto": "$5,200.00",
            "categoria": "Servicios"
        }
        await self._ask_for_confirmation(update, gasto_mock)

    async def handle_audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manejador para notas de voz o archivos de audio"""
        is_voice = update.message.voice is not None
        audio_obj = update.message.voice if is_voice else update.message.audio
        
        log.info(f"(TelegramReceiver -> handle_audio) Audio recibido de @{update.effective_user.username} (Nota de voz: {is_voice})")
        
        # Validar tipo de audio (si tiene tipo MIME)
        if hasattr(audio_obj, "mime_type") and audio_obj.mime_type:
            if audio_obj.mime_type not in ALLOWED_MIME_TYPES:
                # Comprobar extensión si es un archivo de audio con nombre
                file_name = getattr(audio_obj, "file_name", "")
                ext = file_name.split(".")[-1].lower() if file_name and "." in file_name else ""
                if ext not in ALLOWED_EXTENSIONS:
                    await update.message.reply_text(
                        "❌ Formato de audio no soportado.\n"
                        "Por favor envía notas de voz directas de Telegram o audios en formato MP3, WAV, OGG o M4A."
                    )
                    return
        
        # Descargar audio
        file_id = audio_obj.file_id
        ext = "ogg" if is_voice else "mp3"
        file_name = getattr(audio_obj, "file_name", f"{file_id}.{ext}")
        
        telegram_file = await context.bot.get_file(file_id)
        file_path = self.temp_dir / f"{file_id}_{file_name}"
        await telegram_file.download_to_drive(file_path)
        
        log.info(f"(TelegramReceiver -> handle_audio) Audio descargado exitosamente en {file_path}")
        
        # TODO: Integración con la IA 
        gasto_mock = {
            "concepto": "Gasto dictado (Voz)",
            "monto": "$3,500.00",
            "categoria": "Transporte"
        }
        await self._ask_for_confirmation(update, gasto_mock)

    async def _ask_for_confirmation(self, update: Update, gasto: dict):
        """Muestra los datos extraídos del gasto al usuario y pide confirmación"""
        mensaje = (
            "🔍 **Datos extraídos:**\n\n"
            f"📝 **Concepto:** {gasto.get('concepto')}\n"
            f"💵 **Monto:** {gasto.get('monto')}\n"
            f"🏷️ **Categoría:** {gasto.get('categoria')}\n\n"
            "¿La información extraída es correcta para guardarla?"
        )
        
        # Botones en línea para confirmar o cancelar
        keyboard = [
            [
                InlineKeyboardButton("Sí, es correcto ✅", callback_data="gasto_confirmado"),
                InlineKeyboardButton("No, cancelar/corregir ❌", callback_data="gasto_cancelado")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(mensaje, reply_markup=reply_markup, parse_mode="Markdown")

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja las interacciones de los botones de confirmación/cancelación"""
        query = update.callback_query
        # Es necesario responder al callback query para quitar el estado "cargando" del botón en Telegram
        await query.answer()
        
        action = query.data
        original_text = query.message.text
        
        if action == "gasto_confirmado":
            await query.edit_message_text(
                text=f"{original_text}\n\n✅ **¡Gasto guardado con éxito!** 🎉",
                parse_mode="Markdown"
            )
            # TODO: Aquí se guardaría en base de datos o almacenamiento final.
            
        elif action == "gasto_cancelado":
            await query.edit_message_text(
                text=f"{original_text}\n\n❌ **Operación cancelada.** Puedes volver a intentarlo enviando el gasto nuevamente de otra forma.",
                parse_mode="Markdown"
            )

    def run(self):
        """Inicia el bot y se queda escuchando actualizaciones (polling)"""
        log.info("(TelegramReceiver -> run) Iniciando el bot de Telegram...")
        self.app.run_polling()

if __name__ == "__main__":
    receiver = TelegramReceiver()
    receiver.run()
