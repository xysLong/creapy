import json
import os
import platform
import re
import sys
import time
import traceback
import zipfile
from datetime import datetime
from PySide6.QtCore import QSettings, QStandardPaths, QObject, QEvent, Qt, QTimer, QLocale, qVersion
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QApplication, QWidget, QAbstractButton, QComboBox, QAbstractSlider, QAbstractSpinBox,
                               QAbstractItemView, QHeaderView, QLabel, QLineEdit, QDialog, QMessageBox, QFileDialog,
                               QTabBar)

HOVER_MIN_MS = 100
WHEEL_GAP_S = 0.5
CHANGE_SETTLE_MS = 400
HEARTBEAT_S = 60
TEXT_LIMIT = 120

ACTIVE_LOG = None
_RECORDER = None

WATCHED = frozenset([QEvent.MouseButtonPress, QEvent.MouseButtonDblClick, QEvent.Enter, QEvent.Leave, QEvent.ToolTip,
                     QEvent.KeyPress, QEvent.Wheel, QEvent.Show, QEvent.Hide, QEvent.Resize])
SPECIAL_KEYS = {Qt.Key_Escape: 'Escape', Qt.Key_Return: 'Return', Qt.Key_Enter: 'Enter', Qt.Key_Tab: 'Tab',
                Qt.Key_Backtab: 'Backtab', Qt.Key_Delete: 'Delete', Qt.Key_Backspace: 'Backspace', Qt.Key_Space: 'Space',
                Qt.Key_Left: 'Left', Qt.Key_Right: 'Right', Qt.Key_Up: 'Up', Qt.Key_Down: 'Down',
                Qt.Key_PageUp: 'PageUp', Qt.Key_PageDown: 'PageDown', Qt.Key_Home: 'Home', Qt.Key_End: 'End'}
BUTTON_NAMES = {Qt.LeftButton: 'left', Qt.RightButton: 'right', Qt.MiddleButton: 'middle'}


def log_folder():
    """Where the session logs live: CREAPY_LOG_DIR when set, else the user's data folder."""
    override = os.environ.get('CREAPY_LOG_DIR')
    if override:
        return override
    return os.path.join(QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation), "creapy.io", "logs")


class SessionLog(QObject):
    """One JSON-lines file per session on this computer: views, parameters, clicks, hovers, dialogs and errors."""

    def __init__(self):
        super().__init__()
        self.settings = QSettings("CReA", "creapy.io")
        self.enabled = self.settings.value("logging/enabled", True, type=bool)
        self.folder = log_folder()
        self.path = None
        self._file = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.t0 = time.time()
        self.view = None
        self._view_since = None
        self._view_inactive = 0.
        self._inactive_since = None
        self._hovers = {}
        self._wheel = None
        self._timers = {}
        self._last_input = None
        self._input_widget = None
        self.window = None
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
            if self.window is not None:
                self.log_environment()
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
        record = {'t': round(time.time() - self.t0, 3), 'time': datetime.now().isoformat(timespec='milliseconds'),
                  'event': event, 'view': self.view}
        record.update({k: _jsonable(v) for k, v in data.items()})
        try:
            self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._file.flush()
        except (OSError, ValueError):
            self._file = None

    def log_error(self, where, exc):
        self.log('error', where=where, error=str(exc), traceback=traceback.format_exc()[-4000:])

    def log_crash(self, exc_type, exc, tb):
        self.log('crash', error=f"{exc_type.__name__}: {exc}",
                 traceback="".join(traceback.format_exception(exc_type, exc, tb))[-8000:])

    def log_environment(self, **extra):
        import creapy
        import PySide6
        screens = [{'w': s.size().width(), 'h': s.size().height(), 'dpr': s.devicePixelRatio()}
                   for s in QApplication.screens()]
        self.log('environment', creapy=creapy.__version__, python=platform.python_version(), qt=qVersion(),
                 pyside=PySide6.__version__, os=platform.platform(), machine=platform.machine(),
                 frozen=bool(getattr(sys, 'frozen', False)), locale=QLocale.system().name(), screens=screens, **extra)

    def watch(self, app, window):
        """Record the whole window: every click, hover, key, wheel, dialog, action and the time spent in each view."""
        global ACTIVE_LOG, _RECORDER
        ACTIVE_LOG = self
        self.window = window
        if _RECORDER is None:
            _RECORDER = EventRecorder(app)
            app.installEventFilter(_RECORDER)
            app.applicationStateChanged.connect(_on_app_state)
            heartbeat = QTimer(_RECORDER)
            heartbeat.setInterval(HEARTBEAT_S * 1000)
            heartbeat.timeout.connect(_heartbeat)
            heartbeat.start()
        wrap_dialogs()
        for action in window.findChildren(QAction):
            self.hook_action(action)

    def set_view(self, name):
        now = time.time()
        if self.view is not None and self._view_since is not None:
            inactive = self._view_inactive + (now - self._inactive_since if self._inactive_since else 0.)
            seconds = now - self._view_since
            self.log('view_dwell', seconds=round(seconds, 3), active_s=round(max(0., seconds - inactive), 3))
        self.view = name
        self._view_since = now
        self._view_inactive = 0.
        self.log('view')

    def on_app_state(self, state):
        active = state == Qt.ApplicationActive
        now = time.time()
        if active and self._inactive_since is not None:
            self._view_inactive += now - self._inactive_since
            self._inactive_since = None
        elif not active and self._inactive_since is None:
            self._inactive_since = now
        self.log('app_active', active=active)

    def hook_action(self, action):
        if action.property('creapyLogHooked'):
            return
        action.setProperty('creapyLogHooked', True)
        action.triggered.connect(lambda checked=False, a=action: self.log(
            'action', text=a.text().replace('&', ''), checked=a.isChecked() if a.isCheckable() else None,
            shortcut=a.shortcut().toString() or None))

    def hook_control(self, w):
        if w.property('creapyLogHooked'):
            return
        w.setProperty('creapyLogHooked', True)
        if isinstance(w, QComboBox):
            w.currentTextChanged.connect(lambda text: self._changed(w, text))
        elif isinstance(w, QAbstractSlider):
            w.valueChanged.connect(lambda value: self._changed(w, value, settle=True))
        elif isinstance(w, QAbstractSpinBox):
            w.editingFinished.connect(lambda: self._changed(w, w.text()))
        elif isinstance(w, QLineEdit):
            w.editingFinished.connect(lambda: self._changed(w, w.text()[:TEXT_LIMIT]))
        elif isinstance(w, QAbstractButton) and w.isCheckable():
            w.toggled.connect(lambda checked: self._changed(w, checked))
        elif type(w).__name__ == 'HalfDial' and hasattr(w, 'valueChanged'):
            w.valueChanged.connect(lambda value: self._changed(w, value, settle=True))

    def _changed(self, w, value, settle=False):
        if not self.user_touched(w):
            return
        if not settle:
            self.log('control', value=value, **describe(w))
            return
        key = id(w)
        timer = self._timers.get(key)
        if timer is None:
            timer = self._timers[key] = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda t=timer, w=w: self.log('control', value=t.property('pending'), **describe(w)))
        timer.setProperty('pending', value)
        timer.start(CHANGE_SETTLE_MS)

    def user_touched(self, w):
        """True when the last click, key or wheel landed on this control (or inside it), so the change is the user's."""
        if w.hasFocus():
            return True
        last = self._input_widget
        if last is None or time.time() - last[1] > 2.:
            return False
        target = last[0]
        while target is not None:
            if target is w:
                return True
            target = target.parent()
        return False

    def flush_wheel(self):
        if self._wheel is not None:
            pending, self._wheel = self._wheel, None
            self.log('wheel', steps=pending['steps'], ms=int(1000 * (pending['last'] - pending['first'])),
                     **pending['widget'])

    def export_zip(self, dest):
        """Copy every session log into one zip file for a bug report; returns the number of files."""
        if self._file:
            self._file.flush()
        names = sorted(f for f in os.listdir(self.folder) if f.endswith('.jsonl')) if os.path.isdir(self.folder) else []
        with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as zf:
            for name in names:
                zf.write(os.path.join(self.folder, name), name)
        self.log('logs_exported', n_files=len(names), path=os.path.basename(dest))
        return len(names)

    def close(self):
        global ACTIVE_LOG
        if ACTIVE_LOG is self:
            ACTIVE_LOG = None
        if self._file:
            self.flush_wheel()
            if self.view is not None:
                self.set_view(None)
            self.log('session_end', seconds=round(time.time() - self.t0, 1))
            self._file.close()
            self._file = None


def _on_app_state(state):
    if ACTIVE_LOG is not None:
        ACTIVE_LOG.on_app_state(state)


def _heartbeat():
    if ACTIVE_LOG is not None:
        ACTIVE_LOG.log('heartbeat', active=ACTIVE_LOG._inactive_since is None)


class EventRecorder(QObject):
    """One per application: forwards the watched events to the active session log."""

    def eventFilter(self, obj, event):
        kind = event.type()
        log = ACTIVE_LOG
        if kind not in WATCHED or log is None or not log.enabled or not isinstance(obj, QWidget):
            return False
        try:
            self.record(log, obj, event, kind)
        except Exception:  # noqa: BLE001
            pass
        return False

    @staticmethod
    def record(log, w, event, kind):
        if kind in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick, QEvent.KeyPress, QEvent.Wheel):
            stamp = (kind, event.timestamp(), event.key() if kind == QEvent.KeyPress else None)
            if log._last_input is not None and log._last_input[0] == stamp \
                    and time.time() - log._last_input[1] < 0.05:
                return   # the same event on its way up to the parent widgets
            log._last_input = (stamp, time.time())
            log._input_widget = (w, time.time())
        if kind != QEvent.Wheel:
            pending = log._wheel
            if pending is not None and time.time() - pending['last'] > WHEEL_GAP_S:
                log.flush_wheel()
        if kind in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick):
            log.log('click' if kind == QEvent.MouseButtonPress else 'double_click',
                    button=BUTTON_NAMES.get(event.button(), 'other'), **describe(w, event.position()))
        elif kind == QEvent.Enter:
            if hoverable(w):
                log._hovers[id(w)] = (time.time(), describe(w))
        elif kind == QEvent.Leave:
            started = log._hovers.pop(id(w), None)
            if started is not None:
                ms = int(1000 * (time.time() - started[0]))
                if ms >= HOVER_MIN_MS:
                    log.log('hover', ms=ms, **started[1])
        elif kind == QEvent.ToolTip:
            if w.toolTip():
                log.log('tooltip', **describe(w))
        elif kind == QEvent.KeyPress:
            if event.isAutoRepeat():
                return
            key = SPECIAL_KEYS.get(event.key())
            modifiers = event.modifiers()
            command = bool(modifiers & (Qt.ControlModifier | Qt.MetaModifier | Qt.AltModifier))
            if key is None and command and Qt.Key_A <= event.key() <= Qt.Key_Z:
                key = chr(event.key())
            if key is None and Qt.Key_F1 <= event.key() <= Qt.Key_F12:
                key = f"F{event.key() - Qt.Key_F1 + 1}"
            if key is not None:
                mods = [name for flag, name in [(Qt.ControlModifier, 'Ctrl'), (Qt.MetaModifier, 'Meta'),
                                                (Qt.AltModifier, 'Alt'), (Qt.ShiftModifier, 'Shift')] if modifiers & flag]
                log.log('key', key="+".join(mods + [key]), **describe(w))
        elif kind == QEvent.Wheel:
            steps = (event.angleDelta().y() or event.angleDelta().x()) / 120.
            desc = describe(w)
            pending = log._wheel
            now = time.time()
            if pending is not None and (pending['widget'] != desc or now - pending['last'] > WHEEL_GAP_S):
                log.flush_wheel()
                pending = None
            if pending is None:
                log._wheel = {'widget': desc, 'steps': 0., 'first': now, 'last': now}
            log._wheel['steps'] = round(log._wheel['steps'] + steps, 2)
            log._wheel['last'] = now
        elif kind == QEvent.Show:
            if w.isWindow():
                log.log('window_shown', window=type(w).__name__, title=w.windowTitle())
            elif isinstance(w, (QComboBox, QAbstractSlider, QAbstractSpinBox, QLineEdit, QAbstractButton)) \
                    or type(w).__name__ == 'HalfDial':
                log.hook_control(w)
        elif kind == QEvent.Hide:
            if w.isWindow():
                result = w.result() if isinstance(w, QDialog) else None
                log.log('window_hidden', window=type(w).__name__, title=w.windowTitle(), result=result)
        elif kind == QEvent.Resize:
            if w is log.window:
                timer = log._timers.get('resize')
                if timer is None:
                    timer = log._timers['resize'] = QTimer(log)
                    timer.setSingleShot(True)
                    timer.timeout.connect(lambda: log.log('window_resized', w=log.window.width(), h=log.window.height()))
                timer.start(1000)


def hoverable(w):
    return bool(w.toolTip()) or isinstance(w, (QAbstractButton, QComboBox, QAbstractSlider, QAbstractSpinBox, QTabBar)) \
        or type(w).__name__ in ('ProjectTile', 'StimulusThumbnail', 'HalfDial')


def describe(w, pos=None):
    """Which control: its class, object name, label and the named panel or window it sits in."""
    d = {'widget': type(w).__name__}
    parent = w.parent()
    if isinstance(parent, QAbstractItemView) and w.objectName() == 'qt_scrollarea_viewport':
        w = parent
        d['widget'] = type(w).__name__
        if pos is not None:
            index = w.indexAt(pos.toPoint())
            if index.isValid():
                d['item'] = shorten(index.data())
    elif isinstance(w, QHeaderView) and pos is not None:
        i = w.logicalIndexAt(pos.toPoint())
        if i >= 0 and w.model() is not None:
            d['item'] = shorten(w.model().headerData(i, w.orientation()))
    name = w.objectName()
    if name and not name.startswith('qt_'):
        d['name'] = name
    text = widget_text(w)
    if text:
        d['text'] = text
    context = context_of(w)
    if context:
        d['in'] = context
    return d


def widget_text(w):
    if isinstance(w, QLineEdit):
        return None
    if isinstance(w, QComboBox):
        return shorten(w.currentText())
    if isinstance(w, QTabBar):
        return shorten(w.tabText(w.currentIndex()))
    if isinstance(w, (QAbstractButton, QLabel)):
        return shorten(re.sub(r'<[^>]+>', '', w.text()))
    path = getattr(w, 'path', None)
    if isinstance(path, str):
        return os.path.basename(path)
    text = getattr(w, 'text', None)
    if callable(text):
        try:
            return shorten(text())
        except TypeError:
            return None
    return None


def context_of(w):
    parent = w.parent()
    hops = 0
    while parent is not None and hops < 15:
        if isinstance(parent, QWidget):
            if parent.accessibleName():
                return parent.accessibleName()
            name = parent.objectName()
            if name and not name.startswith('qt_') and name != 'heatmapToolbar':
                return name
            if parent.isWindow():
                return parent.windowTitle() or type(parent).__name__
        parent = parent.parent()
        hops += 1
    return None


def shorten(value):
    text = str(value).strip() if value is not None else ''
    return text[:TEXT_LIMIT] if text else None


def wrap_dialogs():
    """Message boxes and file dialogs report their title, text and answer to the active log."""
    for name in ['information', 'warning', 'critical', 'question']:
        _wrap(QMessageBox, name, 'message_box')
    for name in ['getOpenFileName', 'getOpenFileNames', 'getSaveFileName', 'getExistingDirectory']:
        _wrap(QFileDialog, name, 'file_dialog')


def _wrap(cls, name, kind):
    original = getattr(cls, name)
    if getattr(original, '_creapy_logged', False):
        return

    def wrapper(*args, **kwargs):
        result = original(*args, **kwargs)
        if ACTIVE_LOG is not None:
            if kind == 'message_box':
                ACTIVE_LOG.log(kind, kind=name, title=shorten(args[1] if len(args) > 1 else kwargs.get('title')),
                               text=shorten(args[2] if len(args) > 2 else kwargs.get('text')), answer=_answer(result))
            else:
                chosen = result[0] if isinstance(result, tuple) else result
                if isinstance(chosen, (list, tuple)):
                    chosen = [os.path.basename(c) for c in chosen]
                else:
                    chosen = os.path.basename(chosen) if chosen else None
                ACTIVE_LOG.log(kind, kind=name, title=shorten(args[1] if len(args) > 1 else kwargs.get('caption')),
                               chosen=chosen)
        return result

    wrapper._creapy_logged = True
    setattr(cls, name, staticmethod(wrapper))


def _answer(result):
    try:
        return QMessageBox.StandardButton(result).name if result is not None else None
    except (ValueError, TypeError):
        return str(result)


def _jsonable(value):
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        if hasattr(value, 'item'):
            return value.item()
        if isinstance(value, (list, tuple, set)):
            return [_jsonable(v) for v in value]
        if isinstance(value, dict):
            return {str(k): _jsonable(v) for k, v in value.items()}
        return str(value)
