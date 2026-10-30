
import os
import shutil
import sys
from pathlib import Path


# ==========================================
# CONFIGURACION
# ==========================================

UPTERM_SERVER = os.getenv(
    "UPTERM_SERVER",
    "wss://uptermd.upterm.dev"
).strip()

UPTERM_AUTHORIZED_USER = os.getenv(
    "UPTERM_AUTHORIZED_USER",
    "github:KaworuSSSS"
).strip()

KNOWN_HOSTS = Path.home() / ".ssh" / "known_hosts"


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

    if not UPTERM_SERVER.startswith("wss://"):
        raise ValueError(
            "El servidor debe utilizar WSS."
        )

    if not UPTERM_AUTHORIZED_USER.startswith("github:"):
        raise ValueError(
            "La autorización debe tener formato github:usuario."
        )

    username = UPTERM_AUTHORIZED_USER.split(":", 1)[1]

    if not username or "/" in username:
        raise ValueError(
            "El usuario GitHub configurado no es válido."
        )

    if not KNOWN_HOSTS.is_file():
        raise FileNotFoundError(
            f"No existe el archivo de claves verificadas: {KNOWN_HOSTS}"
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
        UPTERM_AUTHORIZED_USER,
        "--known-hosts",
        str(KNOWN_HOSTS),
        "--accept",
        "--no-sftp",
        "--",
        "/bin/bash",
        "-l",
    ]

    print("======================================")
    print(" RASPBERRY TELEBOT - UPT​ERM")
    print("======================================")

    print(f"Ejecutable: {executable}")
    print(f"Servidor: {UPTERM_SERVER}")
    print(f"Usuario autorizado: {UPTERM_AUTHORIZED_USER}")
    print(f"Claves verificadas: {KNOWN_HOSTS}")
    print("SFTP/SCP: desactivado")
    print("Acceso interactivo: habilitado")
    print("Iniciando terminal remota...")

    os.execv(executable, command)


# ==========================================
# EJECUCION
# ==========================================

if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:
        print("\nUpterm detenido.")

    except Exception as error:
        print(
            f"ERROR UPT​ERM: {error}",
            file=sys.stderr
        )
        sys.exit(1)
