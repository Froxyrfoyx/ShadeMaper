
import logging
from PySide6.QtCore import QObject, Signal, QMetaObject, Qt, Slot, Q_ARG

class AsyncLogger(QObject):
    log_signal = Signal(str)

    def __init__(self, filename="shademaper.log"):
        super().__init__()
        self.logger = logging.getLogger("Shademaper")
        self.logger.setLevel(logging.DEBUG)

        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fhan = logging.FileHandler(filename, encoding='utf-8')
        fhan.setFormatter(formatter)
        self.logger.addHandler(fhan)

    def log(self, level: str, message: str):
        lvl_clean = level.lower()
        if lvl_clean == 'warn':
            lvl_clean = 'warning'
        elif lvl_clean == 'fatal':
            lvl_clean = 'critical'

        log_method = getattr(self.logger, lvl_clean, self.logger.info)
        log_method(message)

        QMetaObject.invokeMethod(
            self,
            "emit_signal",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, f"[{level.upper()}] {message}")
        )

    @Slot(str)
    def emit_signal(self, formatted_message):
        self.log_signal.emit(formatted_message)
