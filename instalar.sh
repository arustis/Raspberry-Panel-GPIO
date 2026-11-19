#!/bin/sh
set -eu
SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
/usr/bin/python3 - "$SOURCE_DIR" <<'PY'
from pathlib import Path
import shutil
import subprocess
import sys

source = Path(sys.argv[1])
app = Path.home() / '.local' / 'share' / 'panel-gpios'
app.mkdir(parents=True, exist_ok=True)
for name in ('panel_gpios.py', 'gpio_hardware.py', 'abrir-panel.sh', 'panel-gpios.svg', 'LEEME.txt'):
    destination = app / name
    if (source / name).resolve() != destination.resolve():
        shutil.copyfile(source / name, destination)
    destination.chmod(0o755 if name.endswith('.sh') else 0o644)

desktop = None
if shutil.which('xdg-user-dir'):
    result = subprocess.run(['xdg-user-dir', 'DESKTOP'], capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.strip():
        candidate = Path(result.stdout.strip())
        if candidate.is_absolute() and candidate != Path.home():
            desktop = candidate
if desktop is None:
    desktop = Path.home() / ('Escritorio' if (Path.home() / 'Escritorio').is_dir() else 'Desktop')
desktop.mkdir(parents=True, exist_ok=True)

def exec_quote(value):
    value = str(value).replace('%', '%%')
    for character in ('\\', '"', '`', '$'):
        value = value.replace(character, '\\' + character)
    return '"' + value + '"'

def entry_value(value):
    return str(value).replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r')

entry = desktop / 'panel-gpios.desktop'
contents = (
    '[Desktop Entry]\n'
    'Version=1.0\n'
    'Type=Application\n'
    'Name=Panel GPIO\n'
    'Comment=Zonas, Botón de Llamado, actuadores e I2C\n'
    f'Exec={exec_quote(app / "abrir-panel.sh")}\n'
    f'Icon={entry_value(app / "panel-gpios.svg")}\n'
    'Terminal=false\n'
    'Categories=Utility;\n'
    'StartupNotify=false\n'
)
if entry.exists() and entry.read_text() != contents:
    raise SystemExit(f'Ya existe un acceso distinto en {entry}. Renómbrelo antes de instalar.')
entry.write_text(contents)
entry.chmod(0o755)
if shutil.which('gio'):
    subprocess.run(['gio', 'set', str(entry), 'metadata::trusted', 'true'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(f'Acceso directo creado: {entry}')
print('Abra Panel GPIO desde el escritorio. Si lo pide, elija Permitir ejecutar / Confiar.')
print('Se reutiliza el entorno virtual de prueba-gpios y sus permisos existentes.')
print('El programa de terminal y su acceso directo se conservan.')
PY
