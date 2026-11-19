#!/usr/bin/env python3
"""Panel gráfico para Raspberry Pi. Ejecutar con --demo para simular."""
from __future__ import annotations

import argparse
import signal
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

from gpio_hardware import (
    HardwareBackend, DemoBackend, RASPBERRY_ZONE_PINS,
    MCP23017_INPUT_BITS, ACTUATOR_PINS,
)

BG = '#f1f4f9'
INK = '#17243b'
GREEN = '#177548'
RED = '#b73542'
GRAY = '#5b6578'


class StateCard(tk.Frame):
    def __init__(self, parent, title, connection, action=None):
        super().__init__(parent, bg=GRAY, padx=12, pady=10)
        self.title_label = tk.Label(self, text=title, font=('Helvetica', 13, 'bold'), anchor='w')
        self.title_label.pack(fill='x')
        self.connection_label = tk.Label(self, text=connection, font=('Helvetica', 9), anchor='w', justify='left')
        self.connection_label.pack(fill='x', pady=(3, 7))
        self.state_label = tk.Label(self, text='SIN LECTURA', font=('Helvetica', 11, 'bold'), anchor='w')
        self.state_label.pack(fill='x')
        self.button = None
        if action is not None:
            self.button = ttk.Button(self, text='Activar', command=action, state='disabled')
            self.button.pack(fill='x', pady=(10, 0))
        self.active = None
        self.set_state(None)

    def set_state(self, active, actuator=False):
        self.active = active
        color = GRAY if active is None else GREEN if active else RED
        state = 'SIN LECTURA' if active is None else ('ON' if active else 'OFF') if actuator else ('ACTIVA' if active else 'NORMAL')
        self.configure(bg=color)
        for label in (self.title_label, self.connection_label, self.state_label):
            label.configure(bg=color, fg='white')
        self.state_label.configure(text=state)
        if self.button is not None:
            self.button.configure(text='Desactivar' if active else 'Activar')

    def demo_binding(self, callback):
        for widget in (self, self.title_label, self.connection_label, self.state_label):
            widget.bind('<Button-1>', lambda event: callback())
            widget.configure(cursor='hand2')


class ScrollPage(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.body = ttk.Frame(self.canvas, padding=14)
        self.window = self.canvas.create_window((0, 0), window=self.body, anchor='nw')
        self.body.bind('<Configure>', lambda event: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda event: self.canvas.itemconfigure(self.window, width=event.width))


class CardGrid(tk.Frame):
    def __init__(self, parent, max_columns=6):
        super().__init__(parent, bg=BG)
        self.cards = []
        self.max_columns = max_columns
        self.columns = 0
        self.bind('<Configure>', self.reflow)

    def reflow(self, event=None):
        columns = max(1, min(self.max_columns, self.winfo_width() // 165))
        if columns == self.columns:
            return
        for index in range(self.max_columns):
            self.columnconfigure(index, weight=1 if index < columns else 0, uniform='cards')
        for index, card in enumerate(self.cards):
            card.grid(row=index // columns, column=index % columns, padx=5, pady=5, sticky='nsew')
        self.columns = columns


class GPIOPanel:
    def __init__(self, root, demo=False):
        self.root = root
        self.demo = demo
        self.backend = DemoBackend() if demo else HardwareBackend()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='gpio')
        self.future = None
        self.closing = False
        self.monitoring = True
        self.timer = None
        self.controls = []
        self.last_errors = None
        self.last_snapshot = None
        self.root.title('Panel GPIO · Raspberry Pi' + (' · SIMULACIÓN' if demo else ''))
        width = min(1120, max(640, root.winfo_screenwidth() - 60))
        height = min(850, max(430, root.winfo_screenheight() - 80))
        root.geometry(f'{width}x{height}')
        root.minsize(600, 400)
        root.configure(bg=BG)
        self._style()
        self._build()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind_all('<MouseWheel>', self._wheel)
        root.bind_all('<Button-4>', self._wheel)
        root.bind_all('<Button-5>', self._wheel)
        self.submit('Conectando hardware e inicializando salidas en OFF…', self.backend.connect, self.render)

    def _style(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('.', font=('Helvetica', 10))
        style.configure('TFrame', background=BG)
        style.configure('TLabel', background=BG, foreground=INK)
        style.configure('TButton', padding=(10, 8))
        style.configure('TNotebook', background=BG, borderwidth=0)
        style.configure('TNotebook.Tab', padding=(16, 9))
        style.configure('Heading.TLabel', font=('Helvetica', 15, 'bold'))

    def _button(self, parent, text, command, **kwargs):
        button = ttk.Button(parent, text=text, command=command)
        button.pack(**kwargs)
        self.controls.append(button)
        return button

    def _build(self):
        header = tk.Frame(self.root, bg=INK, padx=18, pady=12)
        header.pack(fill='x')
        tk.Label(header, text='PANEL DE PRUEBAS GPIO', bg=INK, fg='white',
                 font=('Helvetica', 17, 'bold')).pack(anchor='w')
        tk.Label(header, text='22 zonas  ·  Botón de Llamado  ·  5 actuadores  ·  I2C / RTC',
                 bg=INK, fg='#c6d1e3', font=('Helvetica', 10)).pack(anchor='w', pady=(4, 0))
        if self.demo:
            tk.Label(self.root, text='SIMULACIÓN · Sin acceso al hardware. Hacé clic en una zona para cambiarla.',
                     bg='#ffe2a6', fg='#634000', pady=7, wraplength=700).pack(fill='x')
        toolbar = ttk.Frame(self.root, padding=(14, 9))
        toolbar.pack(fill='x')
        self.monitor_button = ttk.Button(toolbar, text='Pausar monitoreo', command=self.toggle_monitor)
        self.monitor_button.pack(side='left', padx=(0, 8))
        self._button(toolbar, 'Leer una vez', self.refresh, side='left')
        self.summary = ttk.Label(toolbar, text='Esperando lecturas…')
        self.summary.pack(side='right', padx=5)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=12, pady=(0, 8))
        self.pages = {}
        for name in ('Zonas y llamado', 'Actuadores', 'I2C y reloj'):
            page = ScrollPage(self.notebook)
            self.notebook.add(page, text=name)
            self.pages[str(page)] = page
        inputs, outputs, tools = list(self.pages.values())
        ttk.Label(inputs.body, text='Zonas', style='Heading.TLabel').pack(anchor='w')
        ttk.Label(inputs.body, text='Verde: ACTIVA · Rojo: NORMAL · Gris: sin lectura. Entradas activas en bajo.',
                  wraplength=650).pack(anchor='w', pady=(4, 8))
        grid = CardGrid(inputs.body)
        grid.pack(fill='x')
        self.zone_cards = {}
        for number in range(1, 23):
            if number in RASPBERRY_ZONE_PINS:
                pin, physical, name = RASPBERRY_ZONE_PINS[number]
                connection = f'{name} · BCM{pin}\nPin físico {physical}'
            else:
                port, bit = MCP23017_INPUT_BITS[f'ZONA_{number}']
                connection = f'MCP23017\nGP{port}{bit}'
            card = StateCard(grid, f'Zona {number}', connection)
            grid.cards.append(card)
            self.zone_cards[number] = card
            if self.demo:
                card.demo_binding(lambda n=number: self.simulate(n))
        grid.reflow()
        ttk.Label(inputs.body, text='Botón de Llamado', style='Heading.TLabel').pack(anchor='w', pady=(15, 5))
        self.call_card = StateCard(inputs.body, 'Botón de Llamado', 'GPIO17 · BCM17 · Pin físico 11')
        self.call_card.pack(fill='x', padx=5, pady=5)
        if self.demo:
            self.call_card.demo_binding(lambda: self.simulate(None))

        ttk.Label(outputs.body, text='Actuadores', style='Heading.TLabel').pack(anchor='w')
        ttk.Label(outputs.body, text='Nivel alto = ON. Cada botón alterna únicamente su actuador.',
                  wraplength=650).pack(anchor='w', pady=(5, 8))
        act_grid = CardGrid(outputs.body, max_columns=5)
        act_grid.pack(fill='x')
        self.actuator_cards = {}
        for number, (pin, physical) in ACTUATOR_PINS.items():
            card = StateCard(act_grid, f'Actuador {number}', f'GPIO{pin} · BCM{pin}\nPin físico {physical}',
                             action=lambda n=number: self.toggle_actuator(n))
            self.actuator_cards[number] = card
            act_grid.cards.append(card)
        act_grid.reflow()
        self._button(outputs.body, 'Apagar todos', self.all_off, anchor='w', padx=5, pady=15)
        ttk.Label(outputs.body, text='Verde: ON · Rojo: OFF · Gris: sin lectura.\n'
                  'Los estados se conservan al pausar o cambiar de pestaña.\n'
                  'El indicador muestra el nivel GPIO, no confirma movimiento físico.\n'
                  'Al cerrar se ordena OFF y se liberan los pines.',
                  wraplength=680, justify='left').pack(anchor='w', pady=5)

        ttk.Label(tools.body, text='Bus I2C y reloj DS3231', style='Heading.TLabel').pack(anchor='w')
        for label, command in (
            ('Escanear bus I2C 1', self.scan),
            ('Inicializar MCP23017 con pull-up', self.initialize_mcp),
            ('Leer fecha y hora del DS3231', self.read_rtc),
            ('Ajustar DS3231 con la hora del sistema', self.set_rtc),
            ('Reconectar hardware (ordena OFF)', self.reconnect),
        ):
            self._button(tools.body, label, command, fill='x', pady=4)
        self.rtc_label = ttk.Label(tools.body, text='RTC: sin lectura', font=('Helvetica', 12, 'bold'))
        self.rtc_label.pack(anchor='w', pady=(14, 8))
        ttk.Label(tools.body, text='Resultados y diagnóstico', style='Heading.TLabel').pack(anchor='w', pady=(8, 4))
        self.log_widget = tk.Text(tools.body, height=12, wrap='word', bg='white', fg=INK,
                                  font=('Courier', 10), padx=10, pady=10, state='disabled')
        self.log_widget.pack(fill='both', expand=True)
        ttk.Label(tools.body, text='ID_SD (GPIO0/pin 27) debe estar libre de HAT. GPIO15/pin 10 debe estar libre de UART.',
                  wraplength=650).pack(anchor='w', pady=10)
        footer = ttk.Frame(self.root, padding=(14, 7))
        footer.pack(fill='x')
        self.status = ttk.Label(footer, text='Iniciando…', wraplength=660)
        self.status.pack(side='left', fill='x', expand=True)
        self.close_button = ttk.Button(footer, text='Cerrar', command=self.close)
        self.close_button.pack(side='right')

    def _wheel(self, event):
        page = self.pages.get(self.notebook.select())
        if page is not None:
            direction = -1 if event.num == 4 or getattr(event, 'delta', 0) > 0 else 1
            page.canvas.yview_scroll(direction * 3, 'units')

    def log(self, message):
        self.log_widget.configure(state='normal')
        self.log_widget.insert('end', f'[{datetime.now():%H:%M:%S}] {message}\n')
        self.log_widget.see('end')
        self.log_widget.configure(state='disabled')

    def _controls(self):
        state = 'disabled' if self.future is not None or self.closing else 'normal'
        for button in self.controls:
            button.configure(state=state)
        for card in self.actuator_cards.values():
            card.button.configure(state=state if card.active is not None else 'disabled')

    def _cancel_timer(self):
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None

    def submit(self, description, operation, success):
        if self.future is not None or self.closing:
            return
        self._cancel_timer()
        self.status.configure(text=description)
        self.future = self.executor.submit(operation)
        self._controls()
        self.root.after(40, lambda: self._complete(description, success))

    def _complete(self, description, success):
        if not self.future.done():
            self.root.after(40, lambda: self._complete(description, success))
            return
        future, self.future = self.future, None
        try:
            result = future.result()
            if not self.closing:
                success(result)
        except Exception as error:
            self.status.configure(text=f'Error: {error}')
            self.log(f'{description}: {error}')
            if not self.closing:
                messagebox.showerror('No se pudo completar la operación', str(error), parent=self.root)
        if self.closing:
            self._begin_shutdown()
            return
        self._controls()
        self._schedule()

    def _schedule(self):
        self._cancel_timer()
        if self.monitoring and not self.closing and self.future is None:
            self.timer = self.root.after(500, self.refresh)

    def render(self, snapshot):
        self.last_snapshot = snapshot
        for number, raw in snapshot['zones'].items():
            self.zone_cards[number].set_state(None if raw is None else raw == 0)
        raw = snapshot['button']
        self.call_card.set_state(None if raw is None else raw == 0)
        for number, raw in snapshot['actuators'].items():
            self.actuator_cards[number].set_state(None if raw is None else raw == 1, actuator=True)
        known = sum(raw is not None for raw in snapshot['zones'].values())
        active = sum(raw == 0 for raw in snapshot['zones'].values())
        self.summary.configure(text=f'{active} activas · {known}/22 leídas')
        errors = snapshot['errors']
        if errors != self.last_errors:
            if errors:
                self.log('\n'.join(f'{name}: {message}' for name, message in errors.items()))
            elif self.last_errors:
                self.log('Lecturas recuperadas, sin errores.')
            self.last_errors = dict(errors)
        mode = 'Monitoreando' if self.monitoring else 'En pausa · última lectura'
        self.status.configure(text=f'{mode} {snapshot["time"]}' + (' · Ver diagnóstico en I2C y reloj' if errors else ''))

    def refresh(self):
        self.timer = None
        self.submit('Leyendo entradas y salidas…', self.backend.snapshot, self.render)

    def toggle_monitor(self):
        if self.closing:
            return
        self.monitoring = not self.monitoring
        self.monitor_button.configure(text='Pausar monitoreo' if self.monitoring else 'Iniciar monitoreo')
        self._cancel_timer()
        if self.monitoring and self.future is None:
            self.refresh()
        elif not self.monitoring:
            self.status.configure(text='En pausa · se muestran las últimas lecturas; los actuadores siguen disponibles.')

    def toggle_actuator(self, number):
        self.submit(f'Cambiando actuador {number}…', lambda: self.backend.toggle(number), self.render)

    def all_off(self):
        self.submit('Ordenando OFF a todos los actuadores…', self.backend.all_off, self.render)

    def simulate(self, number):
        if self.demo:
            self.submit('Simulando entrada…', lambda: self.backend.simulate_input(number), self.render)

    def scan(self):
        def success(addresses):
            text = ' '.join(f'0x{address:02X}' for address in addresses) or 'ninguno'
            self.log(f'Dispositivos I2C: {text}')
            self.status.configure(text='Escaneo finalizado. Resultados en el diagnóstico.')
        self.submit('Escaneando I2C…', self.backend.scan, success)

    def initialize_mcp(self):
        def success(snapshot):
            self.log('MCP23017 inicializado: entradas con pull-up.')
            self.render(snapshot)
        self.submit('Inicializando MCP23017…', self.backend.initialize_mcp, success)

    def read_rtc(self):
        self.submit('Leyendo DS3231…', self.backend.read_rtc, self._show_rtc)

    def _show_rtc(self, value):
        text = value.strftime('%d/%m/%Y %H:%M:%S')
        self.rtc_label.configure(text=f'Última lectura RTC: {text}')
        self.status.configure(text='Lectura del RTC completada.')
        self.log(f'DS3231: {text}')

    def set_rtc(self):
        self.submit('Ajustando DS3231 con la hora local del sistema…', self.backend.set_rtc, self._show_rtc)

    def reconnect(self):
        self.submit('Reconectando hardware y ordenando OFF…', self.backend.reconnect, self.render)

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.monitoring = False
        self._cancel_timer()
        self.monitor_button.configure(state='disabled')
        self.close_button.configure(state='disabled')
        self._controls()
        self.status.configure(text='Cerrando: ordenando OFF y liberando hardware…')
        if self.future is None:
            self._begin_shutdown()

    def _begin_shutdown(self):
        self.future = self.executor.submit(self.backend.close)
        self.root.after(40, self._finish_shutdown)

    def _finish_shutdown(self):
        if not self.future.done():
            self.root.after(40, self._finish_shutdown)
            return
        try:
            errors = self.future.result()
            if errors:
                messagebox.showerror('Error al cerrar hardware', '\n'.join(errors), parent=self.root)
        finally:
            self.executor.shutdown(wait=False)
            self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description='Panel gráfico de pruebas GPIO para Raspberry Pi')
    parser.add_argument('--demo', action='store_true', help='Simulación explícita sin acceso al hardware')
    args = parser.parse_args()
    root = tk.Tk()
    panel = GPIOPanel(root, demo=args.demo)
    signal.signal(signal.SIGTERM, lambda signum, frame: panel.close())
    try:
        root.mainloop()
    except KeyboardInterrupt:
        panel.close()
        root.mainloop()


if __name__ == '__main__':
    main()
