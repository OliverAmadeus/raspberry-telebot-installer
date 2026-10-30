
import logging
import os

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from terminal import execute_command, get_working_directory


# ==========================================
# CONFIGURACION
# ==========================================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
AUTHORIZED_USER_ID = os.getenv(
    "TELEGRAM_AUTHORIZED_USER_ID", ""
).strip()


# ==========================================
# REGISTRO DE EVENTOS
# ==========================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# ==========================================
# AUTORIZACION
# ==========================================

def authorized(update: Update) -> bool:
    """
    Permite únicamente al usuario configurado
    y desde una conversación privada.
    """

    user = update.effective_user
    chat = update.effective_chat

    if user is None or chat is None:
        return False

    if not AUTHORIZED_USER_ID.isdigit():
        return False

    if user.id != int(AUTHORIZED_USER_ID):
        return False

    if chat.type != "private":
        return False

    return True


# ==========================================
# MENSAJES LARGOS
# ==========================================

async def send_long_message(update: Update, text: str):
    """Divide respuestas para respetar el límite de Telegram."""

    if not update.message:
        return

    if not text:
        text = "(Sin salida)"

    max_length = 4000

    for position in range(0, len(text), max_length):
        await update.message.reply_text(
            text[position:position + max_length]
        )


# ==========================================
# COMANDO START
# ==========================================

async def start_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not authorized(update):
        return

    await update.message.reply_text(
        "Raspberry Telebot está activo.\n\n"
        "Comandos disponibles:\n"
        "/terminal comando - Ejecutar comando Linux\n"
        "/pwd - Mostrar directorio actual\n"
        "/ayuda - Mostrar ayuda"
    )


# ==========================================
# COMANDO AYUDA
# ==========================================

async def help_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not authorized(update):
        return

    await update.message.reply_text(
        "TERMINAL REMOTA RASPBERRY\n\n"
        "Ejemplos:\n"
        "/terminal ls -la\n"
        "/terminal uname -a\n"
        "/terminal df -h\n"
        "/terminal systemctl status ssh\n"
        "/terminal cd /home\n"
        "/pwd\n\n"
        "Los comandos se ejecutan con los permisos "
        "del usuario Linux que ejecuta el bot.\n\n"
        "IMPORTANTE:\n"
        "El bot permite ejecutar comandos Linux arbitrarios. "
        "Utilízalo únicamente desde tu chat privado autorizado."
    )


# ==========================================
# COMANDO PWD
# ==========================================

async def pwd_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not authorized(update):
        return

    user_id = str(update.effective_user.id)

    directory = get_working_directory(user_id)

    await update.message.reply_text(directory)


# ==========================================
# COMANDO TERMINAL
# ==========================================

async def terminal_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not authorized(update):
        return

    if not update.message:
        return

    message = update.message.text or ""
    command = message.partition(" ")[2].strip()

    if not command:
        await update.message.reply_text(
            "Indica un comando.\n"
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
# INICIAR BOT
# ==========================================

def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "Falta TELEGRAM_BOT_TOKEN en la configuración."
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

    logger.info("Raspberry Telebot iniciado.")

    application.run_polling()


if __name__ == "__main__":
    main()
