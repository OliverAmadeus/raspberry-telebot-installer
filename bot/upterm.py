
import asyncio
import json
import os
import secrets
import shutil
import signal
from pathlib import Path

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


def validate_session(session):
    """Comprueba que el registro de sesión tenga datos válidos."""

    if not isinstance(session, dict):
        raise RuntimeError("El registro de sesión no es válido.")

    name = session.get("name")

    if not isinstance(name, str) or not name.startswith("telegram-"):
        raise RuntimeError("El nombre de sesión no es válido.")

    join_command = session.get("joinCommand")
    ssh_command = session.get("sshCommand")

    if not join_command and not ssh_command:
        raise RuntimeError("El registro no contiene datos de conexión.")

    return {
        "name": name,
        "joinCommand": join_command,
        "sshCommand": ssh_command,
    }


def read_session():
    """Lee el registro local sin seguir enlaces simbólicos."""

    try:
        info = STATE_FILE.lstat()
    except FileNotFoundError:
        return None

    if not STATE_FILE.is_file() or STATE_FILE.is_symlink():
        raise RuntimeError("El archivo de sesión no es un archivo regular.")

    if info.st_mode & 0o077:
        raise RuntimeError("Los permisos del archivo de sesión son inseguros.")

    session = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return validate_session(session)


def save_session(session):
    """Guarda los datos de conexión con permisos 600."""

    STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o750)

    if STATE_DIR.is_symlink() or SSH_DIR.is_symlink():
        raise RuntimeError("Se detectó un enlace simbólico inseguro.")

    temporary = STATE_DIR / (
        ".upterm_session_" + secrets.token_hex(8) + ".tmp"
    )

    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(session, file)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary, STATE_FILE)
        os.chmod(STATE_FILE, 0o600)

    finally:
        temporary.unlink(missing_ok=True)


def remove_session_file():
    if STATE_FILE.is_symlink():
        raise RuntimeError("El archivo de sesión es un enlace simbólico.")

    STATE_FILE.unlink(missing_ok=True)


async def run_upterm(*args, timeout=COMMAND_TIMEOUT):
    """Ejecuta Upterm con un entorno controlado."""

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
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

        await process.wait()
        raise RuntimeError("Upterm tardó demasiado en responder.")

    output = stdout.decode(errors="replace").strip()
    error = stderr.decode(errors="replace").strip()

    if process.returncode != 0:
        raise RuntimeError(
            error or output or "Error ejecutando Upterm."
        )

    return output


async def get_active_session():
    """Devuelve la sesión registrada si Upterm confirma que sigue activa."""

    previous = read_session()

    if previous is None:
        return None

    try:
        await run_upterm(
            "session",
            "info",
            previous["name"],
            "-o",
            "json",
        )
        return previous

    except RuntimeError:
        remove_session_file()
        return None


async def start_upterm():
    async with LOCK:

        previous = await get_active_session()

        if previous:
            return {
                "already_running": True,
                **previous,
            }

        name = "telegram-" + secrets.token_hex(4)

        output = await run_upterm(
            "host",
            "--server", UPTERM_SERVER,
            "--name", name,
            "--detach",
            "--accept",
            "--no-sftp",
            "--hide-client-ip",
            "-o", "json",
            "--",
            "/bin/bash",
            "-l",
        )

        try:
            data = json.loads(output)

            if not isinstance(data, dict):
                raise ValueError("La respuesta no es un objeto JSON.")

            session = validate_session({
                "name": name,
                "joinCommand": data.get("joinCommand"),
                "sshCommand": data.get("sshCommand"),
            })

            save_session(session)
            return session

        except (json.JSONDecodeError, ValueError, RuntimeError) as error:
            # Si la sesión llegó a crearse, intentar detenerla.
            try:
                await run_upterm(
                    "session",
                    "stop",
                    name,
                )
            except Exception:
                pass

            raise RuntimeError(
                "No se pudo registrar correctamente la sesión Upterm."
            ) from error


async def stop_upterm():
    async with LOCK:

        session = read_session()

        if session is None:
            return "No hay una sesión registrada."

        try:
            await run_upterm(
                "session",
                "stop",
                session["name"],
            )

        except RuntimeError:
            # Si ya no existe, limpiar el registro local.
            pass

        remove_session_file()
        return "Sesión Upterm detenida."


async def status_upterm():
    async with LOCK:

        try:
            session = await get_active_session()

        except (RuntimeError, json.JSONDecodeError, OSError):
            return "No se pudo comprobar el estado de Upterm."

        if session is None:
            return "No hay una sesión Upterm activa."

        return "Sesión activa: " + session["name"]
