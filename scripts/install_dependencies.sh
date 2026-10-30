
#!/usr/bin/env bash
set -Eeuo pipefail

# ==========================================
# RASPBERRY TELEBOT - DEPENDENCIAS
# ==========================================

UPTERM_VERSION="v0.40.0"
UPTERM_INSTALL="/usr/local/bin/upterm"

echo "=========================================="
echo " INSTALADOR DE DEPENDENCIAS"
echo "=========================================="

# ==========================================
# VALIDAR ROOT
# ==========================================

if [[ "$EUID" -ne 0 ]]; then
    echo "ERROR: ejecuta este script como root."
    exit 1
fi

# ==========================================
# DEPENDENCIAS DEL SISTEMA
# ==========================================

echo
echo "Instalando dependencias del sistema..."

apt-get update

apt-get install -y \
    git \
    curl \
    ca-certificates \
    python3 \
    python3-venv \
    python3-pip \
    tar

# ==========================================
# DETECTAR ARQUITECTURA
# ==========================================

ARCH="$(dpkg --print-architecture)"

case "$ARCH" in
    arm64)
        UPTERM_ARCH="arm64"
        EXPECTED_ELF_MACHINE=183
        ;;
    amd64)
        UPTERM_ARCH="amd64"
        EXPECTED_ELF_MACHINE=62
        ;;
    *)
        echo "ERROR: arquitectura no compatible: $ARCH"
        exit 1
        ;;
esac

echo "Arquitectura: $ARCH"
echo "Upterm: $UPTERM_VERSION"

# ==========================================
# DIRECTORIO TEMPORAL
# ==========================================

TMP_DIR="$(mktemp -d)"

cleanup() {
    rm -rf -- "$TMP_DIR"
}

trap cleanup EXIT

# ==========================================
# DESCARGAR Y VERIFICAR UPT​​ERM
# ==========================================

python3 - \
    "$UPTERM_VERSION" \
    "$UPTERM_ARCH" \
    "$EXPECTED_ELF_MACHINE" \
    "$TMP_DIR" <<'PY'

import hashlib
import json
import pathlib
import re
import struct
import sys
import tarfile
import urllib.request

version = sys.argv[1]
arch = sys.argv[2]
expected_machine = int(sys.argv[3])
directory = pathlib.Path(sys.argv[4])

api = (
    "https://api.github.com/repos/owenthereal/upterm"
    f"/releases/tags/{version}"
)


def download(url, destination):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "raspberry-telebot-installer"
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=120,
    ) as response:
        destination.write_bytes(response.read())


# ==========================================
# OBTENER RELEASE OFICIAL
# ==========================================

request = urllib.request.Request(
    api,
    headers={
        "User-Agent": "raspberry-telebot-installer"
    },
)

with urllib.request.urlopen(
    request,
    timeout=30,
) as response:
    release = json.load(response)

if release.get("tag_name") != version:
    raise SystemExit(
        "ERROR: versión de Upterm inesperada."
    )

if release.get("draft") or release.get("prerelease"):
    raise SystemExit(
        "ERROR: el release no es una versión estable."
    )

assets = {
    item["name"]: item
    for item in release.get("assets", [])
}

archive_name = f"upterm_linux_{arch}.tar.gz"

if archive_name not in assets:
    raise SystemExit(
        f"ERROR: no existe el paquete oficial {archive_name}."
    )

if "checksums.txt" not in assets:
    raise SystemExit(
        "ERROR: no se encontró checksums.txt."
    )


# ==========================================
# DESCARGAR ARCHIVOS
# ==========================================

archive = directory / archive_name
checksums = directory / "checksums.txt"

download(
    assets[archive_name]["browser_download_url"],
    archive,
)

download(
    assets["checksums.txt"]["browser_download_url"],
    checksums,
)


# ==========================================
# VERIFICAR SHA256
# ==========================================

expected_hash = None

for line in checksums.read_text(
    encoding="utf-8"
).splitlines():

    parts = line.split()

    if len(parts) >= 2:

        filename = parts[-1].lstrip("*")

        if filename == archive_name:
            expected_hash = parts[0]
            break

if not expected_hash or not re.fullmatch(
    r"[a-fA-F0-9]{64}",
    expected_hash,
):
    raise SystemExit(
        "ERROR: SHA256 no válido o inexistente."
    )

actual_hash = hashlib.sha256(
    archive.read_bytes()
).hexdigest()

if actual_hash.lower() != expected_hash.lower():
    raise SystemExit(
        "ERROR: la verificación SHA256 falló."
    )

print("SHA256 verificado correctamente.")


# ==========================================
# EXTRAER EJECUTABLE DE FORMA SEGURA
# ==========================================

binary_path = directory / "upterm"

with tarfile.open(archive, "r:gz") as tar:

    candidates = [
        member
        for member in tar.getmembers()
        if pathlib.PurePosixPath(member.name).name == "upterm"
        and member.isfile()
    ]

    if len(candidates) != 1:
        raise SystemExit(
            "ERROR: el archivo no contiene un único "
            "ejecutable Upterm válido."
        )

    member = candidates[0]

    if member.size <= 0:
        raise SystemExit(
            "ERROR: el ejecutable está vacío."
        )

    if member.size > 100 * 1024 * 1024:
        raise SystemExit(
            "ERROR: tamaño inesperado del ejecutable."
        )

    binary = tar.extractfile(member)

    if binary is None:
        raise SystemExit(
            "ERROR: no se pudo leer el ejecutable."
        )

    binary_data = binary.read()

if len(binary_data) != member.size:
    raise SystemExit(
        "ERROR: el tamaño del ejecutable no coincide."
    )

if binary_data[:4] != b"\x7fELF":
    raise SystemExit(
        "ERROR: el archivo descargado no es un ejecutable ELF."
    )

if binary_data[4] != 2:
    raise SystemExit(
        "ERROR: se esperaba un ejecutable ELF de 64 bits."
    )

if binary_data[5] == 1:
    byte_order = "<"
elif binary_data[5] == 2:
    byte_order = ">"
else:
    raise SystemExit(
        "ERROR: formato ELF con endianness desconocido."
    )

machine = struct.unpack(
    byte_order + "H",
    binary_data[18:20],
)[0]

if machine != expected_machine:
    raise SystemExit(
        "ERROR: arquitectura ELF incorrecta. "
        f"Esperada: {expected_machine}; recibida: {machine}."
    )

binary_path.write_bytes(binary_data)

print(f"Versión: {version}")
print("Arquitectura ELF verificada correctamente.")
print("Ejecutable Upterm extraído y validado.")

PY

# ==========================================
# INSTALAR UPT​​ERM
# ==========================================

echo
echo "Instalando Upterm CLI..."

INSTALL_TEMP="$(mktemp /usr/local/bin/.upterm.XXXXXX)"

cleanup_install() {
    rm -f -- "$INSTALL_TEMP"
}

trap 'cleanup_install; cleanup' EXIT

install -m 0755 \
    "$TMP_DIR/upterm" \
    "$INSTALL_TEMP"

mv -fT -- "$INSTALL_TEMP" "$UPTERM_INSTALL"

# ==========================================
# VERIFICAR INSTALACION
# ==========================================

echo
echo "=========================================="
echo " VERIFICACION"
echo "=========================================="

VERSION_OUTPUT="$("$UPTERM_INSTALL" version)"

echo "$VERSION_OUTPUT"

if [[ "$VERSION_OUTPUT" != *"$UPTERM_VERSION"* ]]; then
    echo "ERROR: la versión instalada no coincide."
    exit 1
fi

if [[ ! -x "$UPTERM_INSTALL" ]]; then
    echo "ERROR: Upterm no tiene permisos de ejecución."
    exit 1
fi

# ==========================================
# RESULTADO
# ==========================================

echo
echo "=========================================="
echo " DEPENDENCIAS INSTALADAS"
echo "=========================================="

echo "Upterm: $UPTERM_VERSION"
echo "Arquitectura: $UPTERM_ARCH"
echo "Ejecutable: $UPTERM_INSTALL"
echo "Relay: wss://uptermd.upterm.dev"

echo
echo "Instalación de dependencias terminada."
