
import os
import shutil
import sys
from pathlib import Path


# ==========================================
# CONFIGURACIÓN
# ==========================================

UPTERM_SERVER = os.getenv(
    "UPTERM_SERVER",
    "wss://uptermd.upterm.dev"
).strip()

UPTERM_AUTHORIZED_USER = os.getenv(
    "UPTERM_AUTHORIZED_USER",
    "github:KaworuSSSS"
).strip()


# ==========================================
# LOCALIZAR UPT​ERM
# ==========================================

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
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)

    raise FileNotFoundError(
        "No se encontró Upterm. "
        "Ejecuta primero el instalador."
    )


# ==========================================
# VALIDAR CONFIGURACIÓN
# ==========================================

def validate_configuration():

    if not UPTERM_SERVER.startswith("wss://"):
        raise ValueError(
            "El servidor debe utilizar una conexión WSS."
        )

    if not UPTERM_AUTHORIZED_USER.startswith("github:"):
        raise ValueError(
            "UPTERM_AUTHORIZED_USER debe tener "
            "el formato github:usuario."
        )

    username = UPTERM_AUTHORIZED_USER.split(":", 1)[1]

    if not username or "/" in username:
        raise ValueError(
            "La cuenta GitHub configurada no es válida."
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
    print("Transferencia SFTP: desactivada")
    print("Acceso interactivo: habilitado")
    print("Iniciando sesión remota...")

    os.execv(executable, command)


# ==========================================
# EJECUCIÓN
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
