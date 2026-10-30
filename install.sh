
#!/usr/bin/env bash
set -Eeuo pipefail

# ==========================================
# RASPBERRY TELEBOT INSTALLER
# ==========================================

APP_NAME="raspberry-telebot-installer"
APP_DIR="/opt/${APP_NAME}"
CONFIG_DIR="/etc/raspberry-telebot-installer"

SERVICE_TELEGRAM="telegram-bot.service"
SERVICE_UPTERM="upterm.service"

# ==========================================
# COMPROBAR ROOT
# ==========================================

if [[ "$EUID" -ne 0 ]]; then
    echo "ERROR: ejecuta este instalador con sudo."
    echo "Ejemplo: sudo bash install.sh"
    exit 1
fi

# ==========================================
# LOCALIZAR REPOSITORIO
# ==========================================

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo " RASPBERRY TELEBOT INSTALLER"
echo "=========================================="

echo "Origen: $SOURCE_DIR"
echo "Destino: $APP_DIR"

# ==========================================
# VALIDAR ESTRUCTURA
# ==========================================

REQUIRED_FILES=(
    "requirements.txt"
    "bot/bot.py"
    "bot/terminal.py"
    "bot/upterm.py"
    "systemd/telegram-bot.service"
    "systemd/upterm.service"
    "scripts/install_dependencies.sh"
    "scripts/configure_security.sh"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [[ ! -f "$SOURCE_DIR/$file" ]]; then
        echo "ERROR: falta el archivo $file"
        exit 1
    fi
done

# ==========================================
# COMPROBAR SISTEMA
# ==========================================

if ! command -v apt-get >/dev/null 2>&1; then
    echo "ERROR: se requiere Debian o Ubuntu."
    exit 1
fi

ARCH="$(dpkg --print-architecture)"

if [[ "$ARCH" != "arm64" && "$ARCH" != "amd64" ]]; then
    echo "ERROR: arquitectura no compatible: $ARCH"
    exit 1
fi

# ==========================================
# INSTALAR DEPENDENCIAS
# ==========================================

echo
echo "[1/7] Instalando dependencias..."

bash "$SOURCE_DIR/scripts/install_dependencies.sh"

# ==========================================
# COPIAR PROYECTO
# ==========================================

echo
echo "[2/7] Instalando archivos del proyecto..."

install -d -m 0755 "$APP_DIR"

if [[ "$(realpath "$SOURCE_DIR")" != "$(realpath "$APP_DIR")" ]]; then
    cp -a "$SOURCE_DIR/." "$APP_DIR/"
fi

chown -R root:root "$APP_DIR"

# ==========================================
# CREAR ENTORNO PYTHON
# ==========================================

echo
echo "[3/7] Preparando entorno Python..."

if [[ ! -d "$APP_DIR/venv" ]]; then
    python3 -m venv "$APP_DIR/venv"
fi

"$APP_DIR/venv/bin/python" -m pip install --upgrade pip

"$APP_DIR/venv/bin/python" -m pip install \
    -r "$APP_DIR/requirements.txt"

# ==========================================
# CONFIGURAR SEGURIDAD
# ==========================================

echo
echo "[4/7] Configurando usuario y credenciales..."

bash "$APP_DIR/scripts/configure_security.sh"

# ==========================================
# INSTALAR SERVICIOS SYSTEMD
# ==========================================

echo
echo "[5/7] Instalando servicios..."

install -m 0644 \
    "$APP_DIR/systemd/telegram-bot.service" \
    "/etc/systemd/system/$SERVICE_TELEGRAM"

install -m 0644 \
    "$APP_DIR/systemd/upterm.service" \
    "/etc/systemd/system/$SERVICE_UPTERM"

systemctl daemon-reload

# ==========================================
# HABILITAR INICIO AUTOMATICO
# ==========================================

echo
echo "[6/7] Habilitando inicio automático..."

systemctl enable "$SERVICE_TELEGRAM"
systemctl enable "$SERVICE_UPTERM"

# ==========================================
# INICIAR O REINICIAR SERVICIOS
# ==========================================

echo
echo "[7/7] Iniciando servicios..."

for service in "$SERVICE_TELEGRAM" "$SERVICE_UPTERM"; do

    if systemctl is-active --quiet "$service"; then
        systemctl restart "$service"
    else
        systemctl start "$service"
    fi

done

# ==========================================
# RESULTADO
# ==========================================

echo
echo "=========================================="
echo " INSTALACION COMPLETADA"
echo "=========================================="

echo
echo "Bot Telegram:"
systemctl --no-pager --full status "$SERVICE_TELEGRAM" || true

echo
echo "Upterm:"
systemctl --no-pager --full status "$SERVICE_UPTERM" || true

echo
echo "Directorio: $APP_DIR"
echo "Configuración: $CONFIG_DIR/bot.env"

echo
echo "Para consultar los registros:"
echo "sudo journalctl -u telegram-bot.service -f"
echo "sudo journalctl -u upterm.service -f"

echo
echo "La Raspberry está configurada para iniciar"
echo "ambos servicios automáticamente."
