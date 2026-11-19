cd /workspaces/raspberry-telebot-installer

cat > bot/explorer.py <<'PY'
import logging
from pathlib import Path

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    CommandHandler,
)

from file_manager import list_directory, get_downloadable_file, read_text_file

logger = logging.getLogger(__name__)

# Directorio inicial
START_DIRECTORY = Path.home().resolve()

# Límite de archivos mostrados por página
PAGE_SIZE = 10

# Estado del explorador por usuario
explorer_sessions = {}


def build_keyboard(user_id, directory, page=0):
    folders, files = list_directory(directory)

    entries = (
        [("folder", item) for item in folders]
        + [("file", item) for item in files]
    )

    start = page * PAGE_SIZE
    visible = entries[start:start + PAGE_SIZE]

    keyboard = []

    for kind, item in visible:
        if kind == "folder":
            keyboard.append([
                InlineKeyboardButton(
                    f"📁 {item.name[:45]}",
                    callback_data=f"exp:open:{item.name}",
                )
            ])
        else:
            keyboard.append([
                InlineKeyboardButton(
                    f"📄 {item.name[:45]}",
                    callback_data=f"exp:select:{item.name}",
                )
            ])

    navigation = []

    if page > 0:
        navigation.append(
            InlineKeyboardButton("⬅️ Anterior", callback_data="exp:page:prev")
        )

    if start + PAGE_SIZE < len(entries):
        navigation.append(
            InlineKeyboardButton("Siguiente ➡️", callback_data="exp:page:next")
        )

    if navigation:
        keyboard.append(navigation)

    keyboard.append([
        InlineKeyboardButton("🏠 Inicio", callback_data="exp:home"),
        InlineKeyboardButton("⬆️ Atrás", callback_data="exp:back"),
    ])

    session = explorer_sessions[user_id]
    selected = session.get("selected")

    if selected:
        keyboard.append([
            InlineKeyboardButton(
                "📥 Descargar archivo",
                callback_data="exp:download",
            ),
            InlineKeyboardButton(
                "👁 Ver contenido",
                callback_data="exp:view",
            ),
        ])

    return InlineKeyboardMarkup(keyboard), len(entries)


async def render_explorer(query, user_id):
    session = explorer_sessions[user_id]
    directory = Path(session["directory"])

    try:
        markup, total = build_keyboard(
            user_id,
            directory,
            session.get("page", 0),
        )

        selected = session.get("selected")
        message = (
            f"📂 EXPLORADOR DE ARCHIVOS\n\n"
            f"📍 {directory}\n\n"
            f"Elementos: {total}\n"
        )

        if selected:
            message += f"\n📌 Seleccionado: {selected}"

        await query.edit_message_text(
            message,
            reply_markup=markup,
        )

    except Exception:
        logger.exception("Error mostrando explorador")
        await query.edit_message_text(
            "No se pudo acceder a esta carpeta."
        )


async def explorer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user or not update.message:
        return

    explorer_sessions[user.id] = {
        "directory": str(START_DIRECTORY),
        "history": [],
        "page": 0,
        "selected": None,
    }

    markup, total = build_keyboard(
        user.id,
        START_DIRECTORY,
    )

    await update.message.reply_text(
        f"📂 EXPLORADOR DE ARCHIVOS\n\n"
        f"📍 {START_DIRECTORY}\n\n"
        f"Elementos: {total}",
        reply_markup=markup,
    )


async def explorer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user

    if not query or not user:
        return

    await query.answer()

    session = explorer_sessions.get(user.id)

    if not session:
        await query.edit_message_text(
            "Sesión expirada. Ejecuta /archivos nuevamente."
        )
        return

    action = query.data.split(":", 2)
    directory = Path(session["directory"])

    if action[1] == "home":
        session["directory"] = str(START_DIRECTORY)
        session["history"] = []
        session["page"] = 0
        session["selected"] = None

    elif action[1] == "back":
        if session["history"]:
            session["directory"] = session["history"].pop()
        session["page"] = 0
        session["selected"] = None

    elif action[1] == "page":
        session["page"] += 1 if action[2] == "next" else -1
        session["page"] = max(0, session["page"])

    elif action[1] == "open":
        name = action[2]
        target = directory / name

        if target.is_symlink() or not target.is_dir():
            await query.answer("Carpeta no válida.", show_alert=True)
            return

        session["history"].append(str(directory))
        session["directory"] = str(target.resolve())
        session["page"] = 0
        session["selected"] = None

    elif action[1] == "select":
        name = action[2]
        target = directory / name

        try:
            target = get_downloadable_file(target)
            session["selected"] = target.name
        except Exception as error:
            await query.answer(str(error), show_alert=True)
            return

    elif action[1] == "download":
        name = session.get("selected")

        if not name:
            await query.answer("Selecciona un archivo primero.", show_alert=True)
            return

        try:
            target = get_downloadable_file(directory / name)

            with target.open("rb") as document:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=document,
                    filename=target.name,
                )

        except Exception:
            logger.exception("Error descargando archivo")
            await query.message.reply_text("No se pudo descargar el archivo.")

    elif action[1] == "view":
        name = session.get("selected")

        if not name:
            await query.answer("Selecciona un archivo primero.", show_alert=True)
            return

        try:
            content = read_text_file(directory / name)

            if len(content) > 3500:
                content = content[:3500] + "\n\n[Contenido recortado]"

            await query.message.reply_text(
                f"📄 {name}\n\n{content}"
            )

        except Exception:
            logger.exception("Error leyendo archivo")
            await query.message.reply_text("No se pudo leer el archivo.")

    await render_explorer(query, user.id)


def register_explorer(application):
    application.add_handler(
        CommandHandler("archivos", explorer_command)
    )

    application.add_handler(
        CallbackQueryHandler(
            explorer_callback,
            pattern=r"^exp:",
        )
    )
PY

python -m py_compile bot/explorer.py
