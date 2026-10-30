# Raspberry Telebot Installer

Instalador automatizado de un sistema de administración remota para Raspberry Pi mediante Telegram y Upterm.

## Objetivo

Preparar una Raspberry Pi nueva desde cero mediante un instalador que configure las dependencias, el entorno Python, las credenciales y los servicios necesarios.

El sistema permite administrar Linux remotamente desde Telegram y disponer de una terminal interactiva mediante Upterm.

## Características

- Instalación automatizada de dependencias.
- Instalación de Upterm CLI con verificación SHA256.
- Entorno virtual independiente de Python.
- Bot de Telegram basado en `python-telegram-bot`.
- Ejecución de comandos Linux mediante Bash.
- Cambio de directorios desde Telegram.
- Visualización de resultados de comandos.
- Autenticación mediante Telegram User ID.
- Acceso interactivo mediante Upterm y WebSocket seguro.
- Autorización de Upterm mediante claves públicas de GitHub.
- Transferencia SFTP/SCP desactivada.
- Servicios systemd con inicio automático.
- Credenciales y configuración fuera del repositorio.
- Separación entre archivos del proyecto, configuración y datos del servicio.

## Compatibilidad

- Raspberry Pi con arquitectura ARM64.
- Ubuntu 24.04 LTS.
- Debian y Raspberry Pi OS compatibles con `apt`, `dpkg` y systemd.
- Python 3 compatible con `python-telegram-bot` 22.x.
- Arquitectura AMD64 también admitida por el instalador.

## Requisitos previos

Antes de instalar:

- Acceso a una Raspberry Pi con permisos administrativos.
- Conexión a Internet.
- Acceso al repositorio privado de GitHub.
- Un bot creado mediante BotFather.
- El Telegram User ID autorizado.
- Una cuenta GitHub con la clave SSH pública que utilizarás para conectarte mediante Upterm.

## Instalación

Clonar el repositorio:

```bash
git clone https://github.com/KaworuSSSS/raspberry-telebot-installer.git
```

Entrar en el directorio:

```bash
cd raspberry-telebot-installer
```

Ejecutar el instalador:

```bash
sudo bash install.sh
```

Durante la instalación se solicitarán:

- Token del bot de Telegram.
- Telegram User ID autorizado.
- Nombre de usuario GitHub autorizado para Upterm.

El instalador configura las credenciales en:

```text
/etc/raspberry-telebot-installer/bot.env
```

Las credenciales no deben guardarse en GitHub ni compartirse públicamente.

## Arquitectura

### Administración mediante Telegram

```text
TELEGRAM
   |
   v
TELEGRAM BOT API
   |
   v
PYTHON BOT
   |
   v
BASH SHELL
   |
   v
RASPBERRY PI
```

### Terminal interactiva mediante Upterm

```text
CODESPACES / SSH CLIENT
          |
          v
         UPT​ERM
          |
          v
   WEBSOCKET SEGURO
          |
          v
   UPT​ERM RELAY
          |
          v
      RASPBERRY PI
```

Telegram y Upterm funcionan como dos vías independientes de acceso remoto.

## Servicios

El instalador configura dos servicios systemd:

| Servicio | Función |
|---|---|
| `telegram-bot.service` | Bot de administración por Telegram |
| `upterm.service` | Terminal interactiva remota |

Ambos servicios se habilitan para iniciar automáticamente al arrancar la Raspberry Pi.

## Seguridad

- Token de Telegram almacenado fuera del repositorio.
- Acceso al bot restringido por Telegram User ID y chat privado.
- Credenciales protegidas mediante permisos de archivo.
- Usuario de sistema dedicado para ejecutar los servicios.
- Acceso a Upterm restringido mediante claves públicas GitHub.
- Verificación de la identidad del relay mediante `known_hosts`.
- Conexión al relay mediante WSS.
- SFTP/SCP desactivado.
- Servicios systemd con medidas de aislamiento.

### Permisos de ejecución

Los comandos enviados mediante Telegram se ejecutan con Bash utilizando el usuario de sistema `raspberry-telebot`.

Este usuario no dispone de privilegios administrativos por defecto. Por tanto, los comandos que requieren `root` o `sudo` no podrán ejecutarse automáticamente.

La terminal permite ejecutar comandos Linux arbitrarios, sin una lista fija de comandos permitidos. Esto implica que el usuario autorizado debe proteger sus credenciales y el acceso a su cuenta de Telegram y GitHub.

## Directorios principales

| Ruta | Función |
|---|---|
| `/opt/raspberry-telebot-installer` | Archivos del proyecto |
| `/etc/raspberry-telebot-installer` | Configuración y credenciales |
| `/var/lib/raspberry-telebot` | Estado y datos del servicio |
| `/usr/local/bin/upterm` | Ejecutable Upterm |

## Estructura del repositorio

```text
raspberry-telebot-installer/
├── README.md
├── install.sh
├── requirements.txt
├── bot/
│   ├── bot.py
│   ├── terminal.py
│   └── upterm.py
├── systemd/
│   ├── telegram-bot.service
│   └── upterm.service
├── config/
│   └── bot.env.example
└── scripts/
    ├── install_dependencies.sh
    └── configure_security.sh
```

## Comprobación de servicios

Consultar el estado del bot:

```bash
sudo systemctl status telegram-bot.service
```

Consultar el estado de Upterm:

```bash
sudo systemctl status upterm.service
```

Consultar los registros del bot:

```bash
sudo journalctl -u telegram-bot.service -f
```

Consultar los registros de Upterm:

```bash
sudo journalctl -u upterm.service -f
```

## Actualización

Para actualizar el proyecto:

1. Entrar en el repositorio instalado.
2. Obtener los últimos cambios de la rama principal.
3. Ejecutar nuevamente el instalador.

El instalador conserva la configuración existente cuando el archivo de credenciales ya está creado.

## Proyecto

Desarrollado para facilitar la instalación, configuración y administración remota de Raspberry Pi desde cualquier lugar.
