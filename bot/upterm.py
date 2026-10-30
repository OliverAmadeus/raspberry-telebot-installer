
import asyncio
import json
import os
import secrets
import shutil
import signal
import stat
from pathlib import Path


# ==========================================
# CONFIGURACION
# ==========================================

UPTERM_SERVER = os.environ.get(
    "UPTERM_SERVER",
    "wss://uptermd.upterm.dev",
)

UPTERM_BIN = shutil.which("upterm") or "/usr/local/bin/upterm"

STATE_DIR = Path("/var/lib/raspberry-telebot")
STATE_FILE = STATE_DIR / "upterm_session.json"
SSH_DIR = STATE_DIR / ".ssh"

LOCK = asyncio.Lock()
COMMAND_TIMEOUT = 30


# ==========================================
# VALIDAR DIRECTORIOS
# ==========================================

def validate_directories():
    """Comprueba que los directorios de estado sean seguros."""

    if STATE_DIR.is_symlink():
        raise RuntimeError(
            "El directorio de estado es un enlace simbólico."
        )

    if not STATE_DIR.exists() or not STATE_DIR.is_dir():
        raise RuntimeError(
            "El directorio de estado no existe o no es válido."
        )

    if SSH_DIR.is_symlink():
        raise RuntimeError(
            "El directorio SSH es un enlace simbólico."
        )

    if not SSH_DIR.exists() or not SSH_DIR.is_dir():
        raise RuntimeError(
            "El directorio SSH no existe o no es válido."
        )

    ssh_info = SSH_DIR.stat()

    if stat.S_IMODE(ssh_info.st_mode) & 0o077:
        raise RuntimeError(
            "Los permisos del directorio SSH son inseguros."
        )


# ==========================================
# VALIDAR SESION
# ==========================================

def validate_session(session):
    """Comprueba que el registro de sesión tenga datos válidos."""

    if not isinstance(session, dict):
        raise RuntimeError(
            "El registro de sesión no es válido."
        )

    name = session.get("name")

    if (
        not isinstance(name, str)
        or not name.startswith("telegram-")
        or len(name) > 128
    ):
        raise RuntimeError(
            "El nombre de sesión no es válido."
        )

    join_command = session.get("joinCommand")
    ssh_command = session.get("sshCommand")

    if join_command is not None and not isinstance(join_command, str):
        raise RuntimeError(
            "El comando de conexión no es válido."
        )

    if ssh_command is not None and not isinstance(ssh_command, str):
        raise RuntimeError(
            "El comando SSH no es válido."
        )

    if not join_command and not ssh_command:
        raise RuntimeError(
            "El registro no contiene datos de conexión."
        )

    return {
        "name": name,
        "joinCommand": join_command,
        "sshCommand": ssh_command,
    }


# ==========================================
# LEER SESION
# ==========================================

def read_session():
    """Lee el registro local sin seguir enlaces simbólicos."""

    validate_directories()

    try:
        info = STATE_FILE.lstat()

    except FileNotFoundError:
        return None

    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError(
            "El archivo de sesión no es un archivo regular."
        )

    if stat.S_IMODE(info.st_mode) & 0o077:
        raise RuntimeError(
            "Los permisos del archivo de sesión son inseguros."
        )

    try:
        session = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )

    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RuntimeError(
            "El archivo de sesión contiene datos inválidos."
        ) from error

    return validate_session(session)


# ==========================================
# GUARDAR SESION
# ==========================================

def save_session(session):
    """Guarda los datos de conexión con permisos 600."""

    session = validate_session(session)

    validate_directories()

    temporary = STATE_DIR / (
        ".upterm_session_"
        + secrets.token_hex(8)
        + ".tmp"
    )

    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(session, file)
            file.flush()
            os.fsync(file.fileno())

        os.replace(
            temporary,
            STATE_FILE,
        )

        os.chmod(
            STATE_FILE,
            0o600,
        )

    finally:
        temporary.unlink(missing_ok=True)


# ==========================================
# ELIMINAR REGISTRO
# ==========================================

def remove_session_file():
    validate_directories()

    try:
        info = STATE_FILE.lstat()

    except FileNotFoundError:
        return

    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError(
            "El registro de sesión no es un archivo regular."
        )

    STATE_FILE.unlink()


# ==========================================
# EJECUTAR UPT​ERM
# ==========================================

async def run_upterm(
    *args,
    timeout=COMMAND_TIMEOUT,
):
    """Ejecuta Upterm con un entorno controlado."""

    validate_directories()

    env = {
        "HOME": str(STATE_DIR),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }

    process = await asyncio.create_subprocess_exec(
        UPTERM_BIN,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        start_new_session=True,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )

    except asyncio.TimeoutError:

        try:
            os.killpg(
                process.pid,
                signal.SIGKILL,
            )

        except ProcessLookupError:
            pass

        await process.wait()

        raise RuntimeError(
            "Upterm tardó demasiado en responder."
        )

    output = stdout.decode(
        errors="replace"
    ).strip()

    error = stderr.decode(
        errors="replace"
    ).strip()

    if process.returncode != 0:
        raise RuntimeError(
            error or output or "Error ejecutando Upterm."
        )

    return output


# ==========================================
# COMPROBAR SESION ACTIVA
# ==========================================

async def get_active_session():
    """
    Devuelve la sesión registrada si Upterm confirma
    que el comando de consulta terminó correctamente.

    Si no se puede comprobar, conserva el registro
    para evitar perder el control de una sesión activa.
    """

    previous = read_session()

    if previous is None:
        return None

    await run_upterm(
        "session",
        "info",
        previous["name"],
        "-o",
        "json",
    )

    return previous


# ==========================================
# INICIAR UPT​ERM
# ==========================================

async def start_upterm():

    async with LOCK:

        previous = await get_active_session()

        if previous:
            return {
                "already_running": True,
                **previous,
            }

        name = (
            "telegram-"
            + secrets.token_hex(4)
        )

        output = await run_upterm(
            "host",
            "--server",
            UPTERM_SERVER,
            "--name",
            name,
            "--detach",
            "--accept",
            "--no-sftp",
            "--hide-client-ip",
            "-o",
            "json",
            "--",
            "/bin/bash",
            "-l",
        )

        try:
            data = json.loads(output)

            if not isinstance(data, dict):
                raise ValueError(
                    "La respuesta no es un objeto JSON."
                )

            session = validate_session({
                "name": name,
                "joinCommand": data.get("joinCommand"),
                "sshCommand": data.get("sshCommand"),
            })

            save_session(session)

            return session

        except Exception as error:

            # Si Upterm creó la sesión pero falló
            # el registro local, intentar detenerla.
            try:
                await run_upterm(
                    "session",
                    "stop",
                    name,
                )

            except Exception:
                pass

            raise RuntimeError(
                "No se pudo registrar correctamente "
                "la sesión Upterm."
            ) from error


# ==========================================
# DETENER UPT​ERM
# ==========================================

async def stop_upterm():

    async with LOCK:

        session = read_session()

        if session is None:
            return "No hay una sesión registrada."

        # No borrar el registro si el comando de parada
        # falla: la sesión podría seguir activa.
        await run_upterm(
            "session",
            "stop",
            session["name"],
        )

        remove_session_file()

        return "Sesión Upterm detenida."


# ==========================================
# ESTADO UPT​ERM
# ==========================================

async def status_upterm():

    async with LOCK:

        try:
            session = await get_active_session()

        except (
            RuntimeError,
            json.JSONDecodeError,
            OSError,
        ):
            return (
                "No se pudo comprobar el estado de Upterm. "
                "Se conserva el registro local por seguridad."
            )

        if session is None:
            return "No hay una sesión Upterm registrada."

        return "Sesión activa: " + session["name"]
