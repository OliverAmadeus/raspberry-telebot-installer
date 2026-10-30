
#!/usr/bin/env bash
set -Eeuo pipefail

# ==========================================
# RASPBERRY TELEBOT - CONFIGURACION SEGURA
# ==========================================

APP_USER="raspberry-telebot"
APP_GROUP="raspberry-telebot"
APP_SHELL="/usr/sbin/nologin"

CONFIG_DIR="/etc/raspberry-telebot-installer"
CONFIG_FILE="${CONFIG_DIR}/bot.env"

STATE_DIR="/var/lib/raspberry-telebot"
SSH_DIR="${STATE_DIR}/.ssh"
KNOWN_HOSTS="${SSH_DIR}/known_hosts"

TEMP_CONFIG=""
TEMP_KNOWN_HOSTS=""

UPTERM_SERVER="wss://uptermd.upterm.dev"

UPTERM_KNOWN_HOSTS='
@cert-authority uptermd.upterm.dev ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICiecex8Dq718eSe1CCLgLvDmI7AagvCtax7brPFWkh4
@cert-authority [uptermd.upterm.dev]:443 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICiecex8Dq718eSe1CCLgLvDmI7AagvCtax7brPFWkh4
'

# ==========================================
# LIMPIEZA
# ==========================================

cleanup() {
    unset BOT_TOKEN TELEGRAM_ID
    unset EXISTING_TOKEN EXISTING_ID

    if [[ -n "$TEMP_CONFIG" && -f "$TEMP_CONFIG" ]]; then
        rm -f -- "$TEMP_CONFIG"
    fi

    if [[ -n "$TEMP_KNOWN_HOSTS" && -f "$TEMP_KNOWN_HOSTS" ]]; then
        rm -f -- "$TEMP_KNOWN_HOSTS"
    fi
}

trap cleanup EXIT

# ==========================================
# VALIDAR ROOT
# ==========================================

if [[ "$EUID" -ne 0 ]]; then
    echo "ERROR: ejecuta este script como root."
    exit 1
fi

echo "=========================================="
echo " CONFIGURANDO SEGURIDAD"
echo "=========================================="

# ==========================================
# VALIDAR RUTAS EXISTENTES
# ==========================================

for directory in "$CONFIG_DIR" "$STATE_DIR" "$SSH_DIR"; do
    if [[ -L "$directory" ]]; then
        echo "ERROR: no se permiten enlaces simbólicos: $directory"
        exit 1
    fi
done

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
        --shell "$APP_SHELL" \
        "$APP_USER"
fi

# ==========================================
# VALIDAR USUARIO EXISTENTE
# ==========================================

if [[ "$(id -gn "$APP_USER")" != "$APP_GROUP" ]]; then
    echo "ERROR: el grupo principal del usuario es incorrecto."
    exit 1
fi

PASSWD_ENTRY="$(getent passwd "$APP_USER")"

IFS=: read -r _ _ _ _ _ USER_HOME USER_SHELL <<< "$PASSWD_ENTRY"

if [[ "$USER_HOME" != "$STATE_DIR" ]]; then
    echo "ERROR: el directorio personal del usuario es incorrecto."
    exit 1
fi

if [[ "$USER_SHELL" != "$APP_SHELL" ]]; then
    echo "ERROR: el shell del usuario no es el esperado."
    exit 1
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

# Validar nuevamente antes de utilizar SSH_DIR.
if [[ -L "$SSH_DIR" ]]; then
    echo "ERROR: SSH_DIR no puede ser un enlace simbólico."
    exit 1
fi

install -d \
    -o "$APP_USER" \
    -g "$APP_GROUP" \
    -m 0700 \
    "$SSH_DIR"

# ==========================================
# VALIDAR ARCHIVO DE CONFIGURACION
# ==========================================

if [[ -L "$CONFIG_FILE" ]]; then
    echo "ERROR: bot.env no puede ser un enlace simbólico."
    exit 1
fi

if [[ -e "$CONFIG_FILE" && ! -f "$CONFIG_FILE" ]]; then
    echo "ERROR: bot.env no es un archivo regular."
    exit 1
fi

# ==========================================
# OBTENER CREDENCIALES
# ==========================================

BOT_TOKEN=""
TELEGRAM_ID=""

if [[ -f "$CONFIG_FILE" ]]; then

    echo
    echo "Configuración existente encontrada."
    echo "Se conservarán las credenciales de Telegram."

    if [[ ! -s "$CONFIG_FILE" ]]; then
        echo "ERROR: bot.env está vacío."
        exit 1
    fi

    if [[ "$(grep -Ec '^TELEGRAM_BOT_TOKEN=[0-9]+:[A-Za-z0-9_-]+$' "$CONFIG_FILE" || true)" -ne 1 ]]; then
        echo "ERROR: token de Telegram incorrecto o duplicado."
        exit 1
    fi

    if [[ "$(grep -Ec '^TELEGRAM_AUTHORIZED_USER_ID=[0-9]+$' "$CONFIG_FILE" || true)" -ne 1 ]]; then
        echo "ERROR: Telegram User ID incorrecto o duplicado."
        exit 1
    fi

    if [[ "$(grep -Ec '^UPTERM_SERVER=wss://uptermd\.upterm\.dev$' "$CONFIG_FILE" || true)" -ne 1 ]]; then
        echo "ERROR: servidor Upterm incorrecto o duplicado."
        exit 1
    fi

    # Permitir las antiguas variables GitHub únicamente
    # para eliminarlas durante esta actualización.
    if grep -Ev \
        '^(TELEGRAM_BOT_TOKEN=[0-9]+:[A-Za-z0-9_-]+|TELEGRAM_AUTHORIZED_USER_ID=[0-9]+|UPTERM_SERVER=wss://uptermd\.upterm\.dev|UPTERM_AUTHORIZED_USER=github:[A-Za-z0-9-]+|UPTERM_AUTHORIZED_USER_2=github:[A-Za-z0-9-]+|[[:space:]]*|[[:space:]]*#.*)$' \
        "$CONFIG_FILE" >/dev/null; then

        echo "ERROR: bot.env contiene variables no reconocidas."
        exit 1
    fi

    EXISTING_TOKEN="$(sed -n 's/^TELEGRAM_BOT_TOKEN=//p' "$CONFIG_FILE")"
    EXISTING_ID="$(sed -n 's/^TELEGRAM_AUTHORIZED_USER_ID=//p' "$CONFIG_FILE")"

    BOT_TOKEN="$EXISTING_TOKEN"
    TELEGRAM_ID="$EXISTING_ID"

else

    echo
    echo "CONFIGURACION DE TELEGRAM"
    echo "------------------------------------------"

    read -r -s -p "Token del bot de Telegram: " BOT_TOKEN
    echo

    read -r -p "Tu Telegram User ID: " TELEGRAM_ID

fi

# ==========================================
# VALIDAR CREDENCIALES
# ==========================================

if [[ ! "$BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]]; then
    echo "ERROR: formato del token de Telegram no válido."
    exit 1
fi

if [[ ! "$TELEGRAM_ID" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Telegram User ID no válido."
    exit 1
fi

# ==========================================
# GENERAR CONFIGURACION CANONICA
# ==========================================

echo
echo "Generando configuración sin autorización GitHub..."

umask 077

TEMP_CONFIG="$(mktemp "${CONFIG_DIR}/.bot.env.XXXXXX")"

{
    printf 'TELEGRAM_BOT_TOKEN=%s\n' "$BOT_TOKEN"
    printf 'TELEGRAM_AUTHORIZED_USER_ID=%s\n' "$TELEGRAM_ID"
    printf 'UPTERM_SERVER=%s\n' "$UPTERM_SERVER"
} > "$TEMP_CONFIG"

chown root:"$APP_GROUP" "$TEMP_CONFIG"
chmod 0640 "$TEMP_CONFIG"

mv -fT -- "$TEMP_CONFIG" "$CONFIG_FILE"
TEMP_CONFIG=""

# ==========================================
# CONFIGURAR CONFIANZA SSH DE UPT​​ERM
# ==========================================

echo
echo "Configurando confianza SSH de Upterm..."

if [[ -L "$SSH_DIR" ]]; then
    echo "ERROR: SSH_DIR no puede ser un enlace simbólico."
    exit 1
fi

if [[ -L "$KNOWN_HOSTS" ]]; then
    echo "ERROR: known_hosts no puede ser un enlace simbólico."
    exit 1
fi

if [[ -e "$KNOWN_HOSTS" && ! -f "$KNOWN_HOSTS" ]]; then
    echo "ERROR: known_hosts no es un archivo regular."
    exit 1
fi

TEMP_KNOWN_HOSTS="$(mktemp "${SSH_DIR}/.known_hosts.XXXXXX")"

printf '%s\n' "$UPTERM_KNOWN_HOSTS" > "$TEMP_KNOWN_HOSTS"

chown "$APP_USER":"$APP_GROUP" "$TEMP_KNOWN_HOSTS"
chmod 0600 "$TEMP_KNOWN_HOSTS"

mv -fT -- "$TEMP_KNOWN_HOSTS" "$KNOWN_HOSTS"
TEMP_KNOWN_HOSTS=""

# ==========================================
# PERMISOS FINALES
# ==========================================

chown root:"$APP_GROUP" "$CONFIG_DIR"
chmod 0750 "$CONFIG_DIR"

chown root:"$APP_GROUP" "$CONFIG_FILE"
chmod 0640 "$CONFIG_FILE"

chown "$APP_USER":"$APP_GROUP" "$STATE_DIR"
chmod 0750 "$STATE_DIR"

chown "$APP_USER":"$APP_GROUP" "$SSH_DIR"
chmod 0700 "$SSH_DIR"

chown "$APP_USER":"$APP_GROUP" "$KNOWN_HOSTS"
chmod 0600 "$KNOWN_HOSTS"

# ==========================================
# RESULTADO
# ==========================================

echo
echo "=========================================="
echo " SEGURIDAD CONFIGURADA"
echo "=========================================="

echo "Usuario: $APP_USER"
echo "Grupo: $APP_GROUP"
echo "Configuración: $CONFIG_FILE"
echo "Directorio de estado: $STATE_DIR"
echo "Directorio SSH: $SSH_DIR"
echo "Claves de confianza: $KNOWN_HOSTS"

echo
echo "Autorización GitHub: desactivada"
echo "Servidor Upterm: $UPTERM_SERVER"
echo "SFTP/SCP: desactivado por la configuración del bot"

echo
echo "Permisos de configuración:"
stat -c "%A %U:%G %n" "$CONFIG_FILE"

echo
echo "Permisos de known_hosts:"
stat -c "%A %U:%G %n" "$KNOWN_HOSTS"

echo
echo "Configuración de seguridad terminada."
