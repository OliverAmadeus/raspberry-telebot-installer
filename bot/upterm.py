
import os
import re
import shutil
import sys
from pathlib import Path


# ==========================================
# CONFIGURACION
# ==========================================

UPTERM_SERVER = os.getenv(
    "UPTERM_SERVER",
    ""
).strip()

UPTERM_AUTHORIZED_USER = os.getenv(
    "UPTERM_AUTHORIZED_USER",
    ""
).strip()

KNOWN_HOSTS = Path(
    "/etc/raspberry-telebot-installer/upterm_known_hosts"
)

EXPECTED_HOST_MARKER = (
    "@cert-authority uptermd.upterm.dev ssh-ed25519 "
)

EXPECTED_HOST_MARKER_443 = (
    "@cert-authority [uptermd.upterm.dev]:443 ssh-ed25519 "
)


# ==========================================
# LOCALIZAR UPT​ERM
# ==========================================

def find_upterm():

    executable = shutil.which("upterm")

    if executable:
        return executable

    possible_paths = [
        Path("/usr/local/bin/upterm"),
        Path("/usr/bin/upterm"),
        Path.home() / "go/bin/upterm",
    ]

    for path in possible_paths:

        if path.is_file() and os.access(path, os.X_OK):
            return str(path)

    raise RuntimeError(
        "No se encontró el ejecutable Upterm."
    )


# ==========================================
# VALIDAR CONFIGURACION
# ==========================================

def validate_configuration():

    # Validar servidor.

    if UPTERM_SERVER != "wss://uptermd.upterm.dev":
        raise RuntimeError(
            "UPTERM_SERVER no coincide con el relay autorizado."
        )

    # Validar usuario GitHub.

    if not re.fullmatch(
        r"github:[A-Za-z0-9-]+",
        UPTERM_AUTHORIZED_USER
    ):
        raise RuntimeError(
            "UPTERM_AUTHORIZED_USER no es válido."
        )

    # Validar archivo de confianza.

    if not KNOWN_HOSTS.is_file():
        raise RuntimeError(
            f"No existe el archivo de confianza: {KNOWN_HOSTS}"
        )

    if KNOWN_HOSTS.is_symlink():
        raise RuntimeError(
            "El archivo known_hosts no puede ser un enlace simbólico."
        )

    if KNOWN_HOSTS.stat().st_size == 0:
        raise RuntimeError(
            "El archivo known_hosts está vacío."
        )

    # Verificar las dos entradas esperadas.

    content = KNOWN_HOSTS.read_text(
        encoding="utf-8"
    )

    lines = content.splitlines()

    if not any(
        line.startswith(EXPECTED_HOST_MARKER)
        for line in lines
    ):
        raise RuntimeError(
            "Falta la clave de confianza del relay Upterm."
        )

    if not any(
        line.startswith(EXPECTED_HOST_MARKER_443)
        for line in lines
    ):
        raise RuntimeError(
            "Falta la clave de confianza del relay Upterm en el puerto 443."
        )


# ==========================================
# INICIAR UPT​ERM
# ==========================================

def main():

    try:

        validate_configuration()

        executable = find_upterm()

        command = [
            executable,
            "host",

            "--server",
            UPTERM_SERVER,

            "--authorized-user",
            UPTERM_AUTHORIZED_USER,

            "--known-hosts",
            str(KNOWN_HOSTS),

            "--accept",

            "--no-sftp",

            "--hide-client-ip",

            "--",

            "/bin/bash",
            "-l",
        ]

        print(
            "Iniciando servidor Upterm...",
            flush=True
        )

        print(
            f"Relay: {UPTERM_SERVER}",
            flush=True
        )

        print(
            f"Usuario autorizado: {UPTERM_AUTHORIZED_USER}",
            flush=True
        )

        print(
            "Transferencia SFTP: desactivada",
            flush=True
        )

        # Reemplazar el proceso Python por Upterm.
        # systemd supervisará directamente Upterm.

        os.execv(
            executable,
            command
        )

    except Exception as error:

        print(
            f"ERROR iniciando Upterm: {error}",
            file=sys.stderr,
            flush=True
        )

        sys.exit(1)


# ==========================================
# PUNTO DE ENTRADA
# ==========================================

if __name__ == "__main__":
    main()
