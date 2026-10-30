# Raspberry Telebot Installer

Instalador automático de un sistema de administración remota para Raspberry Pi mediante Telegram y Upterm.

## Objetivo

Configurar una Raspberry Pi nueva desde cero utilizando un único instalador.

El sistema permitirá administrar Linux remotamente desde Telegram y disponer de una terminal interactiva mediante Upterm.

## Características

- Instalación automática de dependencias.
- Entorno virtual de Python.
- Bot de Telegram basado en `python-telegram-bot`.
- Ejecución de comandos Linux mediante Bash.
- Cambio de directorios desde Telegram.
- Visualización de resultados de comandos.
- Autenticación mediante Telegram User ID.
- Integración con Upterm mediante WebSocket.
- Servicios systemd con inicio automático.
- Configuración y credenciales fuera del repositorio.
- Instalación y actualización reproducibles.

## Compatibilidad

- Raspberry Pi ARM64.
- Ubuntu 24.04 LTS.
- Debian y Raspberry Pi OS compatibles.
- Python 3.

## Instalación

La instalación se realizará mediante:

```bash
git clone https://github.com/KaworuSSSS/raspberry-telebot-installer.git
cd raspberry-telebot-installer
sudo bash install.sh
```

El instalador solicitará las credenciales necesarias y configurará los servicios.

## Arquitectura

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

Acceso interactivo independiente:

```text
CODESPACES / SSH CLIENT
          |
          v
        UPT​ERM
          |
          v
       RASPBERRY PI
```

## Seguridad

- Token de Telegram almacenado fuera del repositorio.
- Autorización mediante Telegram User ID.
- Configuración protegida con permisos restringidos.
- Servicio dedicado para ejecutar el bot.
- Privilegios administrativos configurados explícitamente.

La ejecución de comandos será flexible y no utilizará una lista fija de comandos permitidos. Los comandos tendrán los privilegios del usuario que ejecute el servicio.

## Estructura prevista

```text
raspberry-telebot-installer/
├── README.md
├── install.sh
├── uninstall.sh
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

## Proyecto

Desarrollado para facilitar la instalación y administración remota de Raspberry Pi desde cualquier lugar.
