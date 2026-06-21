#!/usr/bin/env python3
"""Speedtest - Aplicativo desktop para teste de velocidade de internet."""

import sys
import os

# Suprimir warning do PySide6 em Python 3.14+ (se houver)
os.environ["QT_LOGGING_RULES"] = "*.debug=false;qt.*.debug=false"

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from app import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Speedtest")
    app.setOrganizationName("SpeedtestApp")

    # Forcar paleta escura no Windows
    app.setStyle("Fusion")
    palette = app.palette()
    palette.setColor(palette.ColorRole.Window, Qt.GlobalColor.black)
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
