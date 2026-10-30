
import asyncio
import json
import os
import secrets
import shutil
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


async def run_upterm(*args, timeout=30):
    env = os.environ.copy()

    # Garantiza que Upterm/SSH utilice:
    # /var/lib/raspberry-telebot/.ssh/known_hosts
    env["HOME"] = str(STATE_DIR)

    process = await asyncio.create_subprocess_exec(
        UPTERM_BIN,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise RuntimeError("Upterm tardó demasiado en responder.")

    output = stdout.decode(errors="replace").strip()
    error = stderr.decode(errors="replace").strip()

    if process.returncode != 0:
        raise RuntimeError(
            error or output or "Error ejecutando Upterm."
        )

    return output


def save_session(session):
    """
    Guarda los datos de conexión con permisos 600.
    El archivo contiene el secreto de acceso a la sesión.
    """

    STATE_DIR.mkdir(
        parents=True,
        exist_ok=True,
        mode=0o750,
    )

    temporary = STATE_DIR / (
        ".upterm_session_" + secrets.token_hex(8) + ".tmp"
    )

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(temporary, flags, 0o600)

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(session, file)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary, STATE_FILE)
        os.chmod(STATE_FILE, 0o600)

    finally:
        temporary.unlink(missing_ok=True)


async def start_upterm():
    async with LOCK:

        if STATE_FILE.exists():
            try:
                previous = json.loads(
                    STATE_FILE.read_text(encoding="utf-8")
                )

                await run_upterm(
                    "session",
                    "info",
                    previous["name"],
                    "-o",
                    "json",
                )

                return {
                    "already_running": True,
                    **previous,
                }

            except Exception:
                STATE_FILE.unlink(missing_ok=True)

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
        except json.JSONDecodeError:
            raise RuntimeError(
                "Upterm no devolvió JSON válido."
            )

        join_command = data.get("joinCommand")
        ssh_command = data.get("sshCommand")

        if not join_command and not ssh_command:
            raise RuntimeError(
                "Upterm inició, pero no devolvió datos de conexión."
            )

        session = {
            "name": name,
            "joinCommand": join_command,
            "sshCommand": ssh_command,
        }

        save_session(session)

        return session


async def stop_upterm():
    async with LOCK:

        if not STATE_FILE.exists():
            return "No hay una sesión registrada."

        session = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )

        await run_upterm(
            "session",
            "stop",
            session["name"],
        )

        STATE_FILE.unlink(missing_ok=True)

        return "Sesión Upterm detenida."


async def status_upterm():
    async with LOCK:

        if not STATE_FILE.exists():
            return "Upterm está detenido."

        try:
            session = json.loads(
                STATE_FILE.read_text(encoding="utf-8")
            )

            await run_upterm(
                "session",
                "info",
                session["name"],
                "-o",
                "json",
            )

            return "Sesión activa: " + session["name"]

        except Exception:
            STATE_FILE.unlink(missing_ok=True)
            return "No hay una sesión Upterm activa."
