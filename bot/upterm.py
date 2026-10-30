
import os
import shutil
import sys
from pathlib import Path


UPTERM_SERVER = os.getenv(
    "UPTERM_SERVER",
    "wss://uptermd.upterm.dev"
).strip()

UPTERM_AUTHORIZED_USER = os.getenv(
    "UPTERM_AUTHORIZED_USER",
    "github:KaworuSSSS"
).strip()


def find_upterm():
    """Localiza el ejecutable de Upterm."""

    executable = shutil.which("upterm")

    if executable:
        return executable

    possible_paths = [
        Path.home() / "go/bin/upterm",
        Path("/usr/local/bin/upterm"),
        Path("/usr/bin/upterm"),
    ]

    for path in possible_paths:
        if path.is_file():
            return str(path)

    raise FileNotFoundError(
        "No se encontró Upterm. Ejecuta primero el instalador."
    )


def main():
    if not UPTERM_SERVER.startswith("wss://"):
        raise ValueError("El servidor Upterm debe utilizar WSS.")

    if not UPTERM_AUTHORIZED_USER.startswith("github:"):
        raise ValueError(
            "UPTERM_AUTHORIZED_USER debe indicar una cuenta GitHub."
        )

    executable = find_upterm()

    command = [
        executable,
        "host",
        "--server",
        UPTERM_SERVER,
        "--authorized-user",
        UPTERM_AUTHORIZED_USER,
        "--accept",
        "--",
        "/bin/bash",
        "-l",
    ]

    print("Iniciando terminal remota Upterm...")
    print(f"Servidor: {UPTERM_SERVER}")
    print(f"Acceso autorizado: {UPTERM_AUTHORIZED_USER}")

    os.execv(executable, command)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR UPTERM: {error}", file=sys.stderr)
        sys.exit(1)
