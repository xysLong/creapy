import os
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np  # noqa: E402
from PySide6.QtCore import Qt, QPoint, QPointF, QEvent  # noqa: E402
from PySide6.QtGui import QWheelEvent, QMouseEvent, QNativeGestureEvent, QPointingDevice  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from creapy.io import main as gui  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, monkeypatch):
    for name in ['information', 'critical', 'warning']:
        monkeypatch.setattr(QMessageBox, name, lambda *a, **k: None)
    w = gui.MainWindow(synchronous=True)
    w.open_example()
    w.resize(1200, 800)
    w.show()
    qapp.processEvents()
    w.render_timer.stop()
    return w


def show_view(w, name):
    w.left_toolbar.setCurrentRow(w.VIEWS.index(name))
    w.render_timer.stop()
    w.view_runs[w.VIEWS.index(name)]()
    w.render_timer.stop()
    QApplication.processEvents()


def centre(canvas):
    return QPointF(canvas.width() / 2, canvas.height() / 2)


def wheel(canvas, steps, pos=None, phase=Qt.NoScrollPhase, pixel=QPoint(0, 0), modifiers=Qt.NoModifier):
    pos = pos or centre(canvas)
    event = QWheelEvent(pos, canvas.mapToGlobal(pos), pixel, QPoint(0, int(120 * steps)), Qt.NoButton, modifiers,
                        phase, False)
    QApplication.sendEvent(canvas, event)


def mouse(canvas, kind, pos, button=Qt.LeftButton):
    buttons = Qt.NoButton if kind == QEvent.MouseButtonRelease else button
    event = QMouseEvent(kind, pos, canvas.mapToGlobal(pos), button, buttons, Qt.NoModifier)
    QApplication.sendEvent(canvas, event)


def image_axes(w):
    return w.painter.current_fig.axes[0]


def test_wheel_zooms_at_the_pointer_and_stays_inside_the_figure(window):
    w = window
    show_view(w, "Fixation Heatmap")
    canvas, ax = w.painter.canvas, image_axes(w)
    home_x, home_y = ax.get_xlim(), ax.get_ylim()
    x, y = canvas.mouseEventCoords(centre(canvas))
    point = ax.transData.inverted().transform((x, y))
    wheel(canvas, 3)
    assert w.painter.zoom.level() == pytest.approx(1.25 ** 3)
    assert np.allclose(ax.transData.inverted().transform((x, y)), point)
    assert ax.get_ylim()[0] > ax.get_ylim()[1]
    wheel(canvas, 100)
    assert w.painter.zoom.level() == pytest.approx(w.painter.zoom.MAX_LEVEL)
    wheel(canvas, -200)
    assert w.painter.zoom.level() == pytest.approx(1.)
    assert np.allclose(ax.get_xlim(), home_x) and np.allclose(ax.get_ylim(), home_y)


def test_drag_pans_only_while_zoomed_and_double_click_resets(window):
    w = window
    show_view(w, "Fixation Heatmap")
    canvas, ax = w.painter.canvas, image_axes(w)
    home_x = ax.get_xlim()
    p0 = centre(canvas)
    mouse(canvas, QEvent.MouseButtonPress, p0)
    assert w.painter.zoom.drag is None
    mouse(canvas, QEvent.MouseButtonRelease, p0)
    wheel(canvas, 4)
    before = ax.get_xlim()
    mouse(canvas, QEvent.MouseButtonPress, p0)
    mouse(canvas, QEvent.MouseMove, p0 + QPointF(40, 0))
    mouse(canvas, QEvent.MouseButtonRelease, p0 + QPointF(40, 0))
    assert ax.get_xlim()[0] < before[0]
    mouse(canvas, QEvent.MouseMove, p0)
    for _ in range(3):
        mouse(canvas, QEvent.MouseButtonPress, p0)
        mouse(canvas, QEvent.MouseMove, p0 + QPointF(5000, 0))
        mouse(canvas, QEvent.MouseButtonRelease, p0 + QPointF(5000, 0))
    assert min(ax.get_xlim()) == pytest.approx(min(home_x))
    event = QMouseEvent(QEvent.MouseButtonDblClick, p0, canvas.mapToGlobal(p0), Qt.LeftButton, Qt.LeftButton,
                        Qt.NoModifier)
    QApplication.sendEvent(canvas, event)
    assert w.painter.zoom.level() == pytest.approx(1.)


def test_trackpad_scroll_pans_and_pinch_zooms(window):
    w = window
    show_view(w, "Fixation Heatmap")
    canvas, ax = w.painter.canvas, image_axes(w)
    wheel(canvas, 0, phase=Qt.ScrollUpdate, pixel=QPoint(0, 30))
    assert w.painter.zoom.level() == pytest.approx(1.)
    pos = centre(canvas)
    device = QPointingDevice.primaryPointingDevice()
    event = QNativeGestureEvent(Qt.ZoomNativeGesture, device, 2, pos, pos, canvas.mapToGlobal(pos), 0.5,
                                QPointF(0, 0))
    QApplication.sendEvent(canvas, event)
    assert w.painter.zoom.level() == pytest.approx(1.5)
    before = ax.get_xlim()
    wheel(canvas, 0, phase=Qt.ScrollUpdate, pixel=QPoint(30, 0))
    assert ax.get_xlim()[0] < before[0]
    assert w.painter.zoom.level() == pytest.approx(1.5)


def test_zoom_survives_a_rerender_but_not_a_stimulus_change(window):
    w = window
    show_view(w, "Fixation Heatmap")
    wheel(w.painter.canvas, 3)
    limits = image_axes(w).get_xlim()
    w.view_runs[w.VIEWS.index("Fixation Heatmap")]()
    w.render_timer.stop()
    QApplication.processEvents()
    assert np.allclose(image_axes(w).get_xlim(), limits)
    assert w.painter.zoom_bar.isVisible()
    show_view(w, "Fixation Scanpath")
    assert w.painter.zoom.level() == pytest.approx(1.)
    wheel(w.painter.canvas, 3)
    other = [p for p in w.stim_dfs if p != w.current_path][0]
    w.on_stimulus_selected(other)
    w.render_timer.stop()
    w.view_runs[w.VIEWS.index("Fixation Scanpath")]()
    QApplication.processEvents()
    assert w.painter.zoom.level() == pytest.approx(1.)


def test_buttons_menu_and_log(window):
    w = window
    show_view(w, "Fixation Heatmap")
    bar = w.painter.zoom_bar
    bar.in_btn.click()
    assert w.painter.zoom.level() == pytest.approx(1.5)
    assert bar.level_btn.text() == "150 %"
    w.zoom_in_action.trigger()
    assert w.painter.zoom.level() == pytest.approx(2.25)
    w.zoom_out_action.trigger()
    w.zoom_reset_action.trigger()
    assert w.painter.zoom.level() == pytest.approx(1.) and not bar.level_btn.isEnabled()
    records = []
    w.log.log = lambda event, **data: records.append((event, data))
    w.log_zoom()
    assert records and records[0][0] == 'zoom' and records[0][1]['level'] == 1.0


def test_polar_and_colorbar_axes_are_left_alone(window):
    w = window
    show_view(w, "Saccade Directions")
    assert not w.painter.zoom.available() and not w.painter.zoom_bar.isVisible()
    w.show_notice("Nothing here")
    assert not w.painter.zoom.available()
    from matplotlib.figure import Figure
    fig = Figure()
    ax = fig.add_subplot()
    fig.colorbar(ax.imshow(np.eye(3)), ax=ax)
    w.painter.draw_figure(fig)
    assert list(w.painter.zoom.homes) == [ax]


def test_drawing_an_area_keeps_its_clicks(window):
    w = window
    show_view(w, "Areas of Interest")
    assert w.drawing is not None and not w.painter.zoom.drag_pan
    w.cancel_drawing()
    w.connect_drawing(image_axes(w), 'Draw polygon')
    assert not w.painter.zoom.drag_pan
    canvas = w.painter.canvas
    wheel(canvas, 3)
    p0 = centre(canvas)
    mouse(canvas, QEvent.MouseButtonPress, p0)
    mouse(canvas, QEvent.MouseButtonRelease, p0)
    assert w.painter.zoom.drag is None and len(w.drawing['vertices']) == 1
    w.cancel_drawing()
    assert w.painter.zoom.drag_pan
