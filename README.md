# Raspberry Telebot Installer

Instalador automatizado de un sistema de administración remota para Raspberry Pi mediante Telegram y Upterm.

## Objetivo

Preparar una Raspberry Pi nueva mediante un instalador que configure las dependencias, el entorno Python, las credenciales y el servicio necesario.

El sistema permite administrar Linux remotamente desde Telegram y abrir una terminal interactiva mediante Upterm.

## Características

- Instalación automatizada de dependencias.
- Instalación de Upterm CLI con verificación SHA256.
- Compatibilidad con arquitecturas ARM64 y AMD64.
- Entorno virtual independiente de Python.
- Bot de Telegram basado en `python-telegram-bot` 22.x.
- Ejecución de comandos Linux mediante Bash.
- Cambio persistente de directorios desde Telegram.
- Visualización de resultados de comandos.
- Autenticación mediante Telegram User ID y chat privado.
- Terminal interactiva mediante Upterm.
- Conexión al relay mediante WebSocket seguro (WSS).
- Conexión al relay mediante el puerto 443.
- Transferencia SFTP/SCP desactivada.
- Un único servicio systemd para el bot.
- Inicio automático del bot al arrancar la Raspberry Pi.
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

- Raspberry Pi con permisos administrativos.
- Conexión a Internet.
- Git instalado o disponible para instalar mediante el sistema de paquetes.
- Un bot de Telegram creado mediante BotFather.
- El Telegram User ID que tendrá autorización para utilizar el bot.

Se requiere acceso al repositorio de GitHub si este es privado.

## Instalación

Clonar el repositorio:

```bash
git clone https://github.com/OliverAmadeus/raspberry-telebot-installer.git
```

Entrar en el directorio:

```bash
cd raspberry-telebot-installer
```

Ejecutar el instalador:

```bash
sudo bash install.sh
```

Durante la primera instalación se solicitarán:

- Token del bot de Telegram.
- Telegram User ID autorizado.

El instalador configura las credenciales en:

```text
/etc/raspberry-telebot-installer/bot.env
```

La configuración de confianza SSH utilizada por Upterm se almacena en:

```text
/var/lib/raspberry-telebot/.ssh/known_hosts
```

**Importante:** las credenciales y los archivos de confianza no deben guardarse en GitHub ni compartirse públicamente.

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
         UPT​​ERM
          |
          v
   WEBSOCKET SEGURO
          |
          v
     UPT​​ERM RELAY
          |
          v
      RASPBERRY PI
```

Telegram y Upterm funcionan como dos vías de acceso remoto. Upterm es iniciado y administrado por el propio bot de Telegram.

## Servicios y arranque automático

El instalador configura un único servicio systemd:

| Servicio | Función |
|---|---|
| `telegram-bot.service` | Bot de administración por Telegram e inicio de sesiones Upterm |

El servicio se habilita para arrancar automáticamente cuando se enciende la Raspberry Pi.

Upterm no se ejecuta mediante un servicio systemd independiente. El bot administra su inicio, consulta de estado y detención.

### Inicio de Upterm

Desde Telegram se utilizan los comandos:

```text
/upterm iniciar
/upterm estado
/upterm detener
```

Cuando se apaga o reinicia la Raspberry Pi, la sesión interactiva de Upterm termina. Después de que el bot vuelva a arrancar, se puede iniciar una sesión nueva mediante:

```text
/upterm iniciar
```

El inicio automático del bot no significa que una sesión Upterm anterior se recupere automáticamente.

## Seguridad

- Token de Telegram almacenado fuera del repositorio.
- Acceso al bot restringido por Telegram User ID y chat privado.
- Credenciales protegidas mediante permisos de archivo.
- Usuario de sistema dedicado: `raspberry-telebot`.
- Bot y terminal Upterm ejecutados sin privilegios administrativos.
- Conexión al relay mediante WSS por el puerto 443.
- Transferencia SFTP/SCP desactivada.
- Archivos de configuración separados del código del proyecto.
- Servicio systemd con medidas de aislamiento.

### Permisos de ejecución

Los comandos enviados mediante Telegram se ejecutan con Bash utilizando el usuario de sistema `raspberry-telebot`.

La terminal interactiva de Upterm también utiliza ese usuario.

Este usuario no dispone de privilegios administrativos por defecto. Por tanto, los comandos que requieren `root` o `sudo` no podrán ejecutarse automáticamente.

La terminal interactiva permite ejecutar comandos Linux arbitrarios dentro de los permisos de ese usuario. Por ello, el secreto de conexión de Upterm debe mantenerse privado: cualquier persona que lo obtenga podría acceder a la sesión mientras permanezca activa.

## Directorios principales

| Ruta | Función |
|---|---|
| `/opt/raspberry-telebot-installer` | Archivos del proyecto |
| `/etc/raspberry-telebot-installer` | Configuración y credenciales |
| `/etc/raspberry-telebot-installer/bot.env` | Variables de entorno del bot |
| `/var/lib/raspberry-telebot` | Estado y datos del servicio |
| `/var/lib/raspberry-telebot/.ssh/known_hosts` | Claves de confianza del relay |
| `/usr/local/bin/upterm` | Ejecutable Upterm |

## Estructura del repositorio

```text
raspberry-telebot-installer/
├── README.md
├── install.sh
├── requirements.txt
├── .gitignore
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

El archivo `systemd/upterm.service` se conserva como referencia histórica, pero no se instala ni se habilita. El instalador utiliza únicamente `telegram-bot.service`.

Los archivos de configuración y confianza se generan durante la instalación y no forman parte del repositorio.

## Comprobación del servicio

Consultar el estado del bot:

```bash
sudo systemctl status telegram-bot.service
```

Consultar los registros del bot:

```bash
sudo journalctl -u telegram-bot.service -f
```

Consultar los últimos registros:

```bash
sudo journalctl -u telegram-bot.service -n 100
```

El estado de Upterm se consulta desde Telegram:

```text
/upterm estado
```

## Actualización

Para actualizar el proyecto:

1. Entrar en el directorio donde se clonó el repositorio.
2. Obtener los últimos cambios de la rama principal.
3. Ejecutar nuevamente el instalador.

Ejemplo:

```bash
cd raspberry-telebot-installer
git pull origin main
sudo bash install.sh
```

El instalador actualiza los archivos del proyecto y configura el servicio del bot.

Si el archivo de credenciales ya existe, el proceso debe conservar el token de Telegram y el Telegram User ID existentes, además de mantener la configuración de Upterm.

No es necesario volver a introducir las credenciales si la configuración existente es válida.

## Proyecto

Desarrollado para facilitar la instalación, configuración y administración remota de Raspberry Pi desde cualquier lugar.
