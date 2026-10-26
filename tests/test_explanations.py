import os
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (QApplication, QSlider, QComboBox, QCheckBox, QPushButton, QListWidget, QLabel,  # noqa: E402
                               QMessageBox)

from creapy.io import glossary  # noqa: E402
from creapy.io import help as help_texts  # noqa: E402
from creapy.io import main as gui  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def silent_boxes(monkeypatch):
    # No modal dialogs offscreen (they would block forever): swallow them
    for name in ['information', 'critical', 'warning']:
        monkeypatch.setattr(QMessageBox, name, lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.Yes)


def test_texts_cover_every_view():
    assert list(glossary.VIEW_SUMMARY) == gui.MainWindow.VIEWS
    assert set(glossary.EXPLAINERS) == set(gui.MainWindow.VIEWS)
    for view, html in glossary.EXPLAINERS.items():
        assert "<h3>" in html and "What it shows" in html, view
    assert "View by view" in help_texts.ANALYSES and glossary.EXPLAINERS["Recurrence"] in help_texts.ANALYSES


def test_every_control_has_a_tooltip(qapp, silent_boxes):
    w = gui.MainWindow(synchronous=True)
    w.open_example()  # the workspace (toolbars, filter bar) exists only once a dataset is loaded
    missing = []
    for name, toolbar in zip(w.VIEWS, w.view_toolbars):
        controls = [c for kind in (QSlider, QComboBox, QCheckBox, QPushButton, QListWidget)
                    for c in toolbar.findChildren(kind)]
        for control in controls:
            if not control.toolTip():
                missing.append((name, control.objectName() or type(control).__name__,
                                getattr(control, 'text', lambda: '')()))
    assert missing == [], missing
    # slider titles carry the text too, value readouts do not
    tb = w.fix_heatmap_toolbar
    assert tb.bw_method_slider.title_label.toolTip() == tb.bw_method_slider.toolTip()
    assert "Smoothing bandwidth" in tb.bw_method_slider.toolTip() and tb.bw_method_label.toolTip() == ""
    # combos get the label placed before them
    labels = {lab.text(): lab for lab in tb.findChildren(QLabel)}
    assert labels["Contour Colormap:"].toolTip() == tb.color_selector.toolTip()
    # filter bar and view list
    assert w.filter_bar.participant_selector.toolTip() and w.filter_bar.range_label.toolTip() == ""
    assert all(w.left_toolbar.item(i).toolTip() for i in range(w.left_toolbar.count()))
    # the "K < 0" case must not be swallowed as an HTML tag
    assert "&lt; 0" not in glossary.TOOLTIPS['time_series']['curve_selector']
    assert "<p" in tb.bw_method_slider.toolTip()


def test_explainer_dock_and_captions(qapp, silent_boxes, tmp_path):
    w = gui.MainWindow(synchronous=True)
    w.open_example()
    w.show()  # isVisible() of the dock needs a shown window
    assert not w.explainer_dock.isVisible() and not w.info_btn.isChecked()
    w.info_btn.setChecked(True)
    assert w.explainer_dock.isVisible() and "Fixation Heatmap" in w.explainer_browser.toPlainText()
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Recurrence"))
    assert "RQA" in w.explainer_browser.toPlainText() and w.panel_title.text() == "Recurrence"
    w.explainer_dock.hide()
    assert not w.info_btn.isChecked()

    # captions: none on image views, one on the charts, and the same line lands in the saved file
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Fixation Heatmap"))
    w.view_runs[w.VIEWS.index("Fixation Heatmap")]()
    assert w.current_caption is None and not w.painter.caption.isVisible()
    i = w.VIEWS.index("Saccade Directions")
    w.left_toolbar.setCurrentRow(i)
    w.view_runs[i]()
    assert "direction sector" in w.current_caption and w.painter.caption.text() == w.current_caption
    fig = w.painter.current_fig
    n_texts = len(fig.texts)
    with w.caption_on_figure(fig, w.current_caption, w.current_axes_kind):
        assert len(fig.texts) == n_texts + 1
        fig.savefig(tmp_path / "rose.png", bbox_inches="tight")
    assert len(fig.texts) == n_texts and (tmp_path / "rose.png").stat().st_size > 1000

    # every chart display has a caption that mentions its jargon
    assert "s_loc" in glossary.figure_caption("Saccade Similarity", {'which': 's_loc', 'view': 'Similarity Matrix'})
    assert "MultiMatch" in glossary.figure_caption("Scanpath Comparison", {'which': 'mm_vector', 'view': 'Group Boxplot'})
    assert "Lomb" in glossary.figure_caption("Time Series", {'display': 'Periodogram', 'curve': 'Pupil Size'})
    assert "DET" in glossary.figure_caption("Recurrence", {'display': 'RQA table'})
    assert glossary.figure_caption("Fixation Heatmap", {}) is None
