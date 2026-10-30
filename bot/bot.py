
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

BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "",
).strip()

AUTHORIZED_USER_ID = os.getenv(
    "TELEGRAM_AUTHORIZED_USER_ID",
    "",
).strip()

AUTHORIZED_USER_ID_INT = (
    int(AUTHORIZED_USER_ID)
    if AUTHORIZED_USER_ID.isdigit()
    else None
)


# ==========================================
# REGISTRO
# ==========================================

logging.basicConfig(
    format=(
        "%(asctime)s - %(name)s - "
        "%(levelname)s - %(message)s"
    ),
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# Evitar que HTTPX registre URLs que contienen
# el token de autenticación de Telegram.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# ==========================================
# AUTORIZACION
# ==========================================

def authorized(update: Update) -> bool:
    """
    Permite únicamente al usuario autorizado
    desde un chat privado de Telegram.
    """

    user = update.effective_user
    chat = update.effective_chat

    if user is None or chat is None:
        return False

    if AUTHORIZED_USER_ID_INT is None:
        return False

    return (
        user.id == AUTHORIZED_USER_ID_INT
        and chat.type == "private"
    )


# ==========================================
# VALIDAR MENSAJE
# ==========================================

def valid_message(update: Update) -> bool:
    return (
        authorized(update)
        and update.message is not None
    )


# ==========================================
# MENSAJES LARGOS
# ==========================================

async def send_long_message(
    update: Update,
    text: str,
):
    """
    Divide los mensajes para respetar el límite
    de longitud de Telegram.
    """

    if update.message is None:
        return

    if not text:
        text = "(Sin salida)"

    max_length = 3500
    chunk = []
    current_length = 0

    for character in text:

        char_length = len(
            character.encode("utf-16-le")
        ) // 2

        if (
            current_length + char_length > max_length
            and chunk
        ):
            await update.message.reply_text(
                "".join(chunk)
            )

            chunk = []
            current_length = 0

        chunk.append(character)
        current_length += char_length

    if chunk:
        await update.message.reply_text(
            "".join(chunk)
        )


# ==========================================
# START
# ==========================================

async def start_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not valid_message(update):
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

    if not valid_message(update):
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
        "Upterm permite acceso interactivo remoto.\n\n"
        "IMPORTANTE:\n"
        "El identificador y los comandos de conexión "
        "deben mantenerse privados. Cualquier persona "
        "que los obtenga puede entrar mientras la "
        "sesión esté activa.\n\n"
        "SFTP/SCP está desactivado."
    )


# ==========================================
# PWD
# ==========================================

async def pwd_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not valid_message(update):
        return

    user_id = str(update.effective_user.id)

    directory = get_working_directory(user_id)

    await update.message.reply_text(directory)


# ==========================================
# TERMINAL LINUX
# ==========================================

async def terminal_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not valid_message(update):
        return

    message = update.message.text or ""
    parts = message.split(maxsplit=1)

    command = (
        parts[1].strip()
        if len(parts) > 1
        else ""
    )

    if not command:
        await update.message.reply_text(
            "Ejemplo: /terminal ls -la"
        )
        return

    user_id = str(update.effective_user.id)

    await update.message.reply_text(
        "Ejecutando comando en la Raspberry..."
    )

    try:

        result = await execute_command(
            user_id,
            command,
        )

        await send_long_message(
            update,
            result,
        )

    except Exception:
        logger.exception(
            "Error interno ejecutando comando de terminal."
        )

        await update.message.reply_text(
            "Se produjo un error al ejecutar el comando. "
            "Revisa el registro del servicio."
        )


# ==========================================
# CONTROL UPT​​ERM
# ==========================================

async def upterm_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not valid_message(update):
        return

    action = (
        context.args[0].lower()
        if context.args
        else ""
    )

    # --------------------------------------
    # INICIAR
    # --------------------------------------

    if action == "iniciar":

        await update.message.reply_text(
            "Iniciando sesión Upterm..."
        )

        try:

            session = await start_upterm()

            response = (
                "UPTERM ACTIVO\n\n"
                f"Sesión: {session['name']}\n\n"
            )

            if session.get("joinCommand"):
                response += (
                    "Comando de conexión:\n"
                    f"{session['joinCommand']}\n\n"
                )

            if session.get("sshCommand"):
                response += (
                    "Comando SSH:\n"
                    f"{session['sshCommand']}\n\n"
                )

            response += (
                "IMPORTANTE:\n"
                "Mantén estos datos privados. "
                "Cualquier persona que los obtenga "
                "podrá entrar mientras la sesión esté activa.\n\n"
                "SFTP/SCP: desactivado."
            )

            await send_long_message(
                update,
                response,
            )

        except Exception:
            logger.exception(
                "Error interno iniciando Upterm."
            )

            await update.message.reply_text(
                "No se pudo iniciar Upterm. "
                "Revisa el registro del servicio."
            )

    # --------------------------------------
    # ESTADO
    # --------------------------------------

    elif action == "estado":

        try:

            result = await status_upterm()

            await update.message.reply_text(result)

        except Exception:
            logger.exception(
                "Error interno consultando Upterm."
            )

            await update.message.reply_text(
                "No se pudo consultar el estado de Upterm."
            )

    # --------------------------------------
    # DETENER
    # --------------------------------------

    elif action == "detener":

        try:

            result = await stop_upterm()

            await update.message.reply_text(result)

        except Exception:
            logger.exception(
                "Error interno deteniendo Upterm."
            )

            await update.message.reply_text(
                "No se pudo detener Upterm."
            )

    # --------------------------------------
    # COMANDO INVALIDO
    # --------------------------------------

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

    if AUTHORIZED_USER_ID_INT is None:
        raise RuntimeError(
            "TELEGRAM_AUTHORIZED_USER_ID debe ser numérico."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # --------------------------------------
    # REGISTRAR COMANDOS
    # --------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start_handler,
        )
    )

    application.add_handler(
        CommandHandler(
            "ayuda",
            help_handler,
        )
    )

    application.add_handler(
        CommandHandler(
            "pwd",
            pwd_handler,
        )
    )

    application.add_handler(
        CommandHandler(
            "terminal",
            terminal_handler,
        )
    )

    application.add_handler(
        CommandHandler(
            "upterm",
            upterm_handler,
        )
    )

    # --------------------------------------
    # INICIAR POLLING
    # --------------------------------------

    logger.info(
        "Raspberry Telebot iniciado correctamente."
    )

    application.run_polling()


# ==========================================
# PUNTO DE ENTRADA
# ==========================================

if __name__ == "__main__":
    main()
