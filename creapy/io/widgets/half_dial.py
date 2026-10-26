import math
from PySide6.QtCore import Qt, QPointF, QSize, Signal, QRectF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor
from PySide6.QtWidgets import QWidget
import matplotlib.cm as cm
from matplotlib.colors import Normalize
from PySide6.QtGui import QPainterPath, QFontMetrics

class OrientationSelector(QWidget):
    valueChanged = Signal(int)   # emits angle in degrees [0..180]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 90  # start at middle
        self._hover = False
        self._pressed = False

        # match your QSlider handle colors
        self._color_base = QColor("#007aff")
        self._color_hover = QColor("#005bb5")
        self._color_pressed = QColor("#004080")

        # optional cyclic colormap (matplotlib ScalarMappable)
        self._scalar_mappable = None

        self.setMinimumSize(120, 70)
        self.setMouseTracking(True)

    def setCyclicColormap(self, cyclic_cmap):
        """
        cyclic_cmap: a matplotlib colormap, e.g. the result of __make_cyclic_colormap().
        Pass None to disable the colored dial.
        """
        if cyclic_cmap is None:
            self._scalar_mappable = None
        else:
            self._scalar_mappable = cm.ScalarMappable(
                norm=Normalize(vmin=0.0, vmax=180.0),
                cmap=cyclic_cmap,
            )
        self.update()

    def _paint_colored_dial(self, painter: QPainter, center: QPointF, radius: float):
        """
        Fill the semicircle with colors from the cyclic colormap.
        Color at angle ~self._value is 'warmest', opposite (~self._value+90) is 'coolest',
        using the same mapping: (angle - ooi + 90) % 180.
        """
        if self._scalar_mappable is None:
            return

        # bounding rect for the full circle
        rect = QRectF(
            center.x() - radius,
            center.y() - radius,
            2 * radius,
            2 * radius,
        )

        steps = 30  # 1° per wedge; increase for smoother, decrease for speed

        painter.save()
        painter.setPen(Qt.NoPen)

        step_deg = 180.0 / steps
        for i in range(steps):
            start_deg = i * step_deg
            end_deg = start_deg + step_deg
            mid_deg = (start_deg + end_deg) * 0.5

            # This is exactly np.mod(_angles - ooi + 90, 180)
            mapped = (mid_deg - float(self._value) + 90.0) % 180.0

            # map to RGBA from matplotlib
            r, g, b, a = self._scalar_mappable.to_rgba(mapped)
            color = QColor.fromRgbF(r, g, b, a)

            painter.setBrush(QBrush(color))
            # QPainter angles are in 1/16 degrees, 0° at 3 o'clock, CCW positive
            painter.drawPie(
                rect,
                int(start_deg * 16),
                int(step_deg * 16),
            )

        painter.restore()


    def sizeHint(self):
        return QSize(180, 90)

    def value(self):
        return self._value

    def setValue(self, v: int):
        v = max(0, min(180, int(v)))
        if v == self._value:
            return
        self._value = v
        self.valueChanged.emit(self._value)
        self.update()

    # --- helpers ------------------------------------------------------

    def _geometry(self):
        """Return (center QPointF, radius) of the semicircle."""
        w, h = self.width(), self.height()
        margin = 8
        center = QPointF(w / 2.0, h - margin)
        radius = min(w / 2.0 - margin, h - 2 * margin)
        return center, radius

    def _handle_center(self):
        center, radius = self._geometry()
        angle_rad = math.radians(float(self._value))
        handle_r = radius - 4
        hx = center.x() + handle_r * math.cos(angle_rad)
        hy = center.y() - handle_r * math.sin(angle_rad)
        return QPointF(hx, hy)

    def _is_on_handle(self, pos, tol=10):
        hc = self._handle_center()
        dx = pos.x() - hc.x()
        dy = pos.y() - hc.y()
        return dx * dx + dy * dy <= tol * tol

    # --- painting -----------------------------------------------------

    def paintEvent(self, event):
        center, radius = self._geometry()
        w, h = self.width(), self.height()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1) optional colored fill under the arc
        if self._scalar_mappable is not None:
            self._paint_colored_dial(painter, center, radius)
        else:
            # 2) arc (0..180 degrees along the top)
            rect = (
                center.x() - radius,
                center.y() - radius,
                2 * radius,
                2 * radius,
            )

            pen_arc = QPen(QColor("#888888"), 2)
            painter.setPen(pen_arc)
            painter.setBrush(Qt.NoBrush)
            painter.drawArc(
                int(rect[0]),
                int(rect[1]),
                int(rect[2]),
                int(rect[3]),
                0 * 16,
                180 * 16,
            )

        # 3) handle position
        handle_center = self._handle_center()

        # line from center to handle
        pen_line = QPen(QColor("#ffffff"), 2)
        painter.setPen(pen_line)
        painter.drawLine(center, handle_center)

        # 4) handle circle with hover/pressed color
        if self._pressed:
            color = self._color_pressed
        elif self._hover:
            color = self._color_hover
        else:
            color = self._color_base

        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(handle_center, 6, 6)

        text = f"{self._value}°"
        font = painter.font()
        metrics = QFontMetrics(font)

        text_width = metrics.horizontalAdvance(text)
        text_height = metrics.height()

        # baseline position for bottom-centered text
        x = (w - text_width) / 2.0
        y = h - metrics.descent()

        path = QPainterPath()
        path.addText(x, y, font, text)

        # outline
        painter.setPen(QPen(Qt.black, 5))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        # fill
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawPath(path)

    # --- mouse interaction --------------------------------------------

    def _update_from_pos(self, pos):
        center, _ = self._geometry()
        dx = pos.x() - center.x()
        dy = pos.y() - center.y()

        # angle from positive X axis, going CCW, top half only
        angle = math.degrees(math.atan2(-dy, dx))  # -dy because y axis is down
        angle = max(0.0, min(180.0, angle))
        self.setValue(int(round(angle)))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self._hover = True
            self._update_from_pos(event.position())
            self.update()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position()
        if event.buttons() & Qt.LeftButton:
            self._pressed = True
            self._update_from_pos(pos)
            self._hover = True
            self.update()
            event.accept()
        else:
            # pure hover
            hovered = self._is_on_handle(pos)
            if hovered != self._hover:
                self._hover = hovered
                self.update()
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = False
            # keep hover state depending on pointer position
            self._hover = self._is_on_handle(event.position())
            self.update()
            event.accept()
        else:
            super().mouseReleaseEvent(event)
