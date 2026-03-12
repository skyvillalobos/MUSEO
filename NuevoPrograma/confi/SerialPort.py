import tkinter as tk
from tkinter import ttk, scrolledtext
import serial
import serial.tools.list_ports
import threading
import queue as _queue
import time
from datetime import datetime
from typing import Callable, List, Optional

# ─── Palette ──────────────────────────────────────────────────────────────────
BG      = "#0d0f14"
PANEL   = "#13161e"
ACCENT  = "#00e5ff"
ACCENT2 = "#7b2fff"
SUCCESS = "#00ff9d"
DANGER  = "#ff3d5a"
TEXT    = "#e8eaf6"
SUBTEXT = "#5c6380"
BORDER  = "#1e2233"


class SerialMonitor(tk.Tk):
    """
    Ventana de monitor serial con API pública para integración.

    API pública
    -----------
    on_data(callback)       Registra función llamada con cada línea recibida.
    set_queue(q)            Escribe cada línea en una queue.Queue externa.
    get_buffer()            Retorna lista con todas las líneas leídas hasta ahora.
    get_last_line()         Retorna la última línea recibida (str) o None.
    send(text)              Envía texto al puerto serial activo.
    is_connected()          Bool — True si hay conexión abierta.
    current_port()          Nombre del puerto activo o None.
    connect(port, baud)     Conecta programáticamente sin usar la GUI.
    disconnect()            Desconecta.
    """

    def __init__(self):
        super().__init__()
        self.title("Serial Monitor")
        self.geometry("860x620")
        self.minsize(720, 500)
        self.configure(bg=BG)
        self.resizable(True, True)

        # ── Estado interno ────────────────────────────────────────
        self.ser: Optional[serial.Serial] = None
        self.reading = False
        self.read_thread: Optional[threading.Thread] = None
        self.line_count = 0

        # ── API pública ───────────────────────────────────────────
        self._buffer: List[str] = []
        self._last_line: Optional[str] = None
        self._callbacks: List[Callable[[str], None]] = []
        self._external_queue: Optional[_queue.Queue] = None

        # ── Vars GUI ──────────────────────────────────────────────
        self.autoscroll     = tk.BooleanVar(value=True)
        self.show_timestamp = tk.BooleanVar(value=True)

        self._load_fonts()
        self._build_ui()
        self._refresh_ports()

    # ══════════════════════════════════════════════════════════════
    # API PÚBLICA
    # ══════════════════════════════════════════════════════════════

    def on_data(self, callback: Callable[[str], None]) -> None:
        """Registra un callback(line: str) invocado con cada línea nueva."""
        self._callbacks.append(callback)

    def set_queue(self, q: _queue.Queue) -> None:
        """Escribe cada línea recibida en la Queue externa (thread-safe)."""
        self._external_queue = q

    def get_buffer(self) -> List[str]:
        """Retorna una copia de todas las líneas leídas hasta ahora."""
        return list(self._buffer)

    def get_last_line(self) -> Optional[str]:
        """Retorna la última línea recibida o None."""
        return self._last_line

    def send(self, text: str) -> bool:
        """
        Envía texto al puerto serial activo.
        Retorna True si el envío fue exitoso, False si no hay conexión.
        """
        if not self.ser or not self.ser.is_open:
            return False
        self.ser.write(text.encode())
        self._log(f"→ {text.strip()}", "info")
        return True

    def is_connected(self) -> bool:
        """True si hay un puerto serial abierto."""
        return bool(self.ser and self.ser.is_open)

    def current_port(self) -> Optional[str]:
        """Nombre del puerto activo (ej. 'COM3') o None."""
        return self.ser.port if self.is_connected() else None

    def connect(self, port: str, baud: int = 9600) -> bool:
        """
        Conecta programáticamente sin interacción con la GUI.
        Retorna True si la conexión fue exitosa.
        """
        self.port_var.set(port)
        self.baud_var.set(str(baud))
        self._connect()
        return self.is_connected()

    def disconnect(self) -> None:
        """Desconecta el puerto serial activo."""
        self._disconnect()

    # ══════════════════════════════════════════════════════════════
    # CONSTRUCCIÓN DE UI
    # ══════════════════════════════════════════════════════════════

    def _load_fonts(self):
        self.font_mono  = ("Courier New", 11)
        self.font_label = ("Segoe UI", 9)
        self.font_bold  = ("Segoe UI", 9, "bold")
        self.font_title = ("Segoe UI", 13, "bold")

    def _build_ui(self):
        header = tk.Frame(self, bg=PANEL, height=54)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        tk.Label(header, text="⬡", font=("Segoe UI", 18), fg=ACCENT, bg=PANEL).pack(side="left", padx=(18, 6), pady=10)
        tk.Label(header, text="SERIAL MONITOR", font=self.font_title, fg=TEXT, bg=PANEL).pack(side="left", pady=10)
        self.status_dot   = tk.Label(header, text="●", font=("Segoe UI", 14), fg=SUBTEXT, bg=PANEL)
        self.status_dot.pack(side="right", padx=(6, 18))
        self.status_label = tk.Label(header, text="Desconectado", font=self.font_label, fg=SUBTEXT, bg=PANEL)
        self.status_label.pack(side="right")
        tk.Frame(self, bg=ACCENT2, height=2).pack(fill="x")

        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=16, pady=14)

        # Panel izquierdo
        left = tk.Frame(main, bg=BG, width=210)
        left.pack(side="left", fill="y", padx=(0, 14))
        left.pack_propagate(False)

        self._section(left, "PUERTO")
        port_row = tk.Frame(left, bg=BG)
        port_row.pack(fill="x", pady=(0, 8))
        self.port_var = tk.StringVar()
        self.port_cb  = ttk.Combobox(port_row, textvariable=self.port_var,
                                      state="readonly", font=self.font_label, width=14)
        self.port_cb.pack(side="left", fill="x", expand=True)
        self._icon_btn(port_row, "↻", self._refresh_ports, ACCENT).pack(side="left", padx=(6, 0))

        self._section(left, "VELOCIDAD")
        self.baud_var = tk.StringVar(value="9600")
        bauds = ["1200","2400","4800","9600","19200","38400","57600","115200","230400"]
        ttk.Combobox(left, textvariable=self.baud_var, values=bauds,
                     state="readonly", font=self.font_label).pack(fill="x", pady=(0, 8))

        self._section(left, "OPCIONES")
        self._check(left, "Auto-scroll",       self.autoscroll)
        self._check(left, "Mostrar timestamp", self.show_timestamp)

        tk.Frame(left, bg=BG).pack(expand=True, fill="y")
        self.connect_btn = self._big_btn(left, "CONECTAR", self._toggle_connect, ACCENT)
        self.connect_btn.pack(fill="x", pady=(0, 6))
        self._big_btn(left, "LIMPIAR", self._clear_console, SUBTEXT).pack(fill="x")

        # Panel derecho
        right = tk.Frame(main, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        con_hdr = tk.Frame(right, bg=PANEL, height=34)
        con_hdr.pack(fill="x")
        con_hdr.pack_propagate(False)
        tk.Label(con_hdr, text="CONSOLA", font=self.font_bold, fg=SUBTEXT, bg=PANEL).pack(side="left", padx=12, pady=8)
        self.line_label = tk.Label(con_hdr, text="0 líneas", font=self.font_label, fg=SUBTEXT, bg=PANEL)
        self.line_label.pack(side="right", padx=12)

        self.console = scrolledtext.ScrolledText(
            right, bg="#090b10", fg=SUCCESS, insertbackground=ACCENT,
            font=self.font_mono, relief="flat", bd=0,
            selectbackground=ACCENT2, selectforeground=TEXT,
            wrap="word", state="disabled", cursor="arrow"
        )
        self.console.pack(fill="both", expand=True)
        self.console.tag_configure("ts",   foreground=SUBTEXT)
        self.console.tag_configure("data", foreground=SUCCESS)
        self.console.tag_configure("err",  foreground=DANGER)
        self.console.tag_configure("info", foreground=ACCENT)

        send_bar = tk.Frame(right, bg=PANEL, height=44)
        send_bar.pack(fill="x")
        send_bar.pack_propagate(False)
        self.send_var = tk.StringVar()
        send_entry = tk.Entry(send_bar, textvariable=self.send_var, bg="#0d0f14", fg=TEXT,
                              insertbackground=ACCENT, relief="flat", font=self.font_mono, bd=0)
        send_entry.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=8)
        send_entry.bind("<Return>", lambda e: self._gui_send())
        self._icon_btn(send_bar, "↑ ENVIAR", self._gui_send, ACCENT2, width=10).pack(side="right", padx=8, pady=8)

        self.statusbar = tk.Label(self, text="Listo. Selecciona un puerto y haz clic en CONECTAR.",
                                  font=self.font_label, fg=SUBTEXT, bg=PANEL, anchor="w", padx=12)
        self.statusbar.pack(fill="x", side="bottom")
        self._style_widgets()

    # ══════════════════════════════════════════════════════════════
    # WIDGETS HELPER
    # ══════════════════════════════════════════════════════════════

    def _style_widgets(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox",
                         fieldbackground=PANEL, background=PANEL,
                         foreground=TEXT, selectbackground=PANEL,
                         selectforeground=TEXT, bordercolor=BORDER,
                         lightcolor=BORDER, darkcolor=BORDER, arrowcolor=ACCENT)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL)])

    def _section(self, parent, text):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", pady=(10, 4))
        tk.Label(f, text=text, font=("Segoe UI", 8, "bold"), fg=SUBTEXT, bg=BG).pack(side="left")
        tk.Frame(f, bg=BORDER, height=1).pack(side="left", fill="x", expand=True, padx=(8, 0), pady=6)

    def _check(self, parent, text, var):
        f = tk.Frame(parent, bg=BG, cursor="hand2")
        f.pack(fill="x", pady=2)
        tk.Checkbutton(f, variable=var, bg=BG, fg=TEXT, activebackground=BG,
                       activeforeground=ACCENT, selectcolor=PANEL, relief="flat",
                       font=self.font_label, text=text, highlightthickness=0).pack(side="left")

    def _big_btn(self, parent, text, cmd, color):
        return tk.Button(parent, text=text, command=cmd, bg=color, fg=BG,
                         activebackground=TEXT, activeforeground=BG,
                         font=self.font_bold, relief="flat", bd=0,
                         padx=8, pady=10, cursor="hand2")

    def _icon_btn(self, parent, text, cmd, color, width=3):
        return tk.Button(parent, text=text, command=cmd, bg=color, fg=BG,
                         activebackground=TEXT, activeforeground=BG,
                         font=self.font_bold, relief="flat", bd=0,
                         padx=6, pady=4, width=width, cursor="hand2")

    # ══════════════════════════════════════════════════════════════
    # LÓGICA SERIAL
    # ══════════════════════════════════════════════════════════════

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_cb["values"] = ports
        if ports:
            self.port_var.set(ports[0])
            self._log(f"Se encontraron {len(ports)} puerto(s).", "info")
        else:
            self.port_var.set("")
            self._log("No se encontraron puertos seriales.", "err")

    def _toggle_connect(self):
        self._disconnect() if self.reading else self._connect()

    def _connect(self):
        port = self.port_var.get()
        baud = int(self.baud_var.get())
        if not port:
            self._log("Selecciona un puerto primero.", "err")
            return
        try:
            self.ser = serial.Serial(port=port, baudrate=baud, timeout=1)
            self.reading = True
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            self._set_status(True, f"{port} @ {baud} baud")
            self.connect_btn.config(text="DESCONECTAR", bg=DANGER)
            self._log(f"Conectado a {port} a {baud} baud.", "info")
        except serial.SerialException as e:
            self._log(f"Error: {e}", "err")

    def _disconnect(self):
        self.reading = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self._set_status(False)
        self.connect_btn.config(text="CONECTAR", bg=ACCENT)
        self._log("Desconectado.", "info")

    def _read_loop(self):
        """Hilo de lectura: actualiza buffer, queue y dispara callbacks."""
        while self.reading:
            try:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode(errors="ignore").strip()
                    if line:
                        # Almacenamiento interno
                        self._buffer.append(line)
                        self._last_line = line

                        # Queue externa (thread-safe)
                        if self._external_queue is not None:
                            self._external_queue.put(line)

                        # Callbacks externos
                        for cb in self._callbacks:
                            try:
                                cb(line)
                            except Exception:
                                pass

                        # Actualizar GUI en hilo principal
                        self.after(0, self._log, line, "data")
                else:
                    time.sleep(0.01)
            except serial.SerialException as e:
                self.after(0, self._log, f"Error de conexión: {e}", "err")
                self.after(0, self._disconnect)
                break

    def _gui_send(self):
        data = self.send_var.get()
        if data:
            self.send(data + "\n")
            self.send_var.set("")

    # ══════════════════════════════════════════════════════════════
    # CONSOLA
    # ══════════════════════════════════════════════════════════════

    def _log(self, text, tag="data"):
        self.console.config(state="normal")
        if self.show_timestamp.get():
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self.console.insert("end", f"[{ts}] ", "ts")
        self.console.insert("end", text + "\n", tag)
        self.line_count += 1
        self.line_label.config(text=f"{self.line_count} líneas")
        if self.autoscroll.get():
            self.console.see("end")
        self.console.config(state="disabled")

    def _clear_console(self):
        self.console.config(state="normal")
        self.console.delete("1.0", "end")
        self.console.config(state="disabled")
        self.line_count = 0
        self.line_label.config(text="0 líneas")

    def _set_status(self, connected: bool, info=""):
        if connected:
            self.status_dot.config(fg=SUCCESS)
            self.status_label.config(fg=SUCCESS, text="Conectado")
            self.statusbar.config(text=f"  Conectado · {info}")
        else:
            self.status_dot.config(fg=SUBTEXT)
            self.status_label.config(fg=SUBTEXT, text="Desconectado")
            self.statusbar.config(text="  Desconectado.")

    def on_close(self):
        self.reading = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = SerialMonitor()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()