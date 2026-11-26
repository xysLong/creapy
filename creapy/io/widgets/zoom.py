from PySide6.QtCore import QObject, QEvent, Qt, Signal
from PySide6.QtGui import QInputDevice
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton

from creapy.io import glossary


class CanvasZoom(QObject):
    changed = Signal(float, str)   # zoom level (1 = whole figure), how ('wheel', 'pinch', 'pan', 'button', 'reset')

    MAX_LEVEL = 20.
    WHEEL_BASE = 1.25   # per wheel notch
    STEP = 1.5          # buttons and keys

    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = None
        self.homes = {}   # axes -> (xlim, ylim) of the figure as drawn
        self.drag = None
        self.drag_pan = True

    def attach(self, canvas, view=None):
        if self.canvas is not None:
            self.canvas.removeEventFilter(self)
        self.canvas = canvas
        self.drag = None
        self.homes = {ax: (ax.get_xlim(), ax.get_ylim()) for ax in canvas.figure.axes if self.zoomable(ax)}
        if view is not None and len(view) == len(self.homes):
            for ax, (fx0, fx1, fy0, fy1) in zip(self.homes, view):
                (hx0, hx1), (hy0, hy1) = self.homes[ax]
                ax.set_xlim(hx0 + fx0 * (hx1 - hx0), hx0 + fx1 * (hx1 - hx0))
                ax.set_ylim(hy0 + fy0 * (hy1 - hy0), hy0 + fy1 * (hy1 - hy0))
        canvas.installEventFilter(self)
        canvas.setMouseTracking(True)
        self.update_cursor()

    @staticmethod
    def zoomable(ax):
        return (ax.name == 'rectilinear' and ax.get_visible() and ax.get_navigate()
                and not hasattr(ax, '_colorbar') and ax.get_xscale() == 'linear' and ax.get_yscale() == 'linear')

    def available(self):
        return bool(self.homes)

    def level(self):
        levels = [abs(hx1 - hx0) / abs(ax.get_xlim()[1] - ax.get_xlim()[0]) for ax, ((hx0, hx1), _) in self.homes.items()]
        return float(max(levels, default=1.))

    def view(self):
        ls = []
        for ax, ((hx0, hx1), (hy0, hy1)) in self.homes.items():
            x0, x1 = ax.get_xlim()
            y0, y1 = ax.get_ylim()
            ls.append(((x0 - hx0) / (hx1 - hx0), (x1 - hx0) / (hx1 - hx0),
                       (y0 - hy0) / (hy1 - hy0), (y1 - hy0) / (hy1 - hy0)))
        return ls

    def axes_at(self, x, y):
        return [ax for ax in self.homes if ax.bbox.contains(x, y)]

    def zoom(self, factor, how, x=None, y=None):
        axes = list(self.homes) if x is None else self.axes_at(x, y)
        if not axes:
            return
        done_x, done_y = [], []
        for ax in axes:
            (hx0, hx1), (hy0, hy1) = self.homes[ax]
            x0, x1 = ax.get_xlim()
            y0, y1 = ax.get_ylim()
            level = min(max(abs(hx1 - hx0) / abs(x1 - x0) * factor, 1.), self.MAX_LEVEL)
            if x is None:
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            else:
                cx, cy = ax.transData.inverted().transform((x, y))
            if not any(ax.get_shared_x_axes().joined(ax, o) for o in done_x):
                ax.set_xlim(CanvasZoom.__window(x0, x1, cx, hx0, hx1, level))
                done_x.append(ax)
            if not any(ax.get_shared_y_axes().joined(ax, o) for o in done_y):
                ax.set_ylim(CanvasZoom.__window(y0, y1, cy, hy0, hy1, level))
                done_y.append(ax)
        self.redraw(how)

    def pan(self, axes, start_limits, inverses, dx, dy):
        for ax, ((x0, x1), (y0, y1)), inv in zip(axes, start_limits, inverses):
            (hx0, hx1), (hy0, hy1) = self.homes[ax]
            p0 = inv.transform((0, 0))
            p1 = inv.transform((dx, dy))
            ddx, ddy = p0 - p1
            ax.set_xlim(CanvasZoom.__clamp(x0 + ddx, x1 - x0, hx0, hx1))
            ax.set_ylim(CanvasZoom.__clamp(y0 + ddy, y1 - y0, hy0, hy1))
        self.redraw('pan')

    def reset(self):
        if self.level() <= 1.:
            return
        for ax, (xlim, ylim) in self.homes.items():
            ax.set_xlim(xlim)
            ax.set_ylim(ylim)
        self.redraw('reset')

    def redraw(self, how):
        self.canvas.draw_idle()
        self.update_cursor()
        self.changed.emit(self.level(), how)

    @staticmethod
    def __window(a0, a1, c, h0, h1, level):
        span = (h1 - h0) / level
        t = (c - a0) / (a1 - a0)
        return CanvasZoom.__clamp(c - t * span, span, h0, h1)

    @staticmethod
    def __clamp(n0, span, h0, h1):
        lo, hi = min(h0, h1), max(h0, h1)
        n1 = n0 + span
        shift = 0.
        if min(n0, n1) < lo:
            shift = lo - min(n0, n1)
        elif max(n0, n1) > hi:
            shift = hi - max(n0, n1)
        return n0 + shift, n1 + shift

    def eventFilter(self, obj, event):
        if obj is not self.canvas or not self.homes:
            return False
        kind = event.type()
        if kind == QEvent.Wheel:
            return self.on_wheel(event)
        if kind == QEvent.NativeGesture and event.gestureType() == Qt.ZoomNativeGesture:
            x, y = self.canvas.mouseEventCoords(event.position())
            self.zoom(1. + event.value(), 'pinch', x, y)
            return True
        if kind == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton and self.drag_pan:
            if self.level() > 1.:
                self.reset()
                return True
            return False
        if kind == QEvent.MouseButtonPress:
            return self.on_press(event)
        if kind == QEvent.MouseMove and self.drag is not None:
            pos = event.position()
            dpr = self.canvas.device_pixel_ratio
            dx = (pos.x() - self.drag['pos'].x()) * dpr
            dy = -(pos.y() - self.drag['pos'].y()) * dpr
            self.pan(self.drag['axes'], self.drag['limits'], self.drag['inverses'], dx, dy)
            return True
        if kind == QEvent.MouseButtonRelease and self.drag is not None:
            self.drag = None
            self.update_cursor()
            return True
        return False

    def on_wheel(self, event):
        x, y = self.canvas.mouseEventCoords(event.position())
        touchpad = (event.device() is not None and event.device().type() == QInputDevice.DeviceType.TouchPad) \
            or event.phase() != Qt.NoScrollPhase
        if touchpad and not event.modifiers() & Qt.ControlModifier:
            if self.level() <= 1.:
                return False
            axes = self.axes_at(x, y)
            delta = event.pixelDelta()
            dpr = self.canvas.device_pixel_ratio
            self.pan(axes, [(ax.get_xlim(), ax.get_ylim()) for ax in axes],
                     [ax.transData.inverted().frozen() for ax in axes], delta.x() * dpr, -delta.y() * dpr)
            return True
        steps = event.angleDelta().y() / 120 or event.pixelDelta().y() / 50
        if steps:
            self.zoom(self.WHEEL_BASE ** steps, 'wheel', x, y)
        return True

    def on_press(self, event):
        button = event.button()
        if button not in (Qt.LeftButton, Qt.MiddleButton) or self.level() <= 1.:
            return False
        if button == Qt.LeftButton and not self.drag_pan:
            return False
        x, y = self.canvas.mouseEventCoords(event.position())
        axes = self.axes_at(x, y)
        if not axes:
            return False
        self.drag = {'pos': event.position(), 'axes': axes,
                     'limits': [(ax.get_xlim(), ax.get_ylim()) for ax in axes],
                     'inverses': [ax.transData.inverted().frozen() for ax in axes]}
        self.canvas.setCursor(Qt.ClosedHandCursor)
        return True

    def update_cursor(self):
        if self.canvas is None or not self.drag_pan or self.drag is not None:
            return
        self.canvas.setCursor(Qt.OpenHandCursor if self.level() > 1. else Qt.ArrowCursor)


class ZoomBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ZoomBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        self.out_btn = QPushButton("−")
        self.level_btn = QPushButton("100 %")
        self.in_btn = QPushButton("+")
        for btn, name in ((self.out_btn, 'zoom_out'), (self.level_btn, 'zoom_reset'), (self.in_btn, 'zoom_in')):
            btn.setObjectName("ZoomButton")
            btn.setAccessibleName(name)
            btn.setToolTip(glossary.ZOOM_TIPS[name])
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setCursor(Qt.PointingHandCursor)
            layout.addWidget(btn)
        self.level_btn.setMinimumWidth(58)

    def set_level(self, level):
        self.level_btn.setText(f"{round(level * 100)} %")
        self.level_btn.setEnabled(level > 1.)
        self.out_btn.setEnabled(level > 1.)
        self.in_btn.setEnabled(level < CanvasZoom.MAX_LEVEL)
