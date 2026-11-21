from pathlib import Path

ALLOWED_EXTENSIONS = {
    ".txt", ".csv", ".log", ".json", ".pdf", ".xlsx"
}

MAX_FILE_SIZE = 45 * 1024 * 1024


def list_directory(directory):
    path = Path(directory).resolve()

    if not path.is_dir():
        raise ValueError("El directorio no existe.")

    folders = []
    files = []

    for item in sorted(path.iterdir(), key=lambda x: x.name.lower()):
        try:
            if item.is_symlink():
                continue

            if item.is_dir():
                folders.append(item)
            elif item.is_file():
                files.append(item)

        except PermissionError:
            continue

    return folders, files


def get_downloadable_file(file_path):
    path = Path(file_path).resolve(strict=True)

    if not path.is_file():
        raise ValueError("No es un archivo válido.")

    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("Tipo de archivo no permitido.")

    if path.stat().st_size > MAX_FILE_SIZE:
        raise ValueError("El archivo supera el límite de descarga.")

    return path


def read_text_file(file_path):
    path = get_downloadable_file(file_path)

    if path.suffix.lower() not in {
        ".txt", ".csv", ".log", ".json"
    }:
        raise ValueError("Este archivo no es de texto.")

    return path.read_text(
        encoding="utf-8",
        errors="replace"
    )
