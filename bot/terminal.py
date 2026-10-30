
import asyncio
import os
import shlex
import signal
from pathlib import Path


# ==========================================
# CONFIGURACION
# ==========================================

HOME_DIR = str(Path.home())

COMMAND_TIMEOUT = 120
MAX_OUTPUT_SIZE = 1024 * 1024  # 1 MiB por comando

# Directorio independiente por usuario Telegram
working_directories = {}


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

        destination = arguments[1] if len(arguments) == 2 else HOME_DIR

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
            return f"No existe el directorio:\n{destination}"

        working_directories[user_id] = destination

        return f"Directorio cambiado a:\n{destination}"

    except ValueError:
        return "Error: formato de directorio no válido."


# ==========================================
# EJECUTAR COMANDO
# ==========================================

async def execute_command(user_id, command):
    """
    Ejecuta comandos Linux mediante Bash.

    Características:
    - Comandos arbitrarios.
    - Directorio persistente por usuario.
    - Tiempo máximo de ejecución.
    - Límite de salida.
    - Terminación del grupo de procesos.
    """

    command = command.strip()

    if not command:
        return "No se recibió ningún comando."

    current_dir = get_working_directory(user_id)

    # ======================================
    # PROCESAR CD
    # ======================================

    if command == "cd" or command.startswith("cd "):
        return change_directory(user_id, command)

    # ======================================
    # VALIDAR DIRECTORIO
    # ======================================

    if not os.path.isdir(current_dir):
        current_dir = HOME_DIR
        working_directories[user_id] = HOME_DIR

    # ======================================
    # CREAR PROCESO
    # ======================================

    try:
        process = await asyncio.create_subprocess_exec(
            "/bin/bash",
            "-lc",
            command,
            cwd=current_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True
        )

    except Exception as error:
        return f"No se pudo iniciar el comando: {error}"

    # ======================================
    # CONTROLAR TIEMPO Y SALIDA
    # ======================================

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=COMMAND_TIMEOUT
        )

    except asyncio.TimeoutError:

        try:
            os.killpg(process.pid, signal.SIGTERM)

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

        except ProcessLookupError:
            pass

        return (
            f"El comando superó el límite de "
            f"{COMMAND_TIMEOUT} segundos."
        )

    # ======================================
    # CONTROLAR TAMAÑO DE SALIDA
    # ======================================

    truncated = False

    if len(stdout) > MAX_OUTPUT_SIZE:
        stdout = stdout[:MAX_OUTPUT_SIZE]
        truncated = True

    if len(stderr) > MAX_OUTPUT_SIZE:
        stderr = stderr[:MAX_OUTPUT_SIZE]
        truncated = True

    # ======================================
    # PREPARAR RESULTADO
    # ======================================

    output = stdout.decode(errors="replace").strip()
    errors = stderr.decode(errors="replace").strip()

    result = output

    if errors:
        result += ("\n" if result else "") + errors

    if truncated:
        result += (
            "\n\n[Salida truncada: se alcanzó el límite "
            "de 1 MiB por canal.]"
        )

    if not result:
        result = (
            f"Comando finalizado. "
            f"Código de salida: {process.returncode}"
        )

    return result
