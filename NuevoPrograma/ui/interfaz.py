import random
import threading
import os
import sys
import time
import subprocess

from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QApplication
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont, QMovie
from PyQt5.QtCore import QTimer, QUrl, Qt
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget

# Intentar importar serial para el lector directo (sin Tkinter)
try:
    import serial
    import serial.tools.list_ports
    _SERIAL_DISPONIBLE = True
except ImportError:
    _SERIAL_DISPONIBLE = False
    print("[AVISO] pyserial no está instalado. Instálalo con: pip install pyserial")


class _SerialReader:
    """
    Lector serial mínimo que reutiliza la lógica de _read_loop de SerialMonitor
    pero sin ninguna dependencia de Tkinter. Corre en un hilo daemon.
    """

    def __init__(self, port: str, baud: int = 9600):
        self._port = port
        self._baud = baud
        self._ser = None
        self._reading = False
        self._thread = None
        self._callbacks = []

    def on_data(self, callback):
        self._callbacks.append(callback)

    def start(self) -> bool:
        """Abre el puerto y arranca el hilo lector. Retorna True si conectó."""
        try:
            self._ser = serial.Serial(port=self._port, baudrate=self._baud, timeout=1)
            self._reading = True
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()
            return True
        except serial.SerialException as e:
            print(f"[ERROR SERIAL] No se pudo abrir {self._port}: {e}")
            return False

    def stop(self):
        """Detiene la lectura y cierra el puerto."""
        self._reading = False
        try:
            if self._ser and self._ser.is_open:
                self._ser.close()
        except Exception:
            pass

    def is_connected(self) -> bool:
        return bool(self._ser and self._ser.is_open)

    def _read_loop(self):
        """Igual que SerialMonitor._read_loop pero sin llamadas a Tkinter."""
        while self._reading:
            try:
                if self._ser.in_waiting > 0:
                    line = self._ser.readline().decode(errors="ignore").strip()
                    if line:
                        for cb in self._callbacks:
                            try:
                                cb(line)
                            except Exception:
                                pass
                else:
                    time.sleep(0.01)
            except serial.SerialException as e:
                print(f"[ERROR SERIAL] Conexión perdida: {e}")
                self._reading = False
                break


class Overlay(QWidget):
    def __init__(self, carrera):
        super().__init__(carrera)
        self.carrera = carrera
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        try:
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setStyleSheet("background: transparent;")
        except Exception:
            pass

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setFont(QFont("Arial", 20))

        # Título con sombra para buen contraste sobre las bicicletas
        painter.setPen(QColor(0, 0, 0))
        painter.drawText(421, 41, "Carrera de Bicicletas")
        painter.setPen(QColor(255, 215, 0))
        painter.drawText(420, 40, "Carrera de Bicicletas")

        # meta
        painter.setPen(QColor(255, 255, 255))
        painter.drawLine(self.carrera.meta, 0, self.carrera.meta, 600)

        # bicicletas
        for i in range(5):
            if self.carrera.ganador == i:
                salto = int(10 * abs((self.carrera.animacion % 20) - 10) / 10)
                painter.drawPixmap(self.carrera.x[i], self.carrera.y[i] - salto, 80, 60, self.carrera.bicis[i])
            else:
                painter.drawPixmap(self.carrera.x[i], self.carrera.y[i], 80, 60, self.carrera.bicis[i])

        # semaforo
        if self.carrera.estado_semaforo == 0:
            painter.drawPixmap(560, 20, 80, 80, self.carrera.rojo)
        elif self.carrera.estado_semaforo == 1:
            painter.drawPixmap(560, 20, 80, 80, self.carrera.amarillo)
        elif self.carrera.estado_semaforo == 2:
            painter.drawPixmap(560, 20, 80, 80, self.carrera.verde)

        # ganador
        if self.carrera.ganador is not None:
            painter.setFont(QFont("Arial", 30, QFont.Bold))
            painter.setPen(QColor(0, 0, 0))
            painter.drawText(451, 521, "GANADOR JUGADOR " + str(self.carrera.ganador + 1))
            painter.setPen(QColor(0, 255, 255))
            painter.drawText(450, 520, "GANADOR JUGADOR " + str(self.carrera.ganador + 1))

        # indicador estado serial
        painter.setFont(QFont("Arial", 12))
        if self.carrera._menu_ref is not None and self.carrera._menu_ref.serial_activo:
            painter.setPen(QColor(0, 200, 0))
            painter.drawText(10, 580, "● Puerto serial activo")
        else:
            painter.setPen(QColor(200, 200, 200))
            painter.drawText(10, 580, "○ Puerto serial inactivo")


class Carrera(QWidget):

    def __init__(self, menu_ref, serial_lock, serial_ultimo):
        super().__init__()

        self.setWindowTitle("Carrera de Bicicletas - Parque Lineal Tepic")
        self.setGeometry(100, 100, 1200, 600)
        try:
            self.setStyleSheet("background-color: #1b2430;")
        except Exception:
            pass

        # Referencia al menú para consultar serial_activo en tiempo real
        self._menu_ref = menu_ref
        self._serial_lock = serial_lock
        # Lista mutable compartida: siempre contiene el último [n1,n2,n3,n4,n5]
        self._serial_ultimo = serial_ultimo

        # VIDEO DE FONDO
        self.video = QVideoWidget(self)
        self.video.setGeometry(0, 0, 1200, 600)

        self.player = QMediaPlayer()
        self.player.setVideoOutput(self.video)
        try:
            if hasattr(self.player, 'errorOccurred'):
                self.player.errorOccurred.connect(self.on_media_error)
            elif hasattr(self.player, 'error'):
                self.player.error.connect(self.on_media_error)
        except Exception:
            pass

        fondo_mp4 = "assets/video/fondo.mp4"
        fondo_gif = "assets/video/fondo.gif"

        try:
            if os.path.exists(fondo_mp4):
                self.player.setMedia(QMediaContent(QUrl.fromLocalFile(fondo_mp4)))
                self.player.play()
            elif os.path.exists(fondo_gif):
                raise Exception("MP4 no disponible, usar GIF")
        except Exception:
            try:
                if os.path.exists(fondo_gif):
                    self.movie_label = QLabel(self)
                    self.movie_label.setGeometry(0, 0, 1200, 600)
                    self.movie = QMovie(fondo_gif)
                    self.movie_label.setMovie(self.movie)
                    self.movie.start()
                    self.movie_label.show()
                    try:
                        self.video.hide()
                    except Exception:
                        pass
            except Exception:
                pass

        # videos finales por cada bici (index 0 -> video1.mp4)
        self.final_videos = [
            "assets/videos_finales/video1.mp4",
            "assets/videos_finales/video2.mp4",
            "assets/videos_finales/video3.mp4",
            "assets/videos_finales/video4.mp4",
            "assets/videos_finales/video5.mp4",
        ]

        self.reproduciendo_final = False

        # Overlay para dibujar elementos encima del video
        try:
            self.overlay = Overlay(self)
            self.overlay.setGeometry(0, 0, 1200, 600)
            self.overlay.show()
        except Exception:
            self.overlay = None

        # LOGOS
        self.logo1 = QLabel(self)
        self.logo1.setPixmap(QPixmap("assets/logos/logococyten.png"))
        self.logo1.setGeometry(10, 10, 64, 64)
        self.logo1.setScaledContents(True)
        try:
            self.logo1.setStyleSheet("background: transparent;")
            self.logo1.setAttribute(Qt.WA_TranslucentBackground)
        except Exception:
            pass

        self.logo2 = QLabel(self)
        self.logo2.setPixmap(QPixmap("assets/logos/logomuseo.png"))
        self.logo2.setGeometry(10, 84, 64, 64)
        self.logo2.setScaledContents(True)
        try:
            self.logo2.setStyleSheet("background: transparent;")
            self.logo2.setAttribute(Qt.WA_TranslucentBackground)
        except Exception:
            pass

        try:
            self.logo1.raise_()
            self.logo2.raise_()
        except Exception:
            pass

        try:
            self.top_bar = QLabel(self)
            self.top_bar.setGeometry(0, 0, 1200, 56)
            self.top_bar.setStyleSheet("background-color: rgba(0,0,0,0.15);")
            self.top_bar.lower()
        except Exception:
            pass

        # bicicletas
        self.bicis = [
            QPixmap("assets/bicicletas/bici1.png"),
            QPixmap("assets/bicicletas/bici2.png"),
            QPixmap("assets/bicicletas/bici3.png"),
            QPixmap("assets/bicicletas/bici4.png"),
            QPixmap("assets/bicicletas/bici5.png"),
        ]

        # posiciones
        self.x = [320, 320, 320, 320, 320]
        self.y = [120, 200, 280, 360, 440]

        self.meta = 1100
        self.ganador = None
        self.animacion = 0

        # SEMAFORO
        self.estado_semaforo = 0

        self.rojo     = QPixmap("assets/semaforo/rojo.png")
        self.amarillo = QPixmap("assets/semaforo/amarillo.png")
        self.verde    = QPixmap("assets/semaforo/verde.png")

        self.timer_semaforo = QTimer()
        self.timer_semaforo.timeout.connect(self.cambiar_semaforo)
        self.timer_semaforo.start(1000)

        # TIMER PRINCIPAL
        self.timer = QTimer()
        self.timer.timeout.connect(self.actualizar)
        self.timer.start(40)

    # ── SEMAFORO ─────────────────────────────────────────────────────────────

    def cambiar_semaforo(self):
        self.estado_semaforo += 1
        if self.estado_semaforo > 3:
            self.timer_semaforo.stop()

    # ── LECTURA DATOS SERIAL ─────────────────────────────────────────────────

    def leer_serial(self):
        """
        Lee el último vector recibido del serial y suma sus valores a las posiciones.
        Se llama cada tick (40ms), por lo que las bicis avanzan de forma continua
        mientras el Arduino siga mandando valores distintos de 0.
        """
        with self._serial_lock:
            valores = list(self._serial_ultimo)

        for i in range(5):
            self.x[i] += valores[i]

    # ── ACTUALIZACIÓN PRINCIPAL ───────────────────────────────────────────────

    def actualizar(self):
        if self.ganador is None:
            if self.estado_semaforo >= 3:
                serial_activo = (
                    self._menu_ref is not None and
                    self._menu_ref.serial_activo
                )
                if serial_activo:
                    self.leer_serial()
                else:
                    # modo prueba sin serial: movimiento aleatorio
                    for i in range(5):
                        self.x[i] += random.randint(0, 3)

                for i in range(5):
                    if self.x[i] >= self.meta:
                        self.ganador = i
        else:
            self.animacion += 1
            if not self.reproduciendo_final and self.ganador is not None:
                self.mostrar_video_ganador()

        self.update()

    # ── VIDEO GANADOR ─────────────────────────────────────────────────────────

    def mostrar_video_ganador(self):
        try:
            idx = int(self.ganador)
            if 0 <= idx < len(self.final_videos):
                ruta = self.final_videos[idx]
                try:
                    self.player.stop()
                except Exception:
                    pass
                try:
                    ruta_gif = os.path.splitext(ruta)[0] + ".gif"
                    ruta_final = ruta_gif if os.path.exists(ruta_gif) else ruta
                    self.final_screen = FinalScreen(self, ruta_final)
                    self.final_screen.show()
                    self.reproduciendo_final = True
                    return
                except Exception:
                    pass
        except Exception:
            pass

    # ── RESET ─────────────────────────────────────────────────────────────────

    def reset_race(self):
        """Reinicia el estado de la carrera para volver a jugar."""
        try:
            self.ganador = None
            self.animacion = 0
            self.reproduciendo_final = False
            self.x = [320, 320, 320, 320, 320]
            self.estado_semaforo = 0
            self.timer_semaforo.start(1000)
            with self._serial_lock:
                for i in range(5):
                    self._serial_ultimo[i] = 0
            try:
                if hasattr(self, 'final_screen') and self.final_screen is not None:
                    try:
                        self.final_screen.close()
                    except Exception:
                        pass
                    self.final_screen = None
            except Exception:
                pass
            try:
                fondo_mp4 = "assets/video/fondo.mp4"
                if os.path.exists(fondo_mp4):
                    self.player.setMedia(QMediaContent(QUrl.fromLocalFile(fondo_mp4)))
                    self.player.play()
            except Exception:
                pass
        except Exception:
            pass

    # ── ERRORES ───────────────────────────────────────────────────────────────

    def _mostrar_error(self, msg):
        try:
            if not hasattr(self, 'error_label') or self.error_label is None:
                self.error_label = QLabel(self)
                self.error_label.setStyleSheet(
                    "background-color: rgba(0,0,0,180); color: white; padding:12px; border-radius:6px;"
                )
                self.error_label.setWordWrap(True)
                self.error_label.setGeometry(320, 260, 560, 80)
                self.error_label.setAlignment(Qt.AlignCenter)
                self.error_label.show()
            self.error_label.setText(msg)
            self.error_label.show()
            self.error_label.raise_()
        except Exception:
            pass

    def on_media_error(self, *args):
        try:
            err_str = self.player.errorString()
        except Exception:
            err_str = "Error al reproducir el video."
        msg = (
            "No se pudo reproducir el video.\n"
            "Código/descripción: %s\n"
            "Prueba instalar códecs (K-Lite) o convertir los MP4 a H.264/AAC."
        ) % err_str
        self._mostrar_error(msg)

    def paintEvent(self, event):
        return

    def closeEvent(self, event):
        super().closeEvent(event)


# ── MENÚ PRINCIPAL ────────────────────────────────────────────────────────────

class MainMenu(QWidget):
    """Pantalla principal para controlar la aplicación y proyectores."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Menú - Carrera de Bicicletas")
        self.setGeometry(100, 100, 800, 580)
        try:
            self.setStyleSheet("background-color: #0f1720;")
        except Exception:
            pass

        # Estado serial
        self.serial_activo = False          # True cuando _SerialReader está corriendo
        self._serial_reader = None          # instancia de _SerialReader
        self._serial_lock = threading.Lock()
        # Último vector recibido — se aplica cada tick sin consumirse
        self._serial_ultimo = [0, 0, 0, 0, 0]

        # Logos
        try:
            self.logo1 = QLabel(self)
            pix1 = QPixmap("assets/logos/logococyten.png")
            self.logo1.setPixmap(pix1)
            self.logo1.setGeometry(10, 10, 64, 64)
            self.logo1.setScaledContents(True)
            self.logo1.setStyleSheet("background: transparent;")
            self.logo1.setAttribute(Qt.WA_TranslucentBackground)

            self.logo2 = QLabel(self)
            pix2 = QPixmap("assets/logos/logomuseo.png")
            self.logo2.setPixmap(pix2)
            self.logo2.setGeometry(10, 84, 64, 64)
            self.logo2.setScaledContents(True)
            self.logo2.setStyleSheet("background: transparent;")
            self.logo2.setAttribute(Qt.WA_TranslucentBackground)
        except Exception:
            pass

        cx = self.width() // 2

        btn_start = QPushButton("Iniciar Carrera", self)
        btn_start.setGeometry(cx - 100, 160, 200, 48)
        btn_start.setStyleSheet(
            "background-color:#1f8bff;color:white;border-radius:6px;font-weight:bold;"
        )
        btn_start.clicked.connect(self.start_race)

        self.btn_serial = QPushButton("🔌 Puerto Serial", self)
        self.btn_serial.setGeometry(cx - 100, 224, 200, 40)
        self.btn_serial.setStyleSheet(
            "background-color:#2b8cff;color:white;border-radius:6px;font-weight:bold;"
        )
        self.btn_serial.clicked.connect(self.abrir_serial_port)

        self.btn_cerrar_serial = QPushButton("✖ Cerrar Serial", self)
        self.btn_cerrar_serial.setGeometry(cx - 100, 274, 200, 40)
        self.btn_cerrar_serial.setStyleSheet(
            "background-color:#ff8c00;color:white;border-radius:6px;font-weight:bold;"
        )
        self.btn_cerrar_serial.clicked.connect(self.cerrar_serial_port)
        self.btn_cerrar_serial.setEnabled(False)

        # NUEVO: Botón para abrir proyectores
        self.btn_proyectores = QPushButton("🎬 Proyectores", self)
        self.btn_proyectores.setGeometry(cx - 100, 324, 200, 40)
        self.btn_proyectores.setStyleSheet(
            "background-color:#9c27b0;color:white;border-radius:6px;font-weight:bold;"
        )
        self.btn_proyectores.clicked.connect(self.abrir_proyectores)

        self.lbl_serial_status = QLabel("○ Puerto serial inactivo", self)
        self.lbl_serial_status.setGeometry(cx - 120, 374, 240, 24)
        self.lbl_serial_status.setAlignment(Qt.AlignCenter)
        self.lbl_serial_status.setStyleSheet("color: #888; font-size: 13px;")

        btn_shutdown = QPushButton("Apagar proyectores y salir", self)
        btn_shutdown.setGeometry(cx - 150, 420, 300, 40)
        btn_shutdown.setStyleSheet(
            "background-color:#ff4d4f;color:white;border-radius:6px;font-weight:bold;"
        )
        btn_shutdown.clicked.connect(self.shutdown_and_exit)

    # ── ABRIR PROYECTORES ────────────────────────────────────────────────────

    def abrir_proyectores(self):
        """Abre el archivo main.py de ProyectoProyeccion en una nueva ventana."""
        try:
            # Ruta relativa: ../ProyectoProyeccion/main.py
            ruta_proyectores = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "ProyectoProyeccion", "main.py")
            )
            
            # Verificar que el archivo existe
            if not os.path.exists(ruta_proyectores):
                self.lbl_serial_status.setText(f"✖ No se encontró: ProyectoProyeccion/main.py")
                self.lbl_serial_status.setStyleSheet("color: #ff4d4f; font-size: 11px;")
                return
            
            # Abrir en una nueva ventana de Python
            subprocess.Popen([sys.executable, ruta_proyectores])
            self.lbl_serial_status.setText("✓ Abriendo proyectores...")
            self.lbl_serial_status.setStyleSheet("color: #00c853; font-size: 12px;")
            
        except Exception as e:
            self.lbl_serial_status.setText(f"✖ Error al abrir proyectores")
            self.lbl_serial_status.setStyleSheet("color: #ff4d4f; font-size: 11px;")
            print(f"[ERROR] {str(e)}")

    # ── MANEJO DE SerialPort.py ──────────────────────────────────────────────

    def abrir_serial_port(self):
        """Abre el diálogo para elegir puerto y arranca _SerialReader."""
        if self.serial_activo:
            return
        if not _SERIAL_DISPONIBLE:
            self.lbl_serial_status.setText("✖ pyserial no instalado")
            self.lbl_serial_status.setStyleSheet("color: #ff4d4f; font-size: 12px;")
            return
        try:
            # Detectar puertos disponibles
            puertos = [p.device for p in serial.tools.list_ports.comports()]
            if not puertos:
                self.lbl_serial_status.setText("✖ No se detectaron puertos COM")
                self.lbl_serial_status.setStyleSheet("color: #ff4d4f; font-size: 12px;")
                return

            # Usar el primer puerto disponible (el usuario puede cambiar baud si necesita)
            puerto = puertos[0]
            print(f"[SERIAL] Conectando a {puerto}...")

            self._serial_reader = _SerialReader(port=puerto, baud=9600)
            self._serial_reader.on_data(self._procesar_linea)

            if not self._serial_reader.start():
                self.lbl_serial_status.setText(f"✖ No se pudo abrir {puerto}")
                self.lbl_serial_status.setStyleSheet("color: #ff4d4f; font-size: 12px;")
                return

            self.serial_activo = True
            self.btn_serial.setEnabled(False)
            self.btn_cerrar_serial.setEnabled(True)
            self.lbl_serial_status.setText(f"● {puerto} activo")
            self.lbl_serial_status.setStyleSheet("color: #00c853; font-size: 13px;")
            print(f"[SERIAL] Conectado a {puerto}")

        except Exception as e:
            self.lbl_serial_status.setText(f"Error: {e}")
            self.lbl_serial_status.setStyleSheet("color: #ff4d4f; font-size: 12px;")

    def _procesar_linea(self, linea: str):
        """
        Callback que _SerialReader llama por cada línea recibida del puerto serial.
        Formato esperado: "*n1,n2,n3,n4,n5/"
        """
        try:
            # Validar delimitadores
            if not linea.startswith("*"):
                print(f"[ERROR SERIAL] La cadena no inicia con '*' -> '{linea}'")
                return
            if not linea.endswith("/"):
                print(f"[ERROR SERIAL] La cadena no termina con '/' -> '{linea}'")
                return
            contenido = linea[1:-1]  # quitar '*' y '/'
            partes = contenido.split(",")
            if len(partes) != 5:
                print(f"[ERROR SERIAL] Se esperaban 5 valores pero se recibieron {len(partes)} -> '{linea}'")
                return
            n1, n2, n3, n4, n5 = [int(p.strip()) for p in partes]
            print(f"n1={n1}  n2={n2}  n3={n3}  n4={n4}  n5={n5}")
            with self._serial_lock:
                # Dividir entre 3 para que las bicis tarden más en llegar a la meta.
                # Ajusta este divisor para calibrar la velocidad (mayor = más lento).
                self._serial_ultimo[:] = [n1 // 8, n2 // 8, n3 // 8, n4 // 8, n5 // 8]
        except ValueError:
            print(f"[ERROR SERIAL] No se pudieron convertir los valores a enteros -> '{linea}'")

    def cerrar_serial_port(self):
        """Detiene _SerialReader y resetea el estado serial."""
        if self._serial_reader is not None:
            self._serial_reader.stop()
            self._serial_reader = None
        self.serial_activo = False
        with self._serial_lock:
            self._serial_ultimo[:] = [0, 0, 0, 0, 0]
        self.btn_serial.setEnabled(True)
        self.btn_cerrar_serial.setEnabled(False)
        self.lbl_serial_status.setText("○ Puerto serial inactivo")
        self.lbl_serial_status.setStyleSheet("color: #888; font-size: 13px;")
        print("[SERIAL] Desconectado.")

    # ── CARRERA ───────────────────────────────────────────────────────────────

    def start_race(self):
        try:
            self.carrera = Carrera(
                menu_ref=self,
                serial_lock=self._serial_lock,
                serial_ultimo=self._serial_ultimo,
            )
            self.carrera.show()
            self.hide()
        except Exception:
            pass

    def shutdown_and_exit(self):
        self.cerrar_serial_port()
        try:
            script = os.path.join(os.getcwd(), 'scripts', 'shutdown_projectors.bat')
            if os.path.exists(script):
                os.system(f'"{script}"')
        except Exception:
            pass
        finally:
            try:
                QApplication.quit()
            except Exception:
                try:
                    sys.exit(0)
                except Exception:
                    pass


# ── PANTALLA FINAL ────────────────────────────────────────────────────────────

class FinalScreen(QWidget):
    """Pantalla superpuesta para reproducir el video/GIF del ganador."""

    def __init__(self, parent, ruta):
        super().__init__(parent)
        self.ruta = ruta
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setGeometry(parent.geometry())
        self.setStyleSheet("background-color: black;")

        if ruta.lower().endswith('.gif') and os.path.exists(ruta):
            self.label = QLabel(self)
            self.label.setGeometry(0, 0, self.width(), self.height())
            self.label.setAlignment(Qt.AlignCenter)
            self.movie = QMovie(ruta)
            self.label.setMovie(self.movie)
            self.movie.start()
            self.label.show()
        else:
            try:
                self.video = QVideoWidget(self)
                self.video.setGeometry(0, 0, self.width(), self.height())
                self.player = QMediaPlayer()
                self.player.setVideoOutput(self.video)
                self.player.setMedia(QMediaContent(QUrl.fromLocalFile(ruta)))
                self.player.play()
                self.video.show()
            except Exception:
                self.label = QLabel(self)
                self.label.setGeometry(0, 0, self.width(), self.height())
                self.label.setAlignment(Qt.AlignCenter)
                self.label.setStyleSheet("color: white;")
                self.label.setText("No se pudo reproducir el video final.")
                self.label.show()

        try:
            self.logo1 = QLabel(self)
            self.logo1.setPixmap(QPixmap("assets/logos/logococyten.png"))
            self.logo1.setGeometry(12, 12, 64, 64)
            self.logo1.setScaledContents(True)
            self.logo1.setStyleSheet("background: transparent;")
            self.logo1.setAttribute(Qt.WA_TranslucentBackground)
        except Exception:
            pass

        try:
            self.logo2 = QLabel(self)
            self.logo2.setPixmap(QPixmap("assets/logos/logomuseo.png"))
            self.logo2.setGeometry(12, 84, 64, 64)
            self.logo2.setScaledContents(True)
            self.logo2.setStyleSheet("background: transparent;")
            self.logo2.setAttribute(Qt.WA_TranslucentBackground)
        except Exception:
            pass

        try:
            self.btn_replay = QPushButton("Volver a jugar", self)
            btn_w, btn_h = 160, 40
            self.btn_replay.setGeometry(
                self.width() - btn_w - 20, self.height() - btn_h - 20, btn_w, btn_h
            )
            self.btn_replay.setStyleSheet(
                "background-color:#2b8cff;color:white;border-radius:6px;font-weight:bold;"
            )
            self.btn_replay.show()
            self.btn_replay.clicked.connect(self.on_replay)
        except Exception:
            pass

        try:
            if hasattr(self, 'video'):
                self.video.lower()
            for w in ('logo1', 'logo2', 'btn_replay'):
                if hasattr(self, w):
                    getattr(self, w).raise_()
        except Exception:
            pass

    def mousePressEvent(self, event):
        try:
            if hasattr(self, 'player'):
                self.player.stop()
            if hasattr(self, 'movie'):
                self.movie.stop()
        finally:
            self.close()

    def on_replay(self):
        try:
            parent = self.parent()
            if parent is not None and hasattr(parent, 'reset_race'):
                parent.reset_race()
        finally:
            try:
                if hasattr(self, 'player'):
                    self.player.stop()
                if hasattr(self, 'movie'):
                    self.movie.stop()
            except Exception:
                pass
            self.close()