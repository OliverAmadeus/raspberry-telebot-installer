
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

TEMP_CONFIG=""

# Clave oficial publicada por el proyecto Upterm
UPTERM_KNOWN_HOSTS='
@cert-authority uptermd.upterm.dev ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICiecex8Dq718eSe1CCLgLvDmI7AagvCtax7brPFWkh4
@cert-authority [uptermd.upterm.dev]:443 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICiecex8Dq718eSe1CCLgLvDmI7AagvCtax7brPFWkh4
'

# ==========================================
# LIMPIEZA
# ==========================================

cleanup() {
    unset BOT_TOKEN TELEGRAM_ID GITHUB_USER

    if [[ -n "$TEMP_CONFIG" && -f "$TEMP_CONFIG" ]]; then
        rm -f -- "$TEMP_CONFIG"
    fi
}

trap cleanup EXIT

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

USER_GROUP="$(id -gn "$APP_USER")"

if [[ "$USER_GROUP" != "$APP_GROUP" ]]; then
    echo "ERROR: el usuario tiene un grupo principal inesperado."
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

# ==========================================
# VALIDAR ARCHIVO EXISTENTE
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
# CONFIGURAR CREDENCIALES
# ==========================================

if [[ ! -f "$CONFIG_FILE" ]]; then

    echo
    echo "CONFIGURACION DE TELEGRAM"
    echo "------------------------------------------"

    BOT_TOKEN=""
    TELEGRAM_ID=""
    GITHUB_USER=""

    read -r -s -p "Token del bot de Telegram: " BOT_TOKEN
    echo

    read -r -p "Tu Telegram User ID: " TELEGRAM_ID

    echo
    echo "CONFIGURACION DE UPT​ERM"
    echo "------------------------------------------"

    read -r -p "Usuario GitHub autorizado [KaworuSSSS]: " GITHUB_USER

    GITHUB_USER="${GITHUB_USER:-KaworuSSSS}"

    # Validar token

    if [[ ! "$BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]]; then
        echo "ERROR: formato del token de Telegram no válido."
        exit 1
    fi

    # Validar Telegram ID

    if [[ ! "$TELEGRAM_ID" =~ ^[0-9]+$ ]]; then
        echo "ERROR: Telegram User ID no válido."
        exit 1
    fi

    # Validar GitHub

    if [[ ! "$GITHUB_USER" =~ ^[A-Za-z0-9-]+$ ]]; then
        echo "ERROR: usuario GitHub no válido."
        exit 1
    fi

    # Crear archivo temporal protegido

    umask 077

    TEMP_CONFIG="$(mktemp "${CONFIG_DIR}/.bot.env.XXXXXX")"

    {
        printf 'TELEGRAM_BOT_TOKEN=%s\n' "$BOT_TOKEN"
        printf 'TELEGRAM_AUTHORIZED_USER_ID=%s\n' "$TELEGRAM_ID"
        printf 'UPTERM_SERVER=%s\n' "wss://uptermd.upterm.dev"
        printf 'UPTERM_AUTHORIZED_USER=%s\n' "github:${GITHUB_USER}"
    } > "$TEMP_CONFIG"

    chown root:"$APP_GROUP" "$TEMP_CONFIG"
    chmod 0640 "$TEMP_CONFIG"

    mv -f -- "$TEMP_CONFIG" "$CONFIG_FILE"
    TEMP_CONFIG=""

    echo "Credenciales creadas correctamente."

else
    echo
    echo "Configuración existente: se conserva."
fi

# ==========================================
# VALIDAR CONFIGURACION
# ==========================================

echo
echo "Validando archivo de configuración..."

if [[ ! -s "$CONFIG_FILE" ]]; then
    echo "ERROR: el archivo de configuración está vacío."
    exit 1
fi

# Debe contener exactamente cuatro líneas.

LINE_COUNT="$(wc -l < "$CONFIG_FILE")"

if [[ "$LINE_COUNT" -ne 4 ]]; then
    echo "ERROR: bot.env debe contener exactamente cuatro líneas."
    exit 1
fi

# Validar que cada variable aparezca exactamente una vez.

if [[ "$(grep -Ec '^TELEGRAM_BOT_TOKEN=[0-9]+:[A-Za-z0-9_-]+$' "$CONFIG_FILE")" -ne 1 ]]; then
    echo "ERROR: token de Telegram incorrecto o duplicado."
    exit 1
fi

if [[ "$(grep -Ec '^TELEGRAM_AUTHORIZED_USER_ID=[0-9]+$' "$CONFIG_FILE")" -ne 1 ]]; then
    echo "ERROR: Telegram User ID incorrecto o duplicado."
    exit 1
fi

if [[ "$(grep -Ec '^UPTERM_SERVER=wss://uptermd\.upterm\.dev$' "$CONFIG_FILE")" -ne 1 ]]; then
    echo "ERROR: servidor Upterm incorrecto o duplicado."
    exit 1
fi

if [[ "$(grep -Ec '^UPTERM_AUTHORIZED_USER=github:[A-Za-z0-9-]+$' "$CONFIG_FILE")" -ne 1 ]]; then
    echo "ERROR: usuario GitHub incorrecto o duplicado."
    exit 1
fi

# No permitir variables ni líneas adicionales.

if grep -Ev \
    '^(TELEGRAM_BOT_TOKEN=[0-9]+:[A-Za-z0-9_-]+|TELEGRAM_AUTHORIZED_USER_ID=[0-9]+|UPTERM_SERVER=wss://uptermd\.upterm\.dev|UPTERM_AUTHORIZED_USER=github:[A-Za-z0-9-]+)$' \
    "$CONFIG_FILE" >/dev/null; then

    echo "ERROR: bot.env contiene líneas no permitidas."
    exit 1
fi

# ==========================================
# PROTEGER CREDENCIALES
# ==========================================

chown root:"$APP_GROUP" "$CONFIG_FILE"
chmod 0640 "$CONFIG_FILE"

# ==========================================
# CONFIGURAR CLAVE DEL RELAY
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
