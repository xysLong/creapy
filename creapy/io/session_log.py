import json
import os
import time
import traceback
from datetime import datetime
from PySide6.QtCore import QSettings, QStandardPaths

# Opt-in session log for usability evaluations: one JSON line per event, on the user's own machine,
# never sent anywhere. Parameter VALUES are logged with every render (not just "slider moved"), because the
# forking-paths analysis needs to know which configurations a user visited before settling on one.


class SessionLog:

    def __init__(self):
        self.settings = QSettings("CReA", "creapy.io")
        self.enabled = self.settings.value("logging/enabled", False, type=bool)
        # independent of the QApplication name, so the GUI, tests and notebooks share one folder
        self.folder = os.path.join(QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation),
                                   "creapy.io", "logs")
        self.path = None
        self._file = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.t0 = time.time()
        if self.enabled:
            self._open()

    def _open(self):
        os.makedirs(self.folder, exist_ok=True)
        self.path = os.path.join(self.folder, f"creapy_session_{self.session_id}.jsonl")
        self._file = open(self.path, 'a', encoding='utf-8')
        self.log('session_start')

    def set_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled == self.enabled:
            return
        if enabled:
            self.enabled = True
            self._open()
        else:
            self.log('logging_disabled')
            self.enabled = False
            if self._file:
                self._file.close()
                self._file = None
        self.settings.setValue("logging/enabled", enabled)

    def log(self, event, **data):
        if not self.enabled or self._file is None:
            return
        record = {'t': round(time.time() - self.t0, 3), 'time': datetime.now().isoformat(timespec='seconds'),
                  'event': event}
        record.update({k: _jsonable(v) for k, v in data.items()})
        self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._file.flush()

    def log_error(self, where, exc):
        self.log('error', where=where, error=str(exc), traceback=traceback.format_exc()[-2000:])

    def close(self):
        if self._file:
            self.log('session_end')
            self._file.close()
            self._file = None


def _jsonable(value):
    # numpy scalars, tuples of colors etc. -> plain JSON types; anything else -> str
    try:
        json.dumps(value)
        return value
    except TypeError:
        if hasattr(value, 'item'):
            return value.item()
        if isinstance(value, (list, tuple)):
            return [_jsonable(v) for v in value]
        if isinstance(value, dict):
            return {str(k): _jsonable(v) for k, v in value.items()}
        return str(value)
