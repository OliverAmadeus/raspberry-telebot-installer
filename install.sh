
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

SYSTEMD_DIR="/etc/systemd/system"

# Carpetas administradas por el repositorio.
SYNC_DIRS=(
    "bot"
    "systemd"
    "config"
    "scripts"
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
    "README.md"
    "requirements.txt"
    "install.sh"
    "bot/bot.py"
    "bot/terminal.py"
    "bot/upterm.py"
    "systemd/telegram-bot.service"
    "scripts/install_dependencies.sh"
    "scripts/configure_security.sh"
)

for file in "${REQUIRED_FILES[@]}"; do

    if [[ ! -f "$SOURCE_DIR/$file" ]]; then
        echo "ERROR: falta el archivo $file"
        exit 1
    fi

done

for directory in "${SYNC_DIRS[@]}"; do

    if [[ ! -d "$SOURCE_DIR/$directory" ]]; then
        echo "ERROR: falta el directorio $directory"
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
    getent
    id
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
    echo "Se continuará, pero la activación podría fallar."

fi

# ==========================================
# INSTALAR DEPENDENCIAS
# ==========================================

echo
echo "[1/7] Instalando dependencias..."

bash "$SOURCE_DIR/scripts/install_dependencies.sh"

if ! command -v rsync >/dev/null 2>&1; then
    echo "ERROR: rsync no está disponible."
    echo "Debe instalarse mediante install_dependencies.sh."
    exit 1
fi

# ==========================================
# VALIDAR DESTINO
# ==========================================

echo
echo "[2/7] Preparando directorio de instalación..."

if [[ -L "$APP_DIR" ]]; then
    echo "ERROR: el directorio de instalación no puede ser un enlace simbólico."
    exit 1
fi

install -d -o root -g root -m 0755 "$APP_DIR"

if [[ ! -d "$APP_DIR" ]]; then
    echo "ERROR: no se pudo preparar el directorio de instalación."
    exit 1
fi

# ==========================================
# SINCRONIZAR PROYECTO
# ==========================================

echo
echo "Sincronizando archivos con el repositorio..."

if [[ "$(realpath "$SOURCE_DIR")" != "$(realpath "$APP_DIR")" ]]; then

    for directory in "${SYNC_DIRS[@]}"; do

        TARGET_DIR="$APP_DIR/$directory"

        if [[ -L "$TARGET_DIR" ]]; then
            echo "ERROR: destino no permitido: $TARGET_DIR"
            exit 1
        fi

        install -d -o root -g root -m 0755 "$TARGET_DIR"

        echo "Sincronizando: $directory"

        rsync -a \
            --delete \
            --exclude="bot.env" \
            --exclude="*.local" \
            "$SOURCE_DIR/$directory/" \
            "$TARGET_DIR/"

    done

    # Sincronizar archivos principales.
    install -o root -g root -m 0644 \
        "$SOURCE_DIR/README.md" \
        "$APP_DIR/README.md"

    install -o root -g root -m 0644 \
        "$SOURCE_DIR/requirements.txt" \
        "$APP_DIR/requirements.txt"

    install -o root -g root -m 0755 \
        "$SOURCE_DIR/install.sh" \
        "$APP_DIR/install.sh"

else

    echo "El origen y el destino son el mismo directorio."
    echo "Se omite la sincronización para evitar sobrescribir archivos."

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
# RETIRAR SERVICIO INDEPENDIENTE DE UPT​​ERM
# ==========================================

echo
echo "[5/7] Retirando servicio independiente de Upterm..."

# Upterm se inicia desde el bot de Telegram.
# No debe existir una segunda unidad ejecutándolo.

if [[ -f "$SYSTEMD_DIR/$SERVICE_UPTERM" ||
      -L "$SYSTEMD_DIR/$SERVICE_UPTERM" ]]; then

    systemctl stop "$SERVICE_UPTERM" || true
    systemctl disable "$SERVICE_UPTERM" || true

    rm -f "$SYSTEMD_DIR/$SERVICE_UPTERM"

fi

# Limpiar posibles enlaces de activación antiguos.
rm -f "$SYSTEMD_DIR/multi-user.target.wants/$SERVICE_UPTERM"

systemctl daemon-reload

systemctl reset-failed "$SERVICE_UPTERM" || true

# ==========================================
# INSTALAR SERVICIO DE TELEGRAM
# ==========================================

echo
echo "Instalando servicio de Telegram..."

if [[ ! -s "$APP_DIR/systemd/$SERVICE_TELEGRAM" ]]; then
    echo "ERROR: servicio de Telegram vacío."
    exit 1
fi

install -m 0644 \
    "$APP_DIR/systemd/$SERVICE_TELEGRAM" \
    "$SYSTEMD_DIR/$SERVICE_TELEGRAM"

systemctl daemon-reload

# ==========================================
# VALIDAR SERVICIO
# ==========================================

echo
echo "Validando configuración de systemd..."

systemd-analyze verify \
    "$SYSTEMD_DIR/$SERVICE_TELEGRAM"

echo "Configuración de systemd válida."

# ==========================================
# HABILITAR INICIO AUTOMATICO
# ==========================================

echo
echo "[6/7] Habilitando inicio automático..."

systemctl enable "$SERVICE_TELEGRAM"

systemctl reset-failed "$SERVICE_TELEGRAM" || true

# ==========================================
# INICIAR SERVICIO
# ==========================================

echo
echo "[7/7] Iniciando bot de Telegram..."

if systemctl is-active --quiet "$SERVICE_TELEGRAM"; then

    systemctl restart "$SERVICE_TELEGRAM"

else

    systemctl start "$SERVICE_TELEGRAM"

fi

sleep 3

if ! systemctl is-active --quiet "$SERVICE_TELEGRAM"; then

    echo "ERROR: el bot de Telegram no está activo."

    systemctl --no-pager --full status "$SERVICE_TELEGRAM" || true

    journalctl -u "$SERVICE_TELEGRAM" -n 40 --no-pager || true

    exit 1

fi

MAIN_PID="$(
    systemctl show \
        --property=MainPID \
        --value \
        "$SERVICE_TELEGRAM"
)"

if [[ ! "$MAIN_PID" =~ ^[1-9][0-9]*$ ]]; then

    echo "ERROR: el bot no tiene un proceso principal activo."

    journalctl -u "$SERVICE_TELEGRAM" -n 40 --no-pager || true

    exit 1

fi

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
echo "PID principal: $MAIN_PID"

echo
echo "Directorio: $APP_DIR"
echo "Configuración: $CONFIG_DIR/bot.env"
echo "Estado: /var/lib/raspberry-telebot"
echo "Claves de confianza:"
echo "/var/lib/raspberry-telebot/.ssh/known_hosts"

echo
echo "Servicio Telegram: habilitado"
echo "Inicio automático: activado"
echo "Servicio independiente Upterm: retirado"

echo
echo "Para consultar los registros:"
echo "sudo journalctl -u telegram-bot.service -f"

echo
echo "Para iniciar una sesión remota:"
echo "Envía /upterm iniciar al bot de Telegram."

echo
echo "La instalación terminó correctamente."
