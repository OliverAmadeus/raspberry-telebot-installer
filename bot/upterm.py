
import os
import shutil
import sys
from pathlib import Path


# ==========================================
# CONFIGURACION
# ==========================================

UPTERM_SERVER = os.getenv(
    "UPTERM_SERVER", ""
).strip()

UPTERM_AUTHORIZED_USER = os.getenv(
    "UPTERM_AUTHORIZED_USER", ""
).strip()

HOME_DIR = Path.home()

SSH_DIR = HOME_DIR / ".ssh"
KNOWN_HOSTS = SSH_DIR / "known_hosts"


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
        HOME_DIR / "go/bin/upterm",
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
            "El servidor Upterm no coincide con el relay autorizado."
        )

    if not UPTERM_AUTHORIZED_USER.startswith("github:"):
        raise ValueError(
            "La autorización debe tener formato github:usuario."
        )

    username = UPTERM_AUTHORIZED_USER.split(":", 1)[1]

    if not username:
        raise ValueError(
            "Falta el usuario GitHub autorizado."
        )

    if not all(
        character.isalnum() or character == "-"
        for character in username
    ):
        raise ValueError(
            "El usuario GitHub configurado no es válido."
        )

    if not SSH_DIR.is_dir():
        raise FileNotFoundError(
            f"No existe el directorio SSH: {SSH_DIR}"
        )

    if not KNOWN_HOSTS.is_file():
        raise FileNotFoundError(
            f"No existe known_hosts: {KNOWN_HOSTS}"
        )

    if KNOWN_HOSTS.stat().st_size == 0:
        raise ValueError(
            "El archivo known_hosts está vacío."
        )

    known_hosts_content = KNOWN_HOSTS.read_text(
        encoding="utf-8"
    )

    if "@cert-authority uptermd.upterm.dev ssh-ed25519" not in known_hosts_content:
        raise ValueError(
            "No se encontró la clave oficial del relay."
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
        "--hide-client-ip",
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
    print("IP de invitados: oculta")
    print("Acceso interactivo: habilitado")
    print("Modo: primer plano")
    print("Iniciando terminal remota...", flush=True)

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
