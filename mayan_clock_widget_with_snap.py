
# mayan_clock_widget_with_snap.py
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QSystemTrayIcon, QMenu, QAction
from PySide6.QtCore import QTimer, Qt
import sys, datetime

class MayanClockWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mayan Clock")
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setGeometry(0,0,300,100)
        self.resize(300,100)
        self.update_time()
        timer = QTimer(self)
        timer.timeout.connect(self.update_time)
        timer.start(1000)

        # System tray icon
        tray = QSystemTrayIcon(self)
        tray.setIcon(self.style().standardIcon(QApplication.style().SP_ComputerIcon))
        menu = QMenu()
        exit_action = QAction("Exit")
        exit_action.triggered.connect(sys.exit)
        menu.addAction(exit_action)
        tray.setContextMenu(menu)
        tray.show()
    
    def update_time(self):
        now = datetime.datetime.now()
        self.label.setText(f"Gregorian: {now}\nMayan: LongCount TBD")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = MayanClockWidget()
    w.show()
    sys.exit(app.exec())
