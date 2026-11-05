import sys
import os
import importlib
import traceback
from PyQt5.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QThread, pyqtSignal, Qt


class ImportWorker(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, module_name="Guimain2"):
        super().__init__()
        self.module_name = module_name

    def run(self):
        try:
            importlib.import_module(self.module_name)
            self.finished.emit()
        except Exception:
            self.error.emit(traceback.format_exc())


def show_error_and_quit(splash, err_text):
    try:
        splash.close()
    except Exception:
        pass
    QMessageBox.critical(None, "Launcher Error", f"Failed to start application:\n\n{err_text}")
    QApplication.instance().quit()


def main():
    # make sure working dir is this script's folder
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    app = QApplication(sys.argv)

    pixmap = QPixmap(480, 160)
    pixmap.fill(Qt.white)
    splash = QSplashScreen(pixmap)
    splash.showMessage("Starting SchCAT Market Analyzer...\nPlease wait...",
                       Qt.AlignCenter | Qt.AlignBottom, Qt.black)
    splash.show()
    app.processEvents()

    worker = ImportWorker("Guimain2")

    def on_import_finished():
        try:
            module = importlib.import_module("Guimain2")
            GUIClass = getattr(module, "MarketSmithGUI", None)
            if GUIClass is None:
                raise ImportError("MarketSmithGUI class not found in Guimain2.py")

            main_win = GUIClass()
            main_win.show()
            splash.finish(main_win)
        except Exception:
            show_error_and_quit(splash, traceback.format_exc())

    worker.finished.connect(on_import_finished)
    worker.error.connect(lambda tb: show_error_and_quit(splash, tb))
    worker.start()

    exit_code = app.exec_()

    try:
        if worker.isRunning():
            worker.quit()
            worker.wait(500)
    except Exception:
        pass

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
