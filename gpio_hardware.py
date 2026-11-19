"""Acceso al hardware y simulación explícita para el panel gráfico."""

from __future__ import annotations

from datetime import datetime

I2C_BUS = 1

DS3231_ADDRESS = 0x68

MCP23017_ADDRESS = 0x20

CALL_BUTTON_GPIO = 17

RASPBERRY_ZONE_PINS = {
    1: (0, 27, "ID_SD"),
    2: (5, 29, "GPIO5"),
    3: (6, 31, "GPIO6"),
    4: (13, 33, "GPIO13"),
    15: (19, 35, "GPIO19"),
    22: (22, 15, "GPIO22"),
}

ACTUATOR_PINS = {
    1: (16, 36),
    2: (18, 12),
    3: (12, 32),
    4: (26, 37),
    5: (15, 10),
}

IODIRA = 0x00

IODIRB = 0x01

IOCON = 0x0A

GPPUA = 0x0C

GPPUB = 0x0D

GPIOA = 0x12

GPIOB = 0x13

MCP23017_INPUT_BITS = {
    "ZONA_5": ("B", 7),
    "ZONA_6": ("B", 6),
    "ZONA_7": ("B", 5),
    "ZONA_8": ("B", 4),
    "ZONA_9": ("B", 1),
    "ZONA_10": ("B", 0),
    "ZONA_11": ("B", 2),
    "ZONA_12": ("B", 3),
    "ZONA_13": ("A", 7),
    "ZONA_14": ("A", 6),
    "ZONA_16": ("A", 5),
    "ZONA_17": ("A", 4),
    "ZONA_18": ("A", 3),
    "ZONA_19": ("A", 2),
    "ZONA_20": ("A", 1),
    "ZONA_21": ("A", 0),
}

def bcd_to_decimal(value: int) -> int:
    """Convierte un byte BCD empaquetado a decimal."""
    return ((value >> 4) * 10) + (value & 0x0F)

def decimal_to_bcd(value: int) -> int:
    """Convierte un entero decimal a BCD empaquetado."""
    return ((value // 10) << 4) | (value % 10)

def format_raw_registers(registers: list[int]) -> str:
    """Devuelve los registros del RTC en hexadecimal para diagnóstico."""
    return " ".join(f"0x{value:02X}" for value in registers)

def validate_bcd(value: int, field: str) -> None:
    """Rechaza nibbles que no representan dígitos BCD válidos."""
    if (value & 0x0F) > 9 or ((value >> 4) & 0x0F) > 9:
        raise ValueError(f"BCD inválido en {field}")

def device_responds(bus: SMBus, address: int) -> bool:
    """Comprueba una dirección mediante una lectura, sin escribir registros."""
    try:
        bus.read_byte(address)
        return True
    except OSError:
        return False

def require_device(bus: SMBus, address: int, name: str) -> None:
    if not device_responds(bus, address):
        raise RuntimeError(
            f"No se encontró {name} en 0x{address:02X} sobre el bus I2C {I2C_BUS}."
        )

def read_ds3231_datetime(bus: SMBus) -> datetime:
    """Lee y valida 0x00..0x06 del RTC configurado en formato 24 horas."""
    require_device(bus, DS3231_ADDRESS, "el RTC DS3231")
    data = bus.read_i2c_block_data(DS3231_ADDRESS, 0x00, 7)
    raw_registers = format_raw_registers(data)
    if len(data) != 7:
        raise ValueError(
            f"El DS3231 devolvió {len(data)} registros; se esperaban 7. "
            f"Registros DS3231 crudos: {raw_registers}"
        )

    try:
        # Se enmascaran los bits que no forman parte del valor BCD antes de
        # convertir. En particular, data[5].bit7 es el bit de siglo, no el mes.
        bcd_values = {
            "segundos": data[0] & 0x7F,
            "minutos": data[1] & 0x7F,
            "horas": data[2] & 0x3F,
            "día de semana": data[3] & 0x07,
            "día": data[4] & 0x3F,
            "mes": data[5] & 0x1F,
            "año": data[6],
        }
        for field, value in bcd_values.items():
            validate_bcd(value, field)

        second = bcd_to_decimal(data[0] & 0x7F)
        minute = bcd_to_decimal(data[1] & 0x7F)
        hour = bcd_to_decimal(data[2] & 0x3F)
        day_of_week = bcd_to_decimal(data[3] & 0x07)
        day = bcd_to_decimal(data[4] & 0x3F)
        month = bcd_to_decimal(data[5] & 0x1F)
        year = bcd_to_decimal(data[6]) + 2000

        ranges = {
            "segundos": (second, 0, 59),
            "minutos": (minute, 0, 59),
            "horas": (hour, 0, 23),
            "día de semana": (day_of_week, 1, 7),
            "día": (day, 1, 31),
            "mes": (month, 1, 12),
        }
        invalid = [
            f"{field}={value} (rango {minimum}..{maximum})"
            for field, (value, minimum, maximum) in ranges.items()
            if not minimum <= value <= maximum
        ]
        if invalid:
            raise ValueError(f"valores fuera de rango: {', '.join(invalid)}")

        return datetime(year, month, day, hour, minute, second)
    except ValueError as error:
        raise ValueError(
            f"Fecha/hora inválida ({error}). "
            f"Registros DS3231 crudos: {raw_registers}"
        ) from error

def set_ds3231_from_system(bus: SMBus) -> datetime:
    """Escribe la hora local actual del sistema en formato 24 horas."""
    require_device(bus, DS3231_ADDRESS, "el RTC DS3231")
    now = datetime.now().replace(microsecond=0)
    if not 2000 <= now.year <= 2099:
        raise ValueError(
            "La escritura sin bit de siglo admite años entre 2000 y 2099."
        )

    values = [
        decimal_to_bcd(now.second),
        decimal_to_bcd(now.minute),
        decimal_to_bcd(now.hour),  # bit 6=0: formato de 24 horas
        decimal_to_bcd(now.isoweekday()),
        decimal_to_bcd(now.day),
        decimal_to_bcd(now.month),  # bit de siglo=0
        decimal_to_bcd(now.year - 2000),
    ]
    bus.write_i2c_block_data(DS3231_ADDRESS, 0x00, values)
    return now

def initialize_mcp23017(bus: SMBus) -> None:
    """Fuerza BANK=0 y configura ambos puertos como entradas con pull-up."""
    require_device(bus, MCP23017_ADDRESS, "el MCP23017")
    bus.write_byte_data(MCP23017_ADDRESS, IOCON, 0x00)
    bus.write_byte_data(MCP23017_ADDRESS, IODIRA, 0xFF)
    bus.write_byte_data(MCP23017_ADDRESS, IODIRB, 0xFF)
    bus.write_byte_data(MCP23017_ADDRESS, GPPUA, 0xFF)
    bus.write_byte_data(MCP23017_ADDRESS, GPPUB, 0xFF)
    print("MCP23017 inicializado: GPA/GPB son entradas y sus pull-ups están activos.")

def read_zones(bus: SMBus) -> tuple[int, int]:
    require_device(bus, MCP23017_ADDRESS, "el MCP23017")
    return (
        bus.read_byte_data(MCP23017_ADDRESS, GPIOA),
        bus.read_byte_data(MCP23017_ADDRESS, GPIOB),
    )

def get_raspberry_gpio():
    try:
        import RPi.GPIO as GPIO
    except ImportError as error:
        raise RuntimeError(
            "Instale RPi.GPIO en el mismo Python que ejecuta este programa."
        ) from error
    return GPIO

class HardwareBackend:
    """Todas las llamadas se realizan desde un único hilo de trabajo."""

    def __init__(self):
        self.gpio = None
        self.bus = None
        self.inputs = set()
        self.outputs = set()
        self.errors = {}
        self.mcp_ready = False

    def connect(self):
        try:
            self.gpio = get_raspberry_gpio()
            self.gpio.setmode(self.gpio.BCM)
        except Exception as error:
            self.errors['GPIO'] = str(error)
            self.gpio = None
        if self.gpio is not None:
            pins = [pin for pin, _, _ in RASPBERRY_ZONE_PINS.values()] + [CALL_BUTTON_GPIO]
            for pin in pins:
                try:
                    self.gpio.setup(pin, self.gpio.IN, pull_up_down=self.gpio.PUD_UP)
                    self.inputs.add(pin)
                except Exception as error:
                    self.errors[f'GPIO{pin}'] = str(error)
            for pin, _ in ACTUATOR_PINS.values():
                try:
                    self.gpio.setup(pin, self.gpio.OUT, initial=self.gpio.LOW)
                    self.outputs.add(pin)
                except Exception as error:
                    self.errors[f'GPIO{pin}'] = str(error)
        try:
            from smbus2 import SMBus
            self.bus = SMBus(I2C_BUS)
        except Exception as error:
            self.errors['I2C'] = str(error)
        if self.bus is not None:
            try:
                self.initialize_mcp()
            except Exception as error:
                self.errors['MCP23017'] = str(error)
        return self.snapshot()

    def _read_pin(self, pin, output=False):
        if pin not in (self.outputs if output else self.inputs):
            return None
        try:
            value = int(self.gpio.input(pin))
            self.errors.pop(f'GPIO{pin}', None)
            return value
        except Exception as error:
            self.errors[f'GPIO{pin}'] = str(error)
            return None

    def snapshot(self):
        zones = {number: None for number in range(1, 23)}
        for number, (pin, _, _) in RASPBERRY_ZONE_PINS.items():
            zones[number] = self._read_pin(pin)
        if self.bus is not None and self.mcp_ready:
            try:
                port_a, port_b = read_zones(self.bus)
                for name, (port, bit) in MCP23017_INPUT_BITS.items():
                    zones[int(name.split('_')[1])] = ((port_a if port == 'A' else port_b) >> bit) & 1
                self.errors.pop('MCP23017', None)
            except Exception as error:
                self.errors['MCP23017'] = str(error)
        return {
            'zones': zones,
            'button': self._read_pin(CALL_BUTTON_GPIO),
            'actuators': {number: self._read_pin(pin, output=True) for number, (pin, _) in ACTUATOR_PINS.items()},
            'errors': dict(self.errors),
            'time': datetime.now().strftime('%H:%M:%S'),
        }

    def _require_bus(self):
        if self.bus is None:
            raise RuntimeError('No se pudo abrir /dev/i2c-1. Revise I2C y los permisos; luego use Reconectar.')
        return self.bus

    def scan(self):
        bus = self._require_bus()
        return [address for address in range(0x03, 0x78) if device_responds(bus, address)]

    def initialize_mcp(self):
        self.mcp_ready = False
        initialize_mcp23017(self._require_bus())
        self.mcp_ready = True
        self.errors.pop('MCP23017', None)
        return self.snapshot()

    def read_rtc(self):
        return read_ds3231_datetime(self._require_bus())

    def set_rtc(self):
        return set_ds3231_from_system(self._require_bus())

    def toggle(self, number):
        if number not in ACTUATOR_PINS:
            raise ValueError('Actuador inválido.')
        pin, _ = ACTUATOR_PINS[number]
        if pin not in self.outputs:
            raise RuntimeError(f'GPIO{pin} no está disponible. Revise el error y use Reconectar.')
        current = self._read_pin(pin, output=True)
        if current is None:
            raise RuntimeError(f'No se pudo leer GPIO{pin}; no se cambió su salida.')
        self.gpio.output(pin, self.gpio.LOW if current else self.gpio.HIGH)
        return self.snapshot()

    def all_off(self):
        failures = []
        for pin in sorted(self.outputs):
            try:
                self.gpio.output(pin, self.gpio.LOW)
            except Exception as error:
                failures.append(f'GPIO{pin}: {error}')
        if failures:
            raise RuntimeError('No se pudo ordenar OFF: ' + '; '.join(failures))
        return self.snapshot()

    def close(self):
        failures = []
        try:
            self.all_off()
        except Exception as error:
            failures.append(str(error))
        pins = sorted(self.inputs | self.outputs)
        if self.gpio is not None and pins:
            try:
                self.gpio.cleanup(pins)
            except Exception as error:
                failures.append(f'No se pudieron liberar GPIO: {error}')
        self.inputs.clear()
        self.outputs.clear()
        if self.bus is not None:
            try:
                self.bus.close()
            except Exception as error:
                failures.append(f'No se pudo cerrar I2C: {error}')
            self.bus = None
        self.mcp_ready = False
        return failures

    def reconnect(self):
        failures = self.close()
        if failures:
            raise RuntimeError('; '.join(failures))
        self.errors.clear()
        return self.connect()


class DemoBackend:
    """Simulación visible; nunca importa ni configura hardware real."""

    def __init__(self):
        self.zones = {number: 1 for number in range(1, 23)}
        self.button = 1
        self.actuators = {number: 0 for number in ACTUATOR_PINS}
        self.rtc = None

    def connect(self):
        return self.snapshot()

    def snapshot(self):
        return {'zones': dict(self.zones), 'button': self.button,
                'actuators': dict(self.actuators), 'errors': {},
                'time': datetime.now().strftime('%H:%M:%S')}

    def scan(self):
        return [MCP23017_ADDRESS, DS3231_ADDRESS]

    def initialize_mcp(self):
        return self.snapshot()

    def read_rtc(self):
        return self.rtc or datetime.now().replace(microsecond=0)

    def set_rtc(self):
        self.rtc = datetime.now().replace(microsecond=0)
        return self.rtc

    def toggle(self, number):
        self.actuators[number] = 1 - self.actuators[number]
        return self.snapshot()

    def simulate_input(self, number=None):
        if number is None:
            self.button = 1 - self.button
        else:
            self.zones[number] = 1 - self.zones[number]
        return self.snapshot()

    def all_off(self):
        self.actuators = {number: 0 for number in ACTUATOR_PINS}
        return self.snapshot()

    def close(self):
        self.all_off()
        return []

    def reconnect(self):
        self.close()
        return self.connect()
