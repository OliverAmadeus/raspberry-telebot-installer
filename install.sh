
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

SERVICES=(
    "$SERVICE_TELEGRAM"
    "$SERVICE_UPTERM"
)

# ==========================================
# MANEJO DE ERRORES
# ==========================================

error_handler() {
    local exit_code=$?

    echo
    echo "=========================================="
    echo " ERROR DURANTE LA INSTALACION"
    echo "=========================================="

    echo "Código de salida: $exit_code"
    echo "La instalación no puede considerarse completa."

    echo
    echo "Revisa los registros con:"
    echo "journalctl -u telegram-bot.service -n 50 --no-pager"
    echo "journalctl -u upterm.service -n 50 --no-pager"

    exit "$exit_code"
}

trap error_handler ERR

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

SOURCE_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")" &&
    pwd
)"

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

REQUIRED_COMMANDS=(
    apt-get
    dpkg
    systemctl
    systemd-analyze
    realpath
    install
    cp
    python3
    bash
)

for command in "${REQUIRED_COMMANDS[@]}"; do

    if ! command -v "$command" >/dev/null 2>&1; then
        echo "ERROR: no se encontró el comando $command."
        exit 1
    fi

done

# ==========================================
# VALIDAR SISTEMA OPERATIVO
# ==========================================

if [[ ! -f /etc/os-release ]]; then
    echo "ERROR: no se pudo identificar el sistema operativo."
    exit 1
fi

source /etc/os-release

OS_ID="${ID:-}"
OS_LIKE="${ID_LIKE:-}"

if [[ "$OS_ID" != "ubuntu" &&
      "$OS_ID" != "debian" &&
      "$OS_LIKE" != *debian* ]]; then

    echo "ERROR: sistema operativo no compatible."
    echo "Sistema detectado: ${PRETTY_NAME:-desconocido}"
    exit 1

fi

echo "Sistema operativo: ${PRETTY_NAME:-desconocido}"

# ==========================================
# DETECTAR ARQUITECTURA
# ==========================================

ARCH="$(dpkg --print-architecture)"

if [[ "$ARCH" != "arm64" && "$ARCH" != "amd64" ]]; then

    echo "ERROR: arquitectura no compatible: $ARCH"
    exit 1

fi

echo "Arquitectura: $ARCH"

# ==========================================
# COMPROBAR SYSTEMD
# ==========================================

if ! systemctl is-system-running >/dev/null 2>&1; then

    echo "AVISO: systemd no informa un estado completamente operativo."
    echo "Se continuará, pero la activación de servicios podría fallar."

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

if [[ -L "$APP_DIR" ]]; then
    echo "ERROR: el directorio de instalación no puede ser un enlace simbólico."
    exit 1
fi

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

if [[ ! -x "$APP_DIR/venv/bin/python" ]]; then
    echo "ERROR: el entorno virtual de Python no es válido."
    exit 1
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

for service in "${SERVICES[@]}"; do

    if [[ ! -s "$APP_DIR/systemd/$service" ]]; then
        echo "ERROR: servicio vacío: $service"
        exit 1
    fi

    install -m 0644 \
        "$APP_DIR/systemd/$service" \
        "/etc/systemd/system/$service"

done

systemctl daemon-reload

# ==========================================
# VALIDAR SERVICIOS
# ==========================================

echo
echo "Validando configuración de systemd..."

systemd-analyze verify \
    "/etc/systemd/system/$SERVICE_TELEGRAM" \
    "/etc/systemd/system/$SERVICE_UPTERM"

echo "Configuración de systemd válida."

# ==========================================
# HABILITAR INICIO AUTOMATICO
# ==========================================

echo
echo "[6/7] Habilitando inicio automático..."

for service in "${SERVICES[@]}"; do

    systemctl enable "$service"

    systemctl reset-failed "$service" || true

done

# ==========================================
# INICIAR SERVICIOS
# ==========================================

echo
echo "[7/7] Iniciando servicios..."

for service in "${SERVICES[@]}"; do

    echo
    echo "Iniciando $service..."

    if systemctl is-active --quiet "$service"; then

        systemctl restart "$service"

    else

        systemctl start "$service"

    fi

    # Dar tiempo al proceso para iniciar.

    sleep 3

    # Verificar estado.

    if ! systemctl is-active --quiet "$service"; then

        echo "ERROR: $service no está activo."

        systemctl --no-pager --full status "$service" || true

        journalctl -u "$service" -n 40 --no-pager || true

        exit 1

    fi

    # Verificar que exista un proceso principal.

    MAIN_PID="$(
        systemctl show \
            --property=MainPID \
            --value \
            "$service"
    )"

    if [[ ! "$MAIN_PID" =~ ^[1-9][0-9]*$ ]]; then

        echo "ERROR: $service no tiene un proceso principal activo."

        journalctl -u "$service" -n 40 --no-pager || true

        exit 1

    fi

    echo "$service: ACTIVO"
    echo "PID principal: $MAIN_PID"

done

# ==========================================
# RESULTADO
# ==========================================

trap - ERR

echo
echo "=========================================="
echo " INSTALACION COMPLETADA"
echo "=========================================="

echo
echo "Bot Telegram:"
systemctl --no-pager --full status "$SERVICE_TELEGRAM"

echo
echo "Upterm:"
systemctl --no-pager --full status "$SERVICE_UPTERM"

echo
echo "Directorio: $APP_DIR"
echo "Configuración: $CONFIG_DIR/bot.env"
echo "Claves de confianza: $CONFIG_DIR/upterm_known_hosts"

echo
echo "Registros:"
echo "sudo journalctl -u telegram-bot.service -f"
echo "sudo journalctl -u upterm.service -f"

echo
echo "Ambos servicios están activos y habilitados"
echo "para iniciar automáticamente con la Raspberry Pi."
