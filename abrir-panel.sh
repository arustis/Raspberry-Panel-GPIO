#!/bin/sh
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/panel-gpios"
mkdir -p "$STATE_DIR" || exit 1
LOG="$STATE_DIR/panel.log"

# Una sola ventana para no reconfigurar los mismos GPIO desde dos instancias.
exec 9>"$STATE_DIR/panel.lock"
if ! flock -n 9; then
    if command -v zenity >/dev/null 2>&1; then
        zenity --info --text='El Panel GPIO ya está abierto.'
    elif command -v xmessage >/dev/null 2>&1; then
        xmessage -center 'El Panel GPIO ya está abierto.'
    fi
    exit 0
fi

if [ -x "$HOME/.local/share/prueba-gpios/.venv/bin/python" ]; then
    PANEL_PYTHON="$HOME/.local/share/prueba-gpios/.venv/bin/python"
elif [ -x "$APP_DIR/.venv/bin/python" ]; then
    PANEL_PYTHON="$APP_DIR/.venv/bin/python"
else
    PANEL_PYTHON=/usr/bin/python3
fi

"$PANEL_PYTHON" "$APP_DIR/panel_gpios.py" "$@" >>"$LOG" 2>&1
RESULT=$?
if [ "$RESULT" -ne 0 ]; then
    TEXT="No se pudo abrir el Panel GPIO. Revise el registro: $LOG
Si falta tkinter, instale: sudo apt install python3-tk"
    if command -v zenity >/dev/null 2>&1; then
        zenity --error --text="$TEXT"
    elif command -v xmessage >/dev/null 2>&1; then
        xmessage -center "$TEXT"
    elif command -v x-terminal-emulator >/dev/null 2>&1; then
        x-terminal-emulator -e sh -c 'cat "$1"; printf "\nPresione Enter para cerrar... "; read -r respuesta' sh "$LOG"
    fi
fi
exit "$RESULT"
