from PyQt5.QtWidgets import QApplication, QWidget


class QtFrame:
    def __init__(self):
        self.app = QApplication([])
        self.window = QWidget()

    def start(self):
        self.window.show()
        self.app.exec()
