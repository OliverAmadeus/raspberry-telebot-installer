
import logging
from datetime import datetime
from pathlib import Path

from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Carpeta donde se generan los archivos
REPORT_DIRECTORY = Path("/home/rasp4/Documents")


def get_daily_files():
    """Localiza los archivos correspondientes al día actual."""

    today = datetime.now().date()

    # Archivo TXT: datos_acumulados_AAAA-MM-DD.txt
    txt_name = f"datos_acumulados_{today:%Y-%m-%d}.txt"
    txt_file = REPORT_DIRECTORY / txt_name

    # Mes en inglés, independientemente del idioma de Linux
    months = (
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    )

    month = months[today.month - 1]
    csv_date = f"{month}-{today.day}-{today.year}"

    # El número intermedio es variable
    csv_files = list(
        REPORT_DIRECTORY.glob(f"TesjoQ_*_{csv_date}.csv")
    )

    # Si hay varios, seleccionamos el más reciente
    csv_file = (
        max(csv_files, key=lambda f: f.stat().st_mtime)
        if csv_files else None
    )

    return txt_file, csv_file, today


async def send_daily_reports(
    context: ContextTypes.DEFAULT_TYPE
):
    """Envía automáticamente los reportes diarios."""

    chat_id = context.job.data["chat_id"]

    txt_file, csv_file, today = get_daily_files()

    files = [
        ("TXT", txt_file),
        ("CSV", csv_file),
    ]

    missing = []
    errors = []
    sent = 0

    for file_type, file_path in files:

        if file_path is None or not file_path.is_file():
            missing.append(file_type)
            continue

        try:
            with file_path.open("rb") as document:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=document,
                    filename=file_path.name,
                    caption=(
                        f"📊 Reporte diario {today:%d/%m/%Y}\n"
                        f"Archivo: {file_type}"
                    ),
                )

            logger.info(
                "Reporte %s enviado: %s",
                file_type,
                file_path.name,
            )

            sent += 1

        except Exception as error:
            logger.exception(
                "Error enviando reporte %s",
                file_type,
            )
            errors.append(file_type)

    # Informar si faltan archivos o hubo errores
    if missing or errors:

        message = (
            f"⚠️ REPORTE DIARIO {today:%d/%m/%Y}\n\n"
        )

        if missing:
            message += (
                "No se encontraron:\n"
                + "\n".join(f"• {item}" for item in missing)
                + "\n\n"
            )

        if errors:
            message += (
                "No se pudieron enviar:\n"
                + "\n".join(f"• {item}" for item in errors)
                + "\n\n"
            )

        message += f"Archivos enviados correctamente: {sent}/2"

        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
        )

        logger.warning(message)

    else:
        logger.info(
            "Todos los reportes diarios fueron enviados."
        )


def register_daily_reports(application, chat_id):
    """Programa el envío todos los días a las 23:59."""

    if application.job_queue is None:
        raise RuntimeError(
            'JobQueue no disponible. Instala '
            '"python-telegram-bot[job-queue]".'
        )

    application.job_queue.run_daily(
        send_daily_reports,
        time=datetime.strptime("23:59", "%H:%M").time(),
        data={"chat_id": chat_id},
        name="daily_reports",
    )

    logger.info(
        "Envío automático de reportes programado para las 23:59."
    )
