import sys
from PyQt5.QtWidgets import QApplication
from ui.interfaz import MainMenu

app = QApplication(sys.argv)

ventana = MainMenu()
ventana.show()

sys.exit(app.exec_())