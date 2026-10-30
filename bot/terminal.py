
import asyncio
import os
import shlex
import signal


# ==========================================
# CONFIGURACION
# ==========================================

HOME_DIR = "/var/lib/raspberry-telebot"

COMMAND_TIMEOUT = 120
MAX_OUTPUT_SIZE = 1024 * 1024  # 1 MiB por canal
READ_CHUNK_SIZE = 65536
TERMINATION_GRACE_PERIOD = 3
PIPE_CLEANUP_TIMEOUT = 10

working_directories = {}


# ==========================================
# ENTORNO CONTROLADO
# ==========================================

def get_command_environment():
    return {
        "HOME": HOME_DIR,
        "USER": "raspberry-telebot",
        "LOGNAME": "raspberry-telebot",
        "PATH": (
            "/usr/local/sbin:/usr/local/bin:"
            "/usr/sbin:/usr/bin:/sbin:/bin"
        ),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TERM": "xterm-256color",
    }


# ==========================================
# DIRECTORIO ACTUAL
# ==========================================

def get_working_directory(user_id):
    return working_directories.get(
        user_id,
        HOME_DIR,
    )


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
                destination[2:],
            )

        elif not os.path.isabs(destination):
            destination = os.path.join(
                current_dir,
                destination,
            )

        destination = os.path.abspath(destination)

        if not os.path.isdir(destination):
            return (
                "No existe el directorio:\n"
                f"{destination}"
            )

        if not os.access(
            destination,
            os.X_OK | os.R_OK,
        ):
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

async def terminate_process_group(
    process,
    lock,
    state,
):
    """
    Termina el proceso principal y sus procesos hijos.

    El bloqueo evita que stdout y stderr envíen señales
    simultáneamente al mismo grupo.
    """

    async with lock:

        if state["terminated"]:
            await process.wait()
            return

        try:
            os.killpg(
                process.pid,
                signal.SIGTERM,
            )

        except ProcessLookupError:
            pass

        try:
            await asyncio.wait_for(
                asyncio.shield(process.wait()),
                timeout=TERMINATION_GRACE_PERIOD,
            )

        except asyncio.TimeoutError:
            pass

        # Eliminar también posibles procesos hijos
        # aunque el proceso principal haya terminado.
        try:
            os.killpg(
                process.pid,
                signal.SIGKILL,
            )

        except ProcessLookupError:
            pass

        await process.wait()

        state["terminated"] = True


# ==========================================
# LEER SALIDA CON LIMITE DE MEMORIA
# ==========================================

async def read_limited(
    stream,
    terminate,
):
    """
    Lee un canal sin almacenar más de MAX_OUTPUT_SIZE.

    Si supera el límite, solicita terminar el grupo
    completo de procesos.
    """

    collected = bytearray()
    exceeded = False

    while True:

        chunk = await stream.read(READ_CHUNK_SIZE)

        if not chunk:
            break

        remaining = MAX_OUTPUT_SIZE - len(collected)

        if remaining > 0:
            collected.extend(chunk[:remaining])

        if len(chunk) > remaining and not exceeded:

            exceeded = True

            await terminate()

    return bytes(collected), exceeded


# ==========================================
# CANCELAR TAREAS DE LECTURA
# ==========================================

async def cancel_reader_tasks(
    stdout_task,
    stderr_task,
    gather_task,
):
    """
    Cancela las tareas de lectura y recoge sus resultados
    para evitar tareas asíncronas pendientes.
    """

    for task in (stdout_task, stderr_task):
        if not task.done():
            task.cancel()

    await asyncio.gather(
        stdout_task,
        stderr_task,
        return_exceptions=True,
    )

    if not gather_task.done():
        gather_task.cancel()

    try:
        await gather_task

    except asyncio.CancelledError:
        pass

    except Exception:
        pass


# ==========================================
# EJECUTAR COMANDO
# ==========================================

async def execute_command(user_id, command):
    """
    Ejecuta comandos Linux mediante Bash.

    Características:
    - Ejecuta con los permisos del usuario del servicio.
    - No concede privilegios adicionales.
    - Directorio independiente por usuario Telegram.
    - Entorno controlado.
    - Tiempo máximo de ejecución.
    - Salida limitada a 1 MiB por canal.
    - Terminación del grupo de procesos.
    - Limpieza de tareas asíncronas.
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
        return change_directory(
            user_id,
            command,
        )

    # ======================================
    # VALIDAR DIRECTORIO
    # ======================================

    current_dir = get_working_directory(user_id)

    if not os.path.isdir(current_dir):
        current_dir = HOME_DIR
        working_directories[user_id] = HOME_DIR

    if not os.access(
        current_dir,
        os.X_OK | os.R_OK,
    ):
        return (
            "No tienes permisos para acceder "
            "al directorio actual."
        )

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
            start_new_session=True,
        )

    except (OSError, asyncio.SubprocessError):
        return (
            "No se pudo iniciar el comando. "
            "Revisa los permisos y el registro."
        )

    # ======================================
    # CONTROL DE TERMINACION
    # ======================================

    termination_lock = asyncio.Lock()

    termination_state = {
        "terminated": False,
    }

    async def terminate():
        await terminate_process_group(
            process,
            termination_lock,
            termination_state,
        )

    # ======================================
    # LEER SALIDAS SIMULTANEAMENTE
    # ======================================

    stdout_task = asyncio.create_task(
        read_limited(
            process.stdout,
            terminate,
        )
    )

    stderr_task = asyncio.create_task(
        read_limited(
            process.stderr,
            terminate,
        )
    )

    gather_task = asyncio.gather(
        stdout_task,
        stderr_task,
        process.wait(),
    )

    # ======================================
    # CONTROLAR TIEMPO DE EJECUCION
    # ======================================

    timed_out = False

    try:

        await asyncio.wait_for(
            asyncio.shield(gather_task),
            timeout=COMMAND_TIMEOUT,
        )

    except asyncio.TimeoutError:

        timed_out = True

        # Proteger la terminación frente a cancelaciones.
        await asyncio.shield(terminate())

        try:
            await asyncio.wait_for(
                asyncio.shield(gather_task),
                timeout=PIPE_CLEANUP_TIMEOUT,
            )

        except asyncio.TimeoutError:

            await cancel_reader_tasks(
                stdout_task,
                stderr_task,
                gather_task,
            )

    except asyncio.CancelledError:

        # Si se cancela el comando, terminar también
        # sus procesos secundarios.
        await asyncio.shield(terminate())

        await cancel_reader_tasks(
            stdout_task,
            stderr_task,
            gather_task,
        )

        raise

    except Exception:

        await asyncio.shield(terminate())

        await cancel_reader_tasks(
            stdout_task,
            stderr_task,
            gather_task,
        )

        return (
            "Ocurrió un error durante la ejecución "
            "del comando."
        )

    # ======================================
    # RECUPERAR RESULTADOS
    # ======================================

    if (
        stdout_task.cancelled()
        or stderr_task.cancelled()
        or stdout_task.done() is False
        or stderr_task.done() is False
    ):
        return (
            "El comando terminó, pero no se pudo "
            "recuperar toda la salida."
        )

    if stdout_task.exception() or stderr_task.exception():
        return (
            "Ocurrió un error al recuperar "
            "la salida del comando."
        )

    stdout, stdout_exceeded = stdout_task.result()
    stderr, stderr_exceeded = stderr_task.result()

    # ======================================
    # PREPARAR RESULTADO
    # ======================================

    output = stdout.decode(
        errors="replace"
    ).strip()

    errors = stderr.decode(
        errors="replace"
    ).strip()

    result = output

    if errors:
        result += (
            "\n" if result else ""
        ) + errors

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
