
import logging
import os

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from terminal import execute_command, get_working_directory


# Configuración
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
AUTHORIZED_USER_ID = os.getenv("TELEGRAM_AUTHORIZED_USER_ID", "").strip()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


def authorized(update: Update) -> bool:
    """Comprueba que el mensaje provenga del usuario autorizado."""

    user = update.effective_user

    if user is None or not AUTHORIZED_USER_ID.isdigit():
        return False

    return user.id == int(AUTHORIZED_USER_ID)


async def send_long_message(update: Update, text: str):
    """Divide respuestas largas para respetar el límite de Telegram."""

    if not update.message:
        return

    if not text:
        text = "(Sin salida)"

    max_length = 4000

    for position in range(0, len(text), max_length):
        await update.message.reply_text(text[position:position + max_length])


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
        "del usuario Linux que ejecuta el bot."
    )


async def pwd_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not authorized(update):
        return

    user_id = str(update.effective_user.id)
    directory = get_working_directory(user_id)

    await update.message.reply_text(directory)


async def terminal_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not authorized(update):
        return

    message = update.message.text or ""
    command = message.partition(" ")[2].strip()

    if not command:
        await update.message.reply_text(
            "Indica un comando.\nEjemplo: /terminal ls -la"
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

    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("ayuda", help_handler))
    application.add_handler(CommandHandler("pwd", pwd_handler))
    application.add_handler(CommandHandler("terminal", terminal_handler))

    logger.info("Raspberry Telebot iniciado.")

    application.run_polling()


if __name__ == "__main__":
    main()
