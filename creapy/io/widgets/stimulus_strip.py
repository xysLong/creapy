# stimulus_strip.py

from PySide6.QtCore import Qt, Signal, QObject, QRunnable, QThreadPool
from PySide6.QtGui import QImage, QImageReader
from PySide6.QtWidgets import QScrollArea, QWidget, QHBoxLayout, QFrame

from creapy.io.widgets.stimulus_thumbnail import StimulusThumbnail

THUMBNAIL_SIZE = 72


class ThumbnailLoaderSignals(QObject):
    loaded = Signal(str, QImage)


class ThumbnailLoader(QRunnable):
    # Decodes one stimulus image at thumbnail resolution in a worker thread, so
    # a table with many large stimuli doesn't freeze the GUI at import.
    def __init__(self, path, size, signals):
        super().__init__()
        self.path = path
        self.size = size
        self.signals = signals

    def run(self):
        reader = QImageReader(self.path)
        full_size = reader.size()
        if full_size.isValid():
            reader.setScaledSize(full_size.scaled(self.size, self.size, Qt.KeepAspectRatio))
        image = reader.read()
        if not image.isNull():
            self.signals.loaded.emit(self.path, image)


class StimulusStrip(QScrollArea):
    # Horizontal row of stimulus thumbnails above the canvas; clicking one
    # switches the active stimulus.
    stimulus_selected = Signal(str)

    def __init__(self, paths, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        # The scroll area's default viewport is white: paint the strip in the
        # main window's dark background instead
        self.setStyleSheet("QScrollArea { background-color: #05060a; border: none; }"
                           "#StimulusStripContainer { background-color: #05060a; }")

        self.current_path = None
        self._thumbs = {}

        container = QWidget()
        container.setObjectName("StimulusStripContainer")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        for path in paths:
            thumb = StimulusThumbnail(path_to_stim=path, thumb_size=THUMBNAIL_SIZE)
            thumb.clicked.connect(self.select)
            layout.addWidget(thumb)
            self._thumbs[path] = thumb
        layout.addStretch()
        self.setWidget(container)

        self.setFixedHeight(container.sizeHint().height()
                            + self.horizontalScrollBar().sizeHint().height())

        # Kick off the background thumbnail decoding. The signals object is
        # kept alive by the loaders; a queued connection delivers each image on
        # the GUI thread, and Qt drops deliveries if the strip is gone.
        self._loader_signals = ThumbnailLoaderSignals()
        self._loader_signals.loaded.connect(self._on_thumbnail_loaded)
        for path in paths:
            QThreadPool.globalInstance().start(
                ThumbnailLoader(path, THUMBNAIL_SIZE, self._loader_signals))

    def _on_thumbnail_loaded(self, path, image):
        self._thumbs[path].set_image(image)

    def mark(self, path):
        # Update the highlight only (no signal): used to revert after a failed switch
        if self.current_path in self._thumbs:
            self._thumbs[self.current_path].set_selected(False)
        self.current_path = path
        self._thumbs[path].set_selected(True)
        self.ensureWidgetVisible(self._thumbs[path])

    def select(self, path):
        if path == self.current_path:
            return
        self.mark(path)
        self.stimulus_selected.emit(path)
