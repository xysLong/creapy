from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class JobSignals(QObject):
    finished = Signal(int, object)
    failed = Signal(int, object)
    progress = Signal(int, str)


class Job(QRunnable):
    def __init__(self, job_id, fn, signals):
        super().__init__()
        self.job_id = job_id
        self.fn = fn
        self.signals = signals
        self.cancelled = False
        self.setAutoDelete(True)

    def progress(self, done=None, total=None, text=None):
        if self.cancelled:
            return False
        if text:
            self.signals.progress.emit(self.job_id, text if total is None or not done else f"{text} ({done}/{total})")
        return True

    @Slot()
    def run(self):
        try:
            result = self.fn(self.progress)
        except Exception as e:  # noqa: BLE001
            if not self.cancelled:
                self.signals.failed.emit(self.job_id, e)
            return
        if not self.cancelled:
            self.signals.finished.emit(self.job_id, result)


class JobRunner(QObject):
    def __init__(self, parent=None, synchronous=False):
        super().__init__(parent)
        self.synchronous = synchronous
        self.signals = JobSignals()
        self.signals.finished.connect(self._on_finished)
        self.signals.failed.connect(self._on_failed)
        self.signals.progress.connect(self._on_progress)
        self.current = None
        self.callbacks = {}
        self.next_id = 0

    def busy(self):
        return self.current is not None

    def start(self, fn, on_done, on_error=None, on_progress=None):
        self.cancel()
        self.next_id += 1
        job_id = self.next_id
        if self.synchronous:
            try:
                result = fn(lambda *a, **k: True)
            except Exception as e:  # noqa: BLE001
                if on_error:
                    on_error(e)
                return job_id
            on_done(result)
            return job_id
        self.callbacks[job_id] = (on_done, on_error, on_progress)
        self.current = Job(job_id, fn, self.signals)
        QThreadPool.globalInstance().start(self.current)
        return job_id

    def cancel(self):
        if self.current is not None:
            self.current.cancelled = True
            self.callbacks.pop(self.current.job_id, None)
            self.current = None

    def _finish(self, job_id):
        callbacks = self.callbacks.pop(job_id, None)
        if self.current is not None and self.current.job_id == job_id:
            self.current = None
        return callbacks

    def _on_finished(self, job_id, result):
        callbacks = self._finish(job_id)
        if callbacks:
            callbacks[0](result)

    def _on_failed(self, job_id, exc):
        callbacks = self._finish(job_id)
        if callbacks and callbacks[1]:
            callbacks[1](exc)

    def _on_progress(self, job_id, text):
        callbacks = self.callbacks.get(job_id)
        if callbacks and callbacks[2]:
            callbacks[2](text)
