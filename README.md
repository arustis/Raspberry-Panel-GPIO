# Panel GPIO para Raspberry Pi

Interfaz gráfica en **Python y Tkinter** para probar 22 zonas de entrada, un Botón de Llamado, cinco actuadores y los dispositivos I2C **MCP23017** y **DS3231**.

El panel muestra las entradas en recuadros de colores y permite activar o desactivar cada actuador con un botón. Incluye un acceso directo para abrir la ventana desde el escritorio, sin usar un IDE.

## Funciones

- Monitoreo de las 22 zonas y del Botón de Llamado, con una nueva lectura aproximadamente cada **0,5 segundos** después de finalizar la anterior.
- Botones para pausar, reanudar y realizar una lectura puntual.
- Control independiente de los cinco actuadores y botón **Apagar todos**.
- Escaneo del bus I2C 1 e inicialización del MCP23017 como entradas con pull-up.
- Lectura del DS3231 y ajuste de su fecha y hora a partir del sistema.
- Diagnóstico de errores dentro de la ventana.
- Interfaz adaptable al ancho de pantalla, con desplazamiento vertical.
- Modo de simulación para revisar la interfaz sin hardware.

## Requisitos

La configuración de referencia es una **Raspberry Pi 4 Model B**, con **Debian 11 / Raspberry Pi OS Bullseye**, **Python 3.9** y escritorio gráfico.

| Componente | Uso |
| --- | --- |
| Python 3 y Tkinter | Ventana y controles gráficos |
| `smbus2` | Comunicación I2C |
| `RPi.GPIO==0.7.1` | Entradas y salidas de la Raspberry Pi |
| MCP23017 en `0x20` | 16 de las 22 zonas |
| DS3231 en `0x68` | Reloj de tiempo real |
| Bus I2C 1 habilitado | Acceso mediante `/dev/i2c-1` |
| Permisos GPIO e I2C | Ejecución con el usuario habitual |

La compatibilidad con otros modelos, incluida Raspberry Pi 5, y con otras versiones del sistema requiere validación. El modo real necesita ejecutarse en la Raspberry; el modo de simulación no requiere `smbus2` ni `RPi.GPIO`.

## Instalación

### 1. Preparar el sistema

En una terminal de la Raspberry Pi:

```sh
sudo apt update
sudo apt install python3-tk python3-venv python3-dev build-essential
```

Habilitá I2C desde la configuración de la Raspberry. En sistemas que incluyen esa herramienta:

```sh
sudo raspi-config
```

Buscá **Interface Options → I2C** y habilitalo. Reiniciá si la herramienta lo solicita.

El usuario debe tener acceso a los grupos `gpio` e `i2c`. Para configurar esa pertenencia:

```sh
sudo groupadd -f gpio
sudo groupadd -f i2c
sudo usermod -aG gpio,i2c "$USER"
```

Si se agregaron grupos, cerrá la sesión gráfica y volvé a iniciarla para aplicar el cambio.

### 2. Instalar el panel y el acceso de escritorio

Descargá o cloná este repositorio. Abrí una terminal en la carpeta que contiene `instalar.sh` y ejecutá:

```sh
sh instalar.sh
```

El instalador copia la aplicación a:

```text
~/.local/share/panel-gpios/
```

También crea el acceso **Panel GPIO** en el escritorio. No instala las bibliotecas de Python ni modifica los permisos del hardware; completá el siguiente paso antes de abrirlo por primera vez.

### 3. Preparar las bibliotecas de Python

El lanzador elige el primer intérprete disponible en este orden:

1. `~/.local/share/prueba-gpios/.venv/bin/python`, si existe el entorno del programa de terminal anterior.
2. `~/.local/share/panel-gpios/.venv/bin/python`.
3. `/usr/bin/python3`.

Este bloque prepara las dependencias en el entorno que el lanzador priorizará. Si no existe el entorno anterior, crea uno propio para el panel:

```sh
if [ -x "$HOME/.local/share/prueba-gpios/.venv/bin/python" ]; then
    PANEL_VENV="$HOME/.local/share/prueba-gpios/.venv"
else
    PANEL_VENV="$HOME/.local/share/panel-gpios/.venv"
fi

if [ ! -x "$PANEL_VENV/bin/python" ]; then
    /usr/bin/python3 -m venv --system-site-packages "$PANEL_VENV"
fi

"$PANEL_VENV/bin/python" -m pip install smbus2 "RPi.GPIO==0.7.1"
```

La opción `--system-site-packages` permite aprovechar las bibliotecas del sistema. Tkinter se instala mediante APT; `smbus2` y `RPi.GPIO` se instalan en el entorno virtual.

### 4. Abrir la aplicación

Hacé doble clic en **Panel GPIO**. Si el escritorio solicita confirmación, elegí **Permitir ejecutar**, **Confiar** o **Ejecutar**.

También podés abrirlo con:

```sh
sh "$HOME/.local/share/panel-gpios/abrir-panel.sh"
```

Cerrá previamente cualquier otro programa que configure los mismos GPIO. El lanzador evita abrir dos instancias del panel, pero no bloquea aplicaciones externas ni ejecuciones directas del archivo Python.

## Uso de la interfaz

### Zonas y llamado

Las entradas se configuran con **pull-up** y son **activas en bajo**: conectar una entrada a GND la activa.

| Color | Estado | Lectura |
| --- | --- | --- |
| Verde | ACTIVA | Nivel bajo, `0` |
| Rojo | NORMAL / inactiva | Nivel alto, `1` |
| Gris | SIN LECTURA | Sin dato válido o con error |

Al abrir el panel comienza el monitoreo. **Pausar monitoreo** conserva la última lectura visible y mantiene los actuadores en su estado actual. **Leer una vez** actualiza las entradas y salidas sin cambiar la selección de pausa.

### Actuadores

Los actuadores tienen polaridad confirmada **nivel alto = ON**:

| Color | Estado | Salida |
| --- | --- | --- |
| Verde | ON | Nivel alto, aproximadamente 3,3 V |
| Rojo | OFF | Nivel bajo, aproximadamente 0 V |
| Gris | SIN LECTURA | Salida no disponible o lectura fallida |

Cada botón **Activar / Desactivar** alterna su actuador según el nivel leído en ese GPIO. Los demás actuadores mantienen su estado. **Apagar todos** ordena OFF a las salidas configuradas.

Los estados se conservan al cambiar de pestaña o pausar el monitoreo. Los indicadores describen el nivel GPIO; no confirman movimiento ni funcionamiento mecánico del actuador.

Al iniciar se configuran las salidas disponibles en OFF. **Cerrar** y **Reconectar** también ordenan OFF antes de liberar los pines. Una vez liberados, o al apagar la Raspberry, el nivel depende del circuito externo.

### I2C y reloj

- **Escanear bus I2C 1:** muestra las direcciones que responden. Con ambos módulos conectados y funcionando se esperan `0x20` y `0x68`.
- **Inicializar MCP23017 con pull-up:** configura ambos puertos como entradas con resistencias de pull-up. El panel también intenta esta inicialización al conectarse.
- **Leer fecha y hora del DS3231:** muestra la última lectura del reloj.
- **Ajustar DS3231 con la hora del sistema:** escribe la fecha y hora local de la Raspberry; verificá que el sistema tenga la hora correcta.
- **Reconectar hardware:** cierra y vuelve a abrir los recursos, ordenando OFF a los actuadores.

Las operaciones y sus errores aparecen en **Resultados y diagnóstico**. Las lecturas fallidas se muestran en gris.

## Correspondencia de pines

El programa utiliza **numeración BCM**. La columna «pin físico» identifica la posición del conector de 40 pines y no es el número utilizado por `RPi.GPIO`.

### Zonas conectadas a la Raspberry Pi

Esta tabla incluye el intercambio corregido de las zonas **15 y 22**.

| Zona | Señal | GPIO BCM | Pin físico |
| --- | --- | --- | --- |
| 1 | ID_SD | 0 | 27 |
| 2 | GPIO5 | 5 | 29 |
| 3 | GPIO6 | 6 | 31 |
| 4 | GPIO13 | 13 | 33 |
| 15 | GPIO19 | 19 | 35 |
| 22 | GPIO22 | 22 | 15 |

### Zonas conectadas al MCP23017

Dirección I2C: **`0x20`**. Las referencias GPA/GPB corresponden a los puertos del expansor.

| Zona | Entrada MCP23017 |
| --- | --- |
| 5 | GPB7 |
| 6 | GPB6 |
| 7 | GPB5 |
| 8 | GPB4 |
| 9 | GPB1 |
| 10 | GPB0 |
| 11 | GPB2 |
| 12 | GPB3 |
| 13 | GPA7 |
| 14 | GPA6 |
| 16 | GPA5 |
| 17 | GPA4 |
| 18 | GPA3 |
| 19 | GPA2 |
| 20 | GPA1 |
| 21 | GPA0 |

### Botón de Llamado

| Entrada | GPIO BCM | Pin físico |
| --- | --- | --- |
| Botón de Llamado | 17 | 11 |

### Actuadores

| Actuador | GPIO BCM | Pin físico |
| --- | --- | --- |
| 1 | 16 | 36 |
| 2 | 18 | 12 |
| 3 | 12 | 32 |
| 4 | 26 | 37 |
| 5 | 15 | 10 |

**ID_SD / GPIO0** debe estar libre de la función de identificación de HAT y **GPIO15** debe estar libre de UART para usar estas asignaciones. Las entradas y salidas de la Raspberry trabajan a 3,3 V; los actuadores requieren una etapa de potencia adecuada para su carga.

## Simulación sin hardware

Desde la carpeta del proyecto, con Python y Tkinter disponibles:

```sh
python3 panel_gpios.py --demo
```

La ventana muestra una franja **SIMULACIÓN**. Hacer clic sobre una zona o sobre el Botón de Llamado alterna su estado simulado. Los botones de actuadores y las pruebas del reloj utilizan datos simulados; no se accede al hardware real.

También se puede iniciar este modo después de instalar:

```sh
sh "$HOME/.local/share/panel-gpios/abrir-panel.sh" --demo
```

El acceso del escritorio inicia el **modo real**.

## Solución de problemas

### `No module named 'smbus2'`

Falta la biblioteca en el intérprete que ejecuta el panel. Repetí el paso **Preparar las bibliotecas de Python** y abrí la aplicación mediante el lanzador. Una instalación en el Python del IDE puede no estar disponible para el acceso de escritorio.

### El entorno virtual «no existe»

No todas las instalaciones tienen la carpeta `prueba-gpios/.venv`. El bloque de instalación anterior contempla ese caso y crea el entorno dentro de `panel-gpios/.venv`.

### No se puede abrir `/dev/i2c-1`

Primero revisá el diagnóstico: un error de importación de `smbus2` también impide abrir el bus. Si la biblioteca está disponible, comprobá que I2C esté habilitado y revisá el dispositivo y los grupos:

```sh
ls -l /dev/i2c-1
id
```

El usuario debe tener permiso de lectura y escritura sobre el dispositivo. Si `/dev/i2c-1` no existe, revisá la configuración I2C del sistema. Después de corregir la causa, usá **Reconectar hardware**.

### `No access to /dev/mem` o permisos GPIO insuficientes

Comprobá:

```sh
ls -l /dev/gpiomem
id
```

En la configuración utilizada, `/dev/gpiomem` debe pertenecer a `root:gpio`, tener permisos `0660` (`crw-rw----`) y el usuario debe pertenecer al grupo `gpio`.

Si el dispositivo existe pero solo permite acceso a `root`, esta regla aplica los permisos del grupo de forma persistente:

```sh
printf '%s\n' 'KERNEL=="gpiomem", GROUP="gpio", MODE="0660"' | sudo tee /etc/udev/rules.d/99-gpiomem-permissions.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --action=change --sysname-match=gpiomem
sudo udevadm settle
ls -l /dev/gpiomem
```

La regla requiere que el grupo `gpio` exista. Si `/dev/gpiomem` no existe, hay que revisar el soporte del sistema para el dispositivo. No se soluciona creando un archivo con ese nombre ni cambiando los permisos de `/dev/mem`.

### `Not running on a RPi!`

Revisá que el programa esté en la Raspberry y que el intérprete seleccionado tenga `RPi.GPIO==0.7.1`. Esa versión se utilizó para resolver el reconocimiento de la Raspberry Pi 4 de referencia.

### `Failed to add edge detection`

Esta versión utiliza **lectura por sondeo**, sin interrupciones de flanco ni `gpiozero.Button`. Si aparece ese error, verificá que se esté ejecutando la versión actual del panel y no un programa anterior.

### La ventana no abre o falta Tkinter

Instalá el componente del sistema:

```sh
sudo apt install python3-tk
```

El registro del lanzador está en:

```text
~/.local/state/panel-gpios/panel.log
```

Si configuraste `XDG_STATE_HOME`, el registro se encuentra en `$XDG_STATE_HOME/panel-gpios/panel.log`.

Podés consultar las últimas líneas con:

```sh
tail -n 60 "$HOME/.local/state/panel-gpios/panel.log"
```

## Archivos del proyecto

| Archivo | Función |
| --- | --- |
| `panel_gpios.py` | Ventana, tarjetas de estado, botones y tareas de lectura |
| `gpio_hardware.py` | Asignaciones, acceso a GPIO/I2C, reloj y simulación |
| `abrir-panel.sh` | Selección de Python, bloqueo de instancias y registro de errores |
| `instalar.sh` | Copia de archivos y creación del acceso de escritorio |
| `panel-gpios.svg` | Icono del acceso directo |
| `LEEME.txt` | Instrucciones resumidas de la versión inicial |
| `README.md` | Instalación y documentación completa del repositorio |

## Actualización y validación

Para actualizar, cerrá el panel, descargá la versión nueva y ejecutá nuevamente `sh instalar.sh` desde su carpeta. Se conserva el entorno virtual. Las asignaciones de pines se encuentran en `RASPBERRY_ZONE_PINS`, `MCP23017_INPUT_BITS` y `ACTUATOR_PINS` dentro de `gpio_hardware.py`.

Durante el desarrollo se verificaron la interfaz en una pantalla virtual, la sintaxis compatible con Python 3.9 y la lógica mediante hardware simulado: colores, asignaciones, alternancia, errores de lectura y cierre. Estas pruebas no sustituyen la validación eléctrica ni la prueba de los módulos y actuadores conectados a la Raspberry Pi.
