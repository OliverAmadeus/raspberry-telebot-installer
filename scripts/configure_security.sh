
#!/usr/bin/env bash
set -Eeuo pipefail

# ==========================================
# CONFIGURACION
# ==========================================

APP_USER="raspberry-telebot"
APP_GROUP="raspberry-telebot"

CONFIG_DIR="/etc/raspberry-telebot-installer"
CONFIG_FILE="${CONFIG_DIR}/bot.env"

STATE_DIR="/var/lib/raspberry-telebot"
SSH_DIR="${STATE_DIR}/.ssh"
KNOWN_HOSTS="${SSH_DIR}/known_hosts"

# Clave oficial publicada por el proyecto Upterm
UPTERM_KNOWN_HOSTS='
@cert-authority uptermd.upterm.dev ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICiecex8Dq718eSe1CCLgLvDmI7AagvCtax7brPFWkh4
@cert-authority [uptermd.upterm.dev]:443 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICiecex8Dq718eSe1CCLgLvDmI7AagvCtax7brPFWkh4
'

# ==========================================
# VALIDAR PERMISOS
# ==========================================

if [[ "$EUID" -ne 0 ]]; then
    echo "ERROR: ejecuta este script como root."
    exit 1
fi

echo "=========================================="
echo " CONFIGURANDO SEGURIDAD"
echo "=========================================="

# ==========================================
# CREAR GRUPO
# ==========================================

if ! getent group "$APP_GROUP" >/dev/null; then
    groupadd --system "$APP_GROUP"
fi

# ==========================================
# CREAR USUARIO
# ==========================================

if ! id "$APP_USER" >/dev/null 2>&1; then
    useradd \
        --system \
        --gid "$APP_GROUP" \
        --home-dir "$STATE_DIR" \
        --no-create-home \
        --shell /usr/sbin/nologin \
        "$APP_USER"
fi

# ==========================================
# CREAR DIRECTORIOS
# ==========================================

install -d \
    -o root \
    -g "$APP_GROUP" \
    -m 0750 \
    "$CONFIG_DIR"

install -d \
    -o "$APP_USER" \
    -g "$APP_GROUP" \
    -m 0750 \
    "$STATE_DIR"

# ==========================================
# CONFIGURAR CREDENCIALES
# ==========================================

if [[ ! -f "$CONFIG_FILE" ]]; then

    echo
    echo "CONFIGURACION DE TELEGRAM"
    echo "------------------------------------------"

    read -r -s -p "Token del bot de Telegram: " BOT_TOKEN
    echo

    read -r -p "Tu Telegram User ID: " TELEGRAM_ID

    echo
    echo "CONFIGURACION DE UPT​ERM"
    echo "------------------------------------------"

    read -r -p "Usuario GitHub autorizado [KaworuSSSS]: " GITHUB_USER

    GITHUB_USER="${GITHUB_USER:-KaworuSSSS}"

    if [[ -z "$BOT_TOKEN" ]]; then
        echo "ERROR: token vacío."
        exit 1
    fi

    if [[ ! "$TELEGRAM_ID" =~ ^[0-9]+$ ]]; then
        echo "ERROR: Telegram User ID no válido."
        exit 1
    fi

    if [[ ! "$GITHUB_USER" =~ ^[A-Za-z0-9-]+$ ]]; then
        echo "ERROR: usuario GitHub no válido."
        exit 1
    fi

    umask 027

    {
        printf 'TELEGRAM_BOT_TOKEN=%s\n' "$BOT_TOKEN"
        printf 'TELEGRAM_AUTHORIZED_USER_ID=%s\n' "$TELEGRAM_ID"
        printf 'UPTERM_SERVER=%s\n' "wss://uptermd.upterm.dev"
        printf 'UPTERM_AUTHORIZED_USER=%s\n' "github:${GITHUB_USER}"
    } > "$CONFIG_FILE"

    chown root:"$APP_GROUP" "$CONFIG_FILE"
    chmod 0640 "$CONFIG_FILE"

    unset BOT_TOKEN

    echo "Credenciales creadas."
else
    echo "Configuración existente: se conserva."
fi

# ==========================================
# INSTALAR CLAVE DEL RELAY
# ==========================================

echo
echo "Configurando clave oficial del relay Upterm..."

install -d \
    -o "$APP_USER" \
    -g "$APP_GROUP" \
    -m 0700 \
    "$SSH_DIR"

printf '%s\n' "$UPTERM_KNOWN_HOSTS" > "$KNOWN_HOSTS"

chown "$APP_USER":"$APP_GROUP" "$KNOWN_HOSTS"
chmod 0600 "$KNOWN_HOSTS"

# ==========================================
# PERMISOS FINALES
# ==========================================

chown root:"$APP_GROUP" "$CONFIG_DIR"
chmod 0750 "$CONFIG_DIR"

chown "$APP_USER":"$APP_GROUP" "$STATE_DIR"
chmod 0750 "$STATE_DIR"

echo
echo "=========================================="
echo " SEGURIDAD CONFIGURADA"
echo "=========================================="

echo "Usuario: $APP_USER"
echo "Configuración: $CONFIG_FILE"
echo "Claves verificadas: $KNOWN_HOSTS"

echo
echo "Permisos de credenciales:"
stat -c "%A %U:%G %n" "$CONFIG_FILE"

echo
echo "Permisos de known_hosts:"
stat -c "%A %U:%G %n" "$KNOWN_HOSTS"

echo
echo "Huella oficial documentada:"
echo "SHA256:9ajV8JqMe6jJE/s3TYjb/9xw7T0pfJ2+gADiBIJWDPE"

echo
echo "Configuración de seguridad terminada."
