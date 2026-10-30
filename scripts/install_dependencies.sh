
#!/usr/bin/env bash
set -Eeuo pipefail

# ==========================================
# INSTALADOR DE DEPENDENCIAS
# ==========================================

UPTERM_VERSION="v0.40.0"

echo "======================================"
echo " INSTALADOR DE DEPENDENCIAS"
echo "======================================"

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
        ;;
    amd64)
        UPTERM_ARCH="amd64"
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
trap 'rm -rf "$TMP_DIR"' EXIT

# ==========================================
# DESCARGAR Y VERIFICAR UPT​ERM
# ==========================================

python3 - "$UPTERM_VERSION" "$UPTERM_ARCH" "$TMP_DIR" <<'PY'
import hashlib
import json
import pathlib
import re
import sys
import tarfile
import urllib.request

version = sys.argv[1]
arch = sys.argv[2]
directory = pathlib.Path(sys.argv[3])

api = (
    "https://api.github.com/repos/owenthereal/upterm"
    f"/releases/tags/{version}"
)

def download(url, destination):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "raspberry-telebot-installer"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=120
    ) as response:
        destination.write_bytes(response.read())


# Obtener versión exacta

request = urllib.request.Request(
    api,
    headers={
        "User-Agent": "raspberry-telebot-installer"
    }
)

with urllib.request.urlopen(
    request,
    timeout=30
) as response:
    release = json.load(response)

if release.get("tag_name") != version:
    raise SystemExit("ERROR: versión de Upterm inesperada.")

assets = {
    item["name"]: item
    for item in release["assets"]
}

archive_name = f"upterm_linux_{arch}.tar.gz"

if archive_name not in assets:
    raise SystemExit(
        f"No existe el paquete oficial: {archive_name}"
    )

if "checksums.txt" not in assets:
    raise SystemExit(
        "No se encontró checksums.txt."
    )

# Descargar archivos oficiales

archive = directory / archive_name
checksums = directory / "checksums.txt"

download(
    assets[archive_name]["browser_download_url"],
    archive
)

download(
    assets["checksums.txt"]["browser_download_url"],
    checksums
)

# Buscar SHA256

expected = None

for line in checksums.read_text().splitlines():
    parts = line.split()

    if len(parts) >= 2:
        filename = parts[-1].lstrip("*")

        if filename == archive_name:
            expected = parts[0]
            break

if not expected or not re.fullmatch(
    r"[a-fA-F0-9]{64}",
    expected
):
    raise SystemExit(
        "ERROR: SHA256 no válido o inexistente."
    )

# Verificar integridad

actual = hashlib.sha256(
    archive.read_bytes()
).hexdigest()

if actual.lower() != expected.lower():
    raise SystemExit(
        "ERROR: la verificación SHA256 falló."
    )

print(f"Versión: {version}")
print("SHA256 verificado correctamente.")

# Inspeccionar el archivo sin extraer rutas arbitrarias

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

    binary = tar.extractfile(candidates[0])

    if binary is None:
        raise SystemExit(
            "ERROR: no se pudo leer el ejecutable."
        )

    binary_path = directory / "upterm"
    binary_path.write_bytes(binary.read())

if binary_path.stat().st_size == 0:
    raise SystemExit(
        "ERROR: el ejecutable descargado está vacío."
    )

print("Ejecutable Upterm extraído y validado.")

PY

# ==========================================
# INSTALAR UPT​ERM
# ==========================================

echo
echo "Instalando Upterm CLI..."

install -m 0755 \
    "$TMP_DIR/upterm" \
    /usr/local/bin/upterm

# ==========================================
# VERIFICAR INSTALACION
# ==========================================

echo
echo "======================================"
echo " VERIFICACION"
echo "======================================"

/usr/local/bin/upterm version

echo
echo "Upterm CLI instalado correctamente."
echo "Versión: $UPTERM_VERSION"
echo "Arquitectura: $UPTERM_ARCH"
echo "Ejecutable: /usr/local/bin/upterm"
echo "Relay: wss://uptermd.upterm.dev"

echo
echo "Instalación de dependencias terminada."
