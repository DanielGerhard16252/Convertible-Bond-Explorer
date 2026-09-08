"""Run blocking service calls without touching Qt widgets from worker threads."""

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class JobSignals(QObject):
    completed = Signal(object, object)


class BackgroundJob(QRunnable):
    def __init__(self, function, *args):
        super().__init__()
        self.signals = JobSignals()
        self.function = function
        self.args = args

    @Slot()
    def run(self):
        try:
            result = self.function(*self.args)
        except Exception as error:
            self.signals.completed.emit(None, str(error))
        else:
            self.signals.completed.emit(result, None)
