
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
    echo "Grupo creado: $APP_GROUP"
else
    echo "Grupo existente: $APP_GROUP"
fi

# ==========================================
# CREAR USUARIO DE SERVICIO
# ==========================================

if ! id "$APP_USER" >/dev/null 2>&1; then
    useradd \
        --system \
        --gid "$APP_GROUP" \
        --home-dir "$STATE_DIR" \
        --no-create-home \
        --shell /usr/sbin/nologin \
        "$APP_USER"

    echo "Usuario creado: $APP_USER"
else
    echo "Usuario existente: $APP_USER"
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

if [[ -f "$CONFIG_FILE" ]]; then
    echo
    echo "Ya existe una configuración."
    echo "No se sobrescribirán las credenciales."
else
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

    # Validar datos
    if [[ -z "$BOT_TOKEN" ]]; then
        echo "ERROR: el token no puede estar vacío."
        exit 1
    fi

    if [[ ! "$TELEGRAM_ID" =~ ^[0-9]+$ ]]; then
        echo "ERROR: el Telegram User ID debe ser numérico."
        exit 1
    fi

    if [[ ! "$GITHUB_USER" =~ ^[A-Za-z0-9-]+$ ]]; then
        echo "ERROR: nombre de GitHub no válido."
        exit 1
    fi

    # Crear archivo privado
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

    echo
    echo "Credenciales guardadas correctamente."
fi

# ==========================================
# VERIFICAR PERMISOS
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
echo "Grupo: $APP_GROUP"
echo "Configuración: $CONFIG_FILE"
echo "Estado: $STATE_DIR"

echo
echo "Permisos del archivo:"
stat -c "%A %U:%G %n" "$CONFIG_FILE" 2>/dev/null || true
