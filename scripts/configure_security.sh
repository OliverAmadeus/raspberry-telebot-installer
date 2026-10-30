
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

KNOWN_HOSTS="${CONFIG_DIR}/upterm_known_hosts"

TEMP_CONFIG=""
TEMP_KNOWN_HOSTS=""

# Cuentas GitHub autorizadas para Upterm.
GITHUB_USER_1="OliverAmadeus"
GITHUB_USER_2="KaworuSSSS"

UPTERM_KNOWN_HOSTS='
@cert-authority uptermd.upterm.dev ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICiecex8Dq718eSe1CCLgLvDmI7AagvCtax7brPFWkh4
@cert-authority [uptermd.upterm.dev]:443 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICiecex8Dq718eSe1CCLgLvDmI7AagvCtax7brPFWkh4
'

EXPECTED_FINGERPRINT="SHA256:9ajV8JqMe6jJE/s3TYjb/9xw7T0pfJ2+gADiBIJWDPE"

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
# VALIDAR RUTAS
# ==========================================

if [[ -L "$CONFIG_DIR" ]]; then
    echo "ERROR: el directorio de configuración no puede ser un enlace simbólico."
    exit 1
fi

if [[ -L "$STATE_DIR" ]]; then
    echo "ERROR: el directorio de estado no puede ser un enlace simbólico."
    exit 1
fi

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

install -d -o root -g "$APP_GROUP" -m 0750 "$CONFIG_DIR"

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
# OBTENER CREDENCIALES
# ==========================================

BOT_TOKEN=""
TELEGRAM_ID=""

if [[ -f "$CONFIG_FILE" ]]; then

    echo
    echo "Se encontró una configuración existente."
    echo "Se conservarán las credenciales de Telegram."

    if [[ ! -s "$CONFIG_FILE" ]]; then
        echo "ERROR: bot.env está vacío."
        exit 1
    fi

    # Validar token.
    if [[ "$(grep -Ec '^TELEGRAM_BOT_TOKEN=[0-9]+:[A-Za-z0-9_-]+$' "$CONFIG_FILE")" -ne 1 ]]; then
        echo "ERROR: token de Telegram incorrecto o duplicado."
        exit 1
    fi

    # Validar Telegram ID.
    if [[ "$(grep -Ec '^TELEGRAM_AUTHORIZED_USER_ID=[0-9]+$' "$CONFIG_FILE")" -ne 1 ]]; then
        echo "ERROR: Telegram User ID incorrecto o duplicado."
        exit 1
    fi

    # Validar servidor.
    if [[ "$(grep -Ec '^UPTERM_SERVER=wss://uptermd\.upterm\.dev$' "$CONFIG_FILE")" -ne 1 ]]; then
        echo "ERROR: servidor Upterm incorrecto o duplicado."
        exit 1
    fi

    # Debe existir una cuenta autorizada principal.
    if [[ "$(grep -Ec '^UPTERM_AUTHORIZED_USER=github:[A-Za-z0-9-]+$' "$CONFIG_FILE")" -ne 1 ]]; then
        echo "ERROR: cuenta GitHub principal incorrecta o duplicada."
        exit 1
    fi

    # La segunda cuenta es opcional en configuraciones antiguas.
    if [[ "$(grep -Ec '^UPTERM_AUTHORIZED_USER_2=github:[A-Za-z0-9-]+$' "$CONFIG_FILE")" -gt 1 ]]; then
        echo "ERROR: segunda cuenta GitHub duplicada."
        exit 1
    fi

    # Rechazar variables y líneas adicionales.
    if grep -Ev \
        '^(TELEGRAM_BOT_TOKEN=[0-9]+:[A-Za-z0-9_-]+|TELEGRAM_AUTHORIZED_USER_ID=[0-9]+|UPTERM_SERVER=wss://uptermd\.upterm\.dev|UPTERM_AUTHORIZED_USER=github:[A-Za-z0-9-]+|UPTERM_AUTHORIZED_USER_2=github:[A-Za-z0-9-]+)$' \
        "$CONFIG_FILE" >/dev/null; then

        echo "ERROR: bot.env contiene líneas no permitidas."
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
# CREAR CONFIGURACION CANONICA
# ==========================================

echo
echo "Configurando las dos cuentas GitHub autorizadas..."

umask 077

TEMP_CONFIG="$(mktemp "${CONFIG_DIR}/.bot.env.XXXXXX")"

{
    printf 'TELEGRAM_BOT_TOKEN=%s\n' "$BOT_TOKEN"
    printf 'TELEGRAM_AUTHORIZED_USER_ID=%s\n' "$TELEGRAM_ID"
    printf 'UPTERM_SERVER=%s\n' "wss://uptermd.upterm.dev"
    printf 'UPTERM_AUTHORIZED_USER=github:%s\n' "$GITHUB_USER_1"
    printf 'UPTERM_AUTHORIZED_USER_2=github:%s\n' "$GITHUB_USER_2"
} > "$TEMP_CONFIG"

chown root:"$APP_GROUP" "$TEMP_CONFIG"
chmod 0640 "$TEMP_CONFIG"

mv -fT -- "$TEMP_CONFIG" "$CONFIG_FILE"
TEMP_CONFIG=""

# ==========================================
# CONFIGURAR CLAVE DEL RELAY
# ==========================================

echo
echo "Configurando clave de confianza del relay Upterm..."

if [[ -L "$KNOWN_HOSTS" ]]; then
    echo "ERROR: upterm_known_hosts no puede ser un enlace simbólico."
    exit 1
fi

if [[ -e "$KNOWN_HOSTS" && ! -f "$KNOWN_HOSTS" ]]; then
    echo "ERROR: upterm_known_hosts no es un archivo regular."
    exit 1
fi

TEMP_KNOWN_HOSTS="$(mktemp "${CONFIG_DIR}/.upterm_known_hosts.XXXXXX")"

printf '%s\n' "$UPTERM_KNOWN_HOSTS" > "$TEMP_KNOWN_HOSTS"

chown root:"$APP_GROUP" "$TEMP_KNOWN_HOSTS"
chmod 0640 "$TEMP_KNOWN_HOSTS"

mv -fT -- "$TEMP_KNOWN_HOSTS" "$KNOWN_HOSTS"
TEMP_KNOWN_HOSTS=""

# ==========================================
# CONFIGURAR DIRECTORIO SSH
# ==========================================

if [[ -L "$SSH_DIR" ]]; then
    echo "ERROR: el directorio .ssh no puede ser un enlace simbólico."
    exit 1
fi

if [[ -e "$SSH_DIR" && ! -d "$SSH_DIR" ]]; then
    echo "ERROR: .ssh no es un directorio."
    exit 1
fi

install -d \
    -o "$APP_USER" \
    -g "$APP_GROUP" \
    -m 0700 \
    "$SSH_DIR"

# ==========================================
# PERMISOS FINALES
# ==========================================

chown root:"$APP_GROUP" "$CONFIG_DIR"
chmod 0750 "$CONFIG_DIR"

chown root:"$APP_GROUP" "$CONFIG_FILE"
chmod 0640 "$CONFIG_FILE"

chown root:"$APP_GROUP" "$KNOWN_HOSTS"
chmod 0640 "$KNOWN_HOSTS"

chown "$APP_USER":"$APP_GROUP" "$STATE_DIR"
chmod 0750 "$STATE_DIR"

chown "$APP_USER":"$APP_GROUP" "$SSH_DIR"
chmod 0700 "$SSH_DIR"

# ==========================================
# RESULTADO
# ==========================================

echo
echo "=========================================="
echo " SEGURIDAD CONFIGURADA"
echo "=========================================="

echo "Usuario del servicio: $APP_USER"
echo "Grupo: $APP_GROUP"
echo "Configuración: $CONFIG_FILE"
echo "Claves de confianza: $KNOWN_HOSTS"
echo "Directorio SSH: $SSH_DIR"

echo
echo "Cuentas GitHub autorizadas:"
echo " - github:$GITHUB_USER_1"
echo " - github:$GITHUB_USER_2"

echo
echo "Permisos de credenciales:"
stat -c "%A %U:%G %n" "$CONFIG_FILE"

echo
echo "Permisos de known_hosts:"
stat -c "%A %U:%G %n" "$KNOWN_HOSTS"

echo
echo "Huella oficial documentada:"
echo "$EXPECTED_FINGERPRINT"

echo
echo "Configuración de seguridad terminada."
