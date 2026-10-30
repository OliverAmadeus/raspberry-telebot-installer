
import os
import re
import shutil
import sys
from pathlib import Path


# ==========================================
# CONFIGURACION
# ==========================================

UPTERM_SERVER = os.getenv("UPTERM_SERVER", "").strip()

AUTHORIZED_USERS = [
    os.getenv("UPTERM_AUTHORIZED_USER", "").strip(),
    os.getenv("UPTERM_AUTHORIZED_USER_2", "").strip(),
]

KNOWN_HOSTS = Path(
    "/etc/raspberry-telebot-installer/upterm_known_hosts"
)

EXPECTED_HOST_MARKER = (
    "@cert-authority uptermd.upterm.dev ssh-ed25519 "
)

EXPECTED_HOST_MARKER_443 = (
    "@cert-authority [uptermd.upterm.dev]:443 ssh-ed25519 "
)

EXPECTED_USERS = {
    "github:OliverAmadeus",
    "github:KaworuSSSS",
}


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

    raise FileNotFoundError(
        "No se encontró el ejecutable Upterm."
    )


# ==========================================
# VALIDAR CONFIGURACION
# ==========================================

def validate_configuration():

    if UPTERM_SERVER != "wss://uptermd.upterm.dev":

        raise ValueError(
            "Servidor Upterm no permitido."
        )

    if set(AUTHORIZED_USERS) != EXPECTED_USERS:

        raise ValueError(
            "Las dos cuentas GitHub autorizadas "
            "no coinciden con la configuración esperada."
        )

    for user in AUTHORIZED_USERS:

        if not re.fullmatch(
            r"github:[A-Za-z0-9-]+",
            user
        ):

            raise ValueError(
                "Formato de usuario GitHub no válido."
            )

    # Comprobar archivo de confianza.

    if KNOWN_HOSTS.is_symlink():

        raise ValueError(
            "known_hosts no puede ser un enlace simbólico."
        )

    if not KNOWN_HOSTS.is_file():

        raise FileNotFoundError(
            "No existe el archivo de confianza del relay."
        )

    if KNOWN_HOSTS.stat().st_size == 0:

        raise ValueError(
            "El archivo known_hosts está vacío."
        )

    content = KNOWN_HOSTS.read_text(
        encoding="utf-8"
    )

    lines = content.splitlines()

    if not any(
        line.startswith(EXPECTED_HOST_MARKER)
        for line in lines
    ):

        raise ValueError(
            "Falta la clave de confianza del relay."
        )

    if not any(
        line.startswith(EXPECTED_HOST_MARKER_443)
        for line in lines
    ):

        raise ValueError(
            "Falta la clave de confianza del relay en puerto 443."
        )


# ==========================================
# INICIAR UPT​ERM
# ==========================================

def main():

    validate_configuration()

    executable = find_upterm()

    command = [
        executable,
        "host",

        "--server",
        UPTERM_SERVER,

        "--authorized-user",
        AUTHORIZED_USERS[0],

        "--authorized-user",
        AUTHORIZED_USERS[1],

        "--known-hosts",
        str(KNOWN_HOSTS),

        "--accept",

        "--no-sftp",

        "--hide-client-ip",

        "--",

        "/bin/bash",
        "-l",
    ]

    print("==========================================")
    print(" INICIANDO UPT​ERM")
    print("==========================================")

    print("Servidor:", UPTERM_SERVER)

    print("Cuentas autorizadas:")

    for user in AUTHORIZED_USERS:
        print(" -", user)

    print("SFTP/SCP: desactivado")
    print("Verificación del relay: activada")

    print("Iniciando terminal remota...")

    os.execv(
        executable,
        command
    )


# ==========================================
# EJECUCION PRINCIPAL
# ==========================================

if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print(
            "ERROR UPT​ERM:",
            str(error),
            file=sys.stderr
        )

        sys.exit(1)
