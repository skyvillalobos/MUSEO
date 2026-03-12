import pyglet
import serial
import serial.tools.list_ports
import os

# --- CONFIGURACIÓN DE ARCHIVO ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_FILE = os.path.join(BASE_DIR, "config_puertos.txt")
COMANDO_APAGAR = b'PWR OFF\r\n' # Ajusta según tu marca (Epson usa este)
COMANDO_ENCENDER = b'PWR ON\r\n' # Ajusta según tu marca

def guardar_puertos(lista):
    with open(CONFIG_FILE, "w") as f:
        f.write(",".join(lista))

def cargar_puertos():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            contenido = f.read().strip()
            return contenido.split(",") if contenido else []
    return []

# --- LÓGICA DE HARDWARE ---
puertos_disponibles = [p.device for p in serial.tools.list_ports.comports()]
puertos_seleccionados = cargar_puertos()

def apagar_proyectores():
    for p in puertos_seleccionados:
        try:
            with serial.Serial(p, 9600, timeout=1) as ser:
                ser.write(COMANDO_APAGAR)
                print(f"Comando enviado a {p}")
        except:
            print(f"Error al conectar con {p}")
    pyglet.app.exit()

def encender_proyectores():
    targets = puertos_seleccionados if puertos_seleccionados else puertos_disponibles
    for p in targets:
        try:
            with serial.Serial(p, 9600, timeout=1) as ser:
                ser.write(COMANDO_ENCENDER)
                print(f"Encendido: comando enviado a {p}")
        except Exception as e:
            print(f"Error encendiendo {p}: {e}")

# --- INTERFAZ PYGLET ---
try:
    display = pyglet.display.get_display()
    screens = display.get_screens()
except Exception:
    screens = []

ventanas = []
# Crear ventanas (máximo 2). Si no hay pantallas detectadas, crear una ventana de fallback.
if screens:
    for i in range(min(2, len(screens))):
        win = pyglet.window.Window(fullscreen=True, screen=screens[i])
        ventanas.append(win)
else:
    win = pyglet.window.Window(width=800, height=600, caption="Proyeccion (fallback)")
    ventanas.append(win)

batch = pyglet.graphics.Batch()
labels_puertos = []

# Crear lista visual de puertos
win0_height = ventanas[0].height if ventanas else 600
for i, nombre in enumerate(puertos_disponibles):
    color = (0, 255, 0, 255) if nombre in puertos_seleccionados else (200, 200, 200, 255)
    lbl = pyglet.text.Label(f"Puerto: {nombre}", x=50, y=win0_height - 100 - (i*40), 
                            batch=batch, font_size=16, color=color)
    labels_puertos.append((lbl, nombre))

# Botón Rojo de Apagado
boton_rect = pyglet.shapes.Rectangle(x=50, y=50, width=200, height=50, color=(200, 0, 0), batch=batch)
boton_texto = pyglet.text.Label("APAGAR", x=150, y=75, anchor_x='center', anchor_y='center', batch=batch)

# --- EVENTO DE MOUSE EN VENTANA 0 ---
@ventanas[0].event
def on_mouse_press(x, y, button, modifiers):
    global puertos_seleccionados
    
    # Clic en puertos para seleccionar/deseleccionar
    for lbl, nombre in labels_puertos:
        if (x > lbl.x and x < lbl.x + 150 and y > lbl.y and y < lbl.y + 25):
            if nombre in puertos_seleccionados:
                puertos_seleccionados.remove(nombre)
                lbl.color = (200, 200, 200, 255)
            else:
                puertos_seleccionados.append(nombre)
                lbl.color = (0, 255, 0, 255)
            guardar_puertos(puertos_seleccionados)

    # Clic en botón Apagar
    if (x > boton_rect.x and x < boton_rect.x + boton_rect.width and
        y > boton_rect.y and y < boton_rect.y + boton_rect.height):
        apagar_proyectores()

# --- EVENTO DE DRAW EN VENTANA 0 ---
@ventanas[0].event
def on_draw():
    ventanas[0].clear()
    batch.draw() # Aquí se ve el menú y botón

# --- EVENTOS PARA VENTANA 1 (SOLO SI EXISTE) ---
if len(ventanas) > 1:
    @ventanas[1].event
    def on_draw():
        ventanas[1].clear()
        # Aquí puedes poner el contenido para el segundo proyector
        
    @ventanas[1].event
    def on_mouse_press(x, y, button, modifiers):
        # Opcional: permitir cerrar con clic en la ventana 2
        pass

pyglet.app.run()