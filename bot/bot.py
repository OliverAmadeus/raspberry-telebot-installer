
import logging
import os

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from terminal import execute_command, get_working_directory
from upterm import start_upterm, stop_upterm, status_upterm


# ==========================================
# CONFIGURACION
# ==========================================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

AUTHORIZED_USER_ID = os.getenv(
    "TELEGRAM_AUTHORIZED_USER_ID", ""
).strip()


# ==========================================
# REGISTRO
# ==========================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# Evitar que HTTPX registre URL que contienen
# el token de autenticación de Telegram.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# ==========================================
# AUTORIZACION
# ==========================================

def authorized(update: Update) -> bool:

    user = update.effective_user
    chat = update.effective_chat

    if user is None or chat is None:
        return False

    if not AUTHORIZED_USER_ID.isdigit():
        return False

    return (
        user.id == int(AUTHORIZED_USER_ID)
        and chat.type == "private"
    )


# ==========================================
# MENSAJES LARGOS
# ==========================================

async def send_long_message(update: Update, text: str):

    if not update.message:
        return

    if not text:
        text = "(Sin salida)"

    max_length = 3500
    chunk = ""
    current_length = 0

    for character in text:

        char_length = len(
            character.encode("utf-16-le")
        ) // 2

        if current_length + char_length > max_length:
            await update.message.reply_text(chunk)
            chunk = ""
            current_length = 0

        chunk += character
        current_length += char_length

    if chunk:
        await update.message.reply_text(chunk)


# ==========================================
# START
# ==========================================

async def start_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not authorized(update):
        return

    await update.message.reply_text(
        "Raspberry Telebot está activo.\n\n"
        "COMANDOS:\n"
        "/terminal comando - Ejecutar Linux\n"
        "/pwd - Directorio actual\n"
        "/upterm iniciar - Iniciar terminal remota\n"
        "/upterm estado - Consultar sesión\n"
        "/upterm detener - Cerrar sesión\n"
        "/ayuda - Mostrar ayuda"
    )


# ==========================================
# AYUDA
# ==========================================

async def help_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not authorized(update):
        return

    await update.message.reply_text(
        "RASPBERRY TELEBOT\n\n"
        "TERMINAL LINUX:\n"
        "/terminal ls -la\n"
        "/terminal uname -a\n"
        "/terminal df -h\n"
        "/terminal cd /home\n"
        "/pwd\n\n"
        "UPTERM:\n"
        "/upterm iniciar\n"
        "/upterm estado\n"
        "/upterm detener\n\n"
        "Upterm permite acceso interactivo remoto.\n"
        "El identificador de conexión debe mantenerse "
        "privado: cualquiera que lo obtenga puede entrar "
        "mientras la sesión esté activa.\n\n"
        "SFTP/SCP está desactivado."
    )


# ==========================================
# PWD
# ==========================================

async def pwd_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not authorized(update):
        return

    user_id = str(update.effective_user.id)

    await update.message.reply_text(
        get_working_directory(user_id)
    )


# ==========================================
# TERMINAL LINUX
# ==========================================

async def terminal_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not authorized(update) or not update.message:
        return

    message = update.message.text or ""
    parts = message.split(maxsplit=1)

    command = parts[1].strip() if len(parts) > 1 else ""

    if not command:
        await update.message.reply_text(
            "Ejemplo: /terminal ls -la"
        )
        return

    user_id = str(update.effective_user.id)

    await update.message.reply_text(
        f"Ejecutando:\n{command}"
    )

    try:
        result = await execute_command(user_id, command)
        await send_long_message(update, result)

    except Exception:
        logger.exception("Error ejecutando comando")
        await update.message.reply_text(
            "Se produjo un error al ejecutar el comando."
        )


# ==========================================
# CONTROL UPT​​ERM
# ==========================================

async def upterm_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not authorized(update) or not update.message:
        return

    action = (
        context.args[0].lower()
        if context.args
        else ""
    )

    if action == "iniciar":

        await update.message.reply_text(
            "Iniciando sesión Upterm..."
        )

        try:
            session = await start_upterm()

            message = (
                "UPTERM ACTIVO\n\n"
                f"Sesión: {session['name']}\n\n"
            )

            if session.get("joinCommand"):
                message += (
                    "Comando de conexión:\n"
                    f"{session['joinCommand']}\n\n"
                )

            if session.get("sshCommand"):
                message += (
                    "Comando SSH:\n"
                    f"{session['sshCommand']}\n\n"
                )

            message += (
                "Mantén estos datos privados. "
                "Cualquier persona que los obtenga "
                "podrá entrar mientras la sesión esté activa.\n"
                "SFTP/SCP: desactivado."
            )

            await send_long_message(update, message)

        except Exception:
            logger.exception("Error iniciando Upterm")
            await update.message.reply_text(
                "No se pudo iniciar Upterm. "
                "Revisa el registro del servicio."
            )

    elif action == "estado":

        try:
            result = await status_upterm()
            await update.message.reply_text(result)

        except Exception:
            logger.exception("Error consultando Upterm")
            await update.message.reply_text(
                "No se pudo consultar el estado de Upterm."
            )

    elif action == "detener":

        try:
            result = await stop_upterm()
            await update.message.reply_text(result)

        except Exception:
            logger.exception("Error deteniendo Upterm")
            await update.message.reply_text(
                "No se pudo detener Upterm."
            )

    else:

        await update.message.reply_text(
            "Uso:\n"
            "/upterm iniciar\n"
            "/upterm estado\n"
            "/upterm detener"
        )


# ==========================================
# INICIAR BOT
# ==========================================

def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "Falta TELEGRAM_BOT_TOKEN."
        )

    if not AUTHORIZED_USER_ID.isdigit():
        raise RuntimeError(
            "TELEGRAM_AUTHORIZED_USER_ID debe ser numérico."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start_handler)
    )

    application.add_handler(
        CommandHandler("ayuda", help_handler)
    )

    application.add_handler(
        CommandHandler("pwd", pwd_handler)
    )

    application.add_handler(
        CommandHandler("terminal", terminal_handler)
    )

    application.add_handler(
        CommandHandler("upterm", upterm_handler)
    )

    logger.info("Raspberry Telebot iniciado.")

    application.run_polling()


if __name__ == "__main__":
    main()
