
import asyncio
import os
import shlex
import signal
from pathlib import Path


# ==========================================
# CONFIGURACION
# ==========================================

HOME_DIR = "/var/lib/raspberry-telebot"

COMMAND_TIMEOUT = 120
MAX_OUTPUT_SIZE = 1024 * 1024  # 1 MiB por canal
READ_CHUNK_SIZE = 65536

# Directorio independiente por usuario Telegram.
working_directories = {}


# ==========================================
# ENTORNO CONTROLADO
# ==========================================

def get_command_environment():
    return {
        "HOME": HOME_DIR,
        "USER": "raspberry-telebot",
        "LOGNAME": "raspberry-telebot",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TERM": "xterm-256color",
    }


# ==========================================
# DIRECTORIO ACTUAL
# ==========================================

def get_working_directory(user_id):
    return working_directories.get(user_id, HOME_DIR)


# ==========================================
# CAMBIAR DIRECTORIO
# ==========================================

def change_directory(user_id, command):

    try:
        arguments = shlex.split(command)

        if len(arguments) > 2:
            return "Uso: cd [directorio]"

        destination = (
            arguments[1]
            if len(arguments) == 2
            else HOME_DIR
        )

        current_dir = get_working_directory(user_id)

        if destination == "~":
            destination = HOME_DIR

        elif destination.startswith("~/"):
            destination = os.path.join(
                HOME_DIR,
                destination[2:]
            )

        elif not os.path.isabs(destination):
            destination = os.path.join(
                current_dir,
                destination
            )

        destination = os.path.abspath(destination)

        if not os.path.isdir(destination):
            return (
                "No existe el directorio:\n"
                f"{destination}"
            )

        if not os.access(destination, os.X_OK | os.R_OK):
            return (
                "No tienes permisos para acceder al directorio:\n"
                f"{destination}"
            )

        working_directories[user_id] = destination

        return (
            "Directorio cambiado a:\n"
            f"{destination}"
        )

    except ValueError:
        return "Error: formato de directorio no válido."


# ==========================================
# TERMINAR GRUPO DE PROCESOS
# ==========================================

async def terminate_process_group(process):

    try:
        os.killpg(process.pid, signal.SIGTERM)

    except ProcessLookupError:
        pass

    try:
        await asyncio.wait_for(
            process.wait(),
            timeout=5
        )

    except asyncio.TimeoutError:

        try:
            os.killpg(process.pid, signal.SIGKILL)

        except ProcessLookupError:
            pass

        await process.wait()


# ==========================================
# LEER SALIDA CON LIMITE DE MEMORIA
# ==========================================

async def read_limited(stream, exceeded_event, process):

    collected = bytearray()

    while True:

        chunk = await stream.read(READ_CHUNK_SIZE)

        if not chunk:
            break

        remaining = MAX_OUTPUT_SIZE + 1 - len(collected)

        if remaining > 0:
            collected.extend(chunk[:remaining])

        if len(collected) > MAX_OUTPUT_SIZE:

            if not exceeded_event.is_set():

                exceeded_event.set()

                try:
                    os.killpg(
                        process.pid,
                        signal.SIGTERM
                    )

                except ProcessLookupError:
                    pass

            break

    exceeded = len(collected) > MAX_OUTPUT_SIZE

    return bytes(collected[:MAX_OUTPUT_SIZE]), exceeded


# ==========================================
# EJECUTAR COMANDO
# ==========================================

async def execute_command(user_id, command):
    """
    Ejecuta comandos Linux mediante Bash.

    Características:
    - Comandos arbitrarios dentro de los permisos del servicio.
    - Directorio persistente por usuario durante la ejecución del bot.
    - Entorno controlado.
    - Tiempo máximo de ejecución.
    - Lectura limitada de stdout y stderr.
    - Terminación del grupo de procesos.
    """

    command = command.strip()

    if not command:
        return "No se recibió ningún comando."

    # ======================================
    # PROCESAR CD
    # ======================================

    try:
        parsed_command = shlex.split(command)

    except ValueError:
        parsed_command = []

    if parsed_command and parsed_command[0] == "cd":
        return change_directory(user_id, command)

    # ======================================
    # VALIDAR DIRECTORIO
    # ======================================

    current_dir = get_working_directory(user_id)

    if not os.path.isdir(current_dir):
        current_dir = HOME_DIR
        working_directories[user_id] = HOME_DIR

    if not os.access(current_dir, os.X_OK | os.R_OK):
        return "No tienes permisos para acceder al directorio actual."

    # ======================================
    # CREAR PROCESO
    # ======================================

    try:

        process = await asyncio.create_subprocess_exec(
            "/bin/bash",
            "-lc",
            command,
            cwd=current_dir,
            env=get_command_environment(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True
        )

    except Exception as error:
        return f"No se pudo iniciar el comando: {error}"

    # ======================================
    # LEER SALIDAS SIMULTANEAMENTE
    # ======================================

    exceeded_event = asyncio.Event()

    stdout_task = asyncio.create_task(
        read_limited(
            process.stdout,
            exceeded_event,
            process
        )
    )

    stderr_task = asyncio.create_task(
        read_limited(
            process.stderr,
            exceeded_event,
            process
        )
    )

    gather_task = asyncio.gather(
        stdout_task,
        stderr_task,
        process.wait()
    )

    # ======================================
    # CONTROLAR TIEMPO DE EJECUCION
    # ======================================

    timed_out = False

    try:

        await asyncio.wait_for(
            asyncio.shield(gather_task),
            timeout=COMMAND_TIMEOUT
        )

    except asyncio.TimeoutError:

        timed_out = True

        await terminate_process_group(process)

        await gather_task

    except Exception:

        await terminate_process_group(process)

        if not gather_task.done():
            await gather_task

        raise

    # ======================================
    # RECUPERAR RESULTADOS
    # ======================================

    stdout, stdout_exceeded = stdout_task.result()
    stderr, stderr_exceeded = stderr_task.result()

    # ======================================
    # PREPARAR RESULTADO
    # ======================================

    output = stdout.decode(errors="replace").strip()
    errors = stderr.decode(errors="replace").strip()

    result = output

    if errors:
        result += ("\n" if result else "") + errors

    if timed_out:

        result += (
            "\n\n[Comando terminado por superar "
            f"el límite de {COMMAND_TIMEOUT} segundos.]"
        )

    if stdout_exceeded or stderr_exceeded:

        result += (
            "\n\n[Proceso terminado: se alcanzó "
            "el límite de salida de 1 MiB por canal.]"
        )

    if not result:

        result = (
            "Comando finalizado. "
            f"Código de salida: {process.returncode}"
        )

    return result
