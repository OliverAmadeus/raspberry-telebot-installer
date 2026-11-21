import logging
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    CommandHandler,
)

from file_manager import (
    list_directory,
    get_downloadable_file,
    read_text_file,
)

logger = logging.getLogger(__name__)

START_DIRECTORY = Path("/home/rasp4").resolve()
PAGE_SIZE = 10

explorer_sessions = {}


def is_authorized(update, context):
    user = update.effective_user
    chat = update.effective_chat

    return user is not None and chat is not None


def safe_directory(path):
    path = Path(path).resolve(strict=True)

    if not path.is_dir():
        raise ValueError("No es una carpeta.")

    if not path.is_relative_to(START_DIRECTORY):
        raise ValueError("Acceso fuera del directorio permitido.")

    return path


def build_keyboard(user_id, directory, page=0):
    folders, files = list_directory(directory)

    entries = (
        [("folder", item) for item in folders]
        + [("file", item) for item in files]
    )

    start = page * PAGE_SIZE
    visible = entries[start:start + PAGE_SIZE]

    keyboard = []

    for index, (kind, item) in enumerate(visible):
        if kind == "folder":
            keyboard.append([
                InlineKeyboardButton(
                    f"📁 {item.name[:35]}",
                    callback_data=f"exp:open:{index}",
                )
            ])
        else:
            keyboard.append([
                InlineKeyboardButton(
                    f"📄 {item.name[:35]}",
                    callback_data=f"exp:select:{index}",
                )
            ])

    navigation = []

    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                "⬅️ Anterior",
                callback_data="exp:page:prev",
            )
        )

    if start + PAGE_SIZE < len(entries):
        navigation.append(
            InlineKeyboardButton(
                "Siguiente ➡️",
                callback_data="exp:page:next",
            )
        )

    if navigation:
        keyboard.append(navigation)

    keyboard.append([
        InlineKeyboardButton("🏠 Inicio", callback_data="exp:home"),
        InlineKeyboardButton("⬆️ Atrás", callback_data="exp:back"),
    ])

    selected = explorer_sessions[user_id].get("selected")

    if selected:
        keyboard.append([
            InlineKeyboardButton(
                "📥 Descargar TXT",
                callback_data="exp:download",
            ),
            InlineKeyboardButton(
                "👁 Ver contenido",
                callback_data="exp:view",
            ),
        ])

    return InlineKeyboardMarkup(keyboard), len(entries)


def get_entries(directory):
    folders, files = list_directory(directory)
    return (
        [("folder", item) for item in folders]
        + [("file", item) for item in files]
    )


async def render_explorer(query, user_id):
    session = explorer_sessions[user_id]
    directory = safe_directory(session["directory"])

    markup, total = build_keyboard(
        user_id,
        directory,
        session.get("page", 0),
    )

    message = (
        "📂 EXPLORADOR DE ARCHIVOS\n\n"
        f"📍 {directory}\n\n"
        f"Elementos: {total}"
    )

    if session.get("selected"):
        message += f"\n\n📌 Seleccionado: {session['selected']}"

    await query.edit_message_text(
        message,
        reply_markup=markup,
    )


async def explorer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update, context):
        return

    explorer_sessions[update.effective_user.id] = {
        "directory": str(START_DIRECTORY),
        "history": [],
        "page": 0,
        "selected": None,
    }

    try:
        markup, total = build_keyboard(
            update.effective_user.id,
            START_DIRECTORY,
        )

        await update.message.reply_text(
            "📂 EXPLORADOR DE ARCHIVOS\n\n"
            f"📍 {START_DIRECTORY}\n\n"
            f"Elementos: {total}",
            reply_markup=markup,
        )

    except Exception:
        logger.exception("Error iniciando explorador")
        await update.message.reply_text(
            "No se pudo abrir el directorio inicial."
        )


async def explorer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user

    if not is_authorized(update, context):
        await query.answer(
            "No tienes autorización.",
            show_alert=True,
        )
        return

    await query.answer()

    session = explorer_sessions.get(user.id)

    if not session:
        await query.edit_message_text(
            "Sesión expirada. Ejecuta /archivos nuevamente."
        )
        return

    directory = safe_directory(session["directory"])
    action = query.data.split(":", 2)

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

    elif action[1] in ("open", "select"):
        index = int(action[2])
        entries = get_entries(directory)

        start = session.get("page", 0) * PAGE_SIZE
        entry_index = start + index

        if entry_index >= len(entries):
            await query.answer("Elemento no válido.", show_alert=True)
            return

        kind, item = entries[entry_index]

        if action[1] == "open":
            if kind != "folder":
                return

            target = safe_directory(item)

            session["history"].append(str(directory))
            session["directory"] = str(target)
            session["page"] = 0
            session["selected"] = None

        else:
            if kind != "file":
                return

            try:
                target = get_downloadable_file(item)

                if target.suffix.lower() != ".txt":
                    await query.answer(
                        "Solo se permiten archivos TXT.",
                        show_alert=True,
                    )
                    return

                session["selected"] = target.name

            except Exception as error:
                await query.answer(str(error), show_alert=True)
                return

    elif action[1] == "download":
        name = session.get("selected")

        if not name:
            return

        target = get_downloadable_file(directory / name)

        if target.suffix.lower() != ".txt":
            await query.answer("Solo se permiten TXT.", show_alert=True)
            return

        with target.open("rb") as document:
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=document,
                filename=target.name,
            )

    elif action[1] == "view":
        name = session.get("selected")

        if not name:
            return

        content = read_text_file(directory / name)

        if len(content) > 3500:
            content = content[:3500] + "\n\n[Contenido recortado]"

        await query.message.reply_text(
            f"📄 {name}\n\n{content}"
        )

    await render_explorer(query, user.id)


def register_explorer(application, authorized_user_id):
    application.bot_data["explorer_authorized_user_id"] = authorized_user_id
    application.add_handler(
        CommandHandler("archivos", explorer_command)
    )

    application.add_handler(
        CallbackQueryHandler(
            explorer_callback,
            pattern=r"^exp:",
        )
    )
