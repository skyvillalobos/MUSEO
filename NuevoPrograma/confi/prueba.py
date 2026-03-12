from SerialPort import SerialMonitor
import threading
import time

app = SerialMonitor()

def procesar(linea: str):
    try:
        partes = linea.split(",")
        if len(partes) != 5:
            print(f"Formato inesperado: {linea}")
            return
        n1, n2, n3, n4, n5 = [int(p.strip()) for p in partes]
        print(f"n1={n1}  n2={n2}  n3={n3}  n4={n4}  n5={n5}")
    except ValueError:
        print(f"Error al parsear: {linea}")

def abrir_interfaz():
    """Muestra la ventana si estaba oculta."""
    app.after(0, app.deiconify)

def cerrar_interfaz():
    """Oculta la ventana sin cerrar la conexión serial."""
    app.after(0, app.withdraw)

def mi_logica():
    """Tu código va aquí — corre en paralelo al mainloop."""
    time.sleep(2)

    print("Abriendo interfaz...")
    abrir_interfaz()
    time.sleep(5)

    print("Cerrando interfaz...")
    cerrar_interfaz()
    time.sleep(5)

    print("Volviendo a abrir...")
    abrir_interfaz()

app.on_data(procesar)
app.protocol("WM_DELETE_WINDOW", cerrar_interfaz)  # ocultar en vez de destruir

# Lanza tu lógica en un hilo para no bloquear el mainloop
hilo = threading.Thread(target=mi_logica, daemon=True)
hilo.start()

app.mainloop()