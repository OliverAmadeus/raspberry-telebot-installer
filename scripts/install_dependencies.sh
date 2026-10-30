
#!/usr/bin/env bash
set -Eeuo pipefail

echo "======================================"
echo " Instalando dependencias del sistema"
echo "======================================"

if [[ "$EUID" -ne 0 ]]; then
    echo "ERROR: ejecuta este script como root."
    exit 1
fi

apt-get update

apt-get install -y \
    git \
    curl \
    ca-certificates \
    python3 \
    python3-venv \
    python3-pip \
    tar

echo
echo "======================================"
echo " Detectando arquitectura"
echo "======================================"

ARCH="$(dpkg --print-architecture)"

case "$ARCH" in
    arm64)
        UPTERM_ARCH="arm64"
        ;;
    amd64)
        UPTERM_ARCH="amd64"
        ;;
    *)
        echo "Arquitectura no compatible: $ARCH"
        exit 1
        ;;
esac

echo "Arquitectura: $ARCH"

echo
echo "======================================"
echo " Descargando Upterm oficial"
echo "======================================"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

python3 - "$UPTERM_ARCH" "$TMP_DIR" <<'PY'
import hashlib
import json
import pathlib
import sys
import urllib.request

arch = sys.argv[1]
directory = pathlib.Path(sys.argv[2])

api = "https://api.github.com/repos/owenthereal/upterm/releases/latest"

request = urllib.request.Request(
    api,
    headers={"User-Agent": "raspberry-telebot-installer"}
)

with urllib.request.urlopen(request, timeout=30) as response:
    release = json.load(response)

assets = {item["name"]: item for item in release["assets"]}

binary_name = f"upterm_linux_{arch}.tar.gz"

if binary_name not in assets or "checksums.txt" not in assets:
    raise SystemExit("No se encontraron los archivos oficiales de Upterm.")

def download(url, destination):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "raspberry-telebot-installer"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        destination.write_bytes(response.read())

archive = directory / binary_name
checksums = directory / "checksums.txt"

download(assets[binary_name]["browser_download_url"], archive)
download(assets["checksums.txt"]["browser_download_url"], checksums)

expected = None

for line in checksums.read_text().splitlines():
    parts = line.split()
    if len(parts) >= 2 and parts[-1].lstrip("*") == binary_name:
        expected = parts[0]
        break

if not expected:
    raise SystemExit("No se encontró el SHA256 del archivo.")

actual = hashlib.sha256(archive.read_bytes()).hexdigest()

if actual.lower() != expected.lower():
    raise SystemExit("ERROR: la verificación SHA256 falló.")

print(f"Versión: {release['tag_name']}")
print("SHA256 verificado correctamente.")
PY

tar -xzf "$TMP_DIR/upterm_linux_${UPTERM_ARCH}.tar.gz" -C "$TMP_DIR"

UPTERM_BIN="$(find "$TMP_DIR" -type f -name upterm -print -quit)"

if [[ -z "$UPTERM_BIN" ]]; then
    echo "ERROR: no se encontró el ejecutable Upterm."
    exit 1
fi

install -m 0755 "$UPTERM_BIN" /usr/local/bin/upterm

echo
echo "======================================"
echo " Instalación completada"
echo "======================================"

upterm version
echo "Dependencias instaladas correctamente."
