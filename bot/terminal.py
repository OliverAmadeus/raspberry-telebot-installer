
import asyncio
import os
from pathlib import Path

# Directorio inicial de trabajo
HOME_DIR = str(Path.home())

# Directorio de trabajo independiente de cada sesión
working_directories = {}


def get_working_directory(user_id):
    return working_directories.get(user_id, HOME_DIR)


async def execute_command(user_id, command):
    """
    Ejecuta comandos Linux mediante Bash.
    Cada usuario conserva su propio directorio de trabajo.
    """

    command = command.strip()

    if not command:
        return "No se recibió ningún comando."

    current_dir = get_working_directory(user_id)

    # Cambio de directorio persistente
    if command == "cd":
        working_directories[user_id] = HOME_DIR
        return f"Directorio: {HOME_DIR}"

    if command.startswith("cd "):
        destination = command[3:].strip()

        if destination == "~":
            destination = HOME_DIR
        elif destination.startswith("~/"):
            destination = os.path.join(HOME_DIR, destination[2:])
        elif not os.path.isabs(destination):
            destination = os.path.join(current_dir, destination)

        destination = os.path.abspath(destination)

        if os.path.isdir(destination):
            working_directories[user_id] = destination
            return f"Directorio cambiado a:\n{destination}"

        return f"No existe el directorio:\n{destination}"

    # Ejecutar comando con Bash
    process = await asyncio.create_subprocess_exec(
        "/bin/bash",
        "-lc",
        command,
        cwd=current_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=120
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return "El comando superó el límite de 120 segundos."

    output = stdout.decode(errors="replace").strip()
    errors = stderr.decode(errors="replace").strip()

    result = output

    if errors:
        result += ("\n" if result else "") + errors

    if not result:
        result = f"Comando finalizado. Código de salida: {process.returncode}"

    return result
