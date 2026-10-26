import creapy.io.widgets.utils as utils
import creapy.io.glossary as glossary
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox, QFrame


class StatisticsToolbar(QWidget):
    # Tables + one boxplot: per-participant descriptives, group comparison, AOI metrics
    AVAILABLE_DISPLAY = ["Participants (table)", "Group comparison (table)", "AOI metrics (table)",
                         "Boxplot by group"]

    def __init__(self, update_callback, parent=None):
        super().__init__(parent)
        self.update_callback = update_callback

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        top = QWidget(self)
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(12, 12, 12, 8)
        top_layout.setSpacing(8)

        title = QLabel("Statistics:")
        title.setProperty("boldTitle", True)
        top_layout.addWidget(title)

        self.display_selector = QComboBox()
        self.display_selector.addItems(self.AVAILABLE_DISPLAY)
        self.display_selector.currentIndexChanged.connect(self.update_callback)
        top_layout.addWidget(self.display_selector)

        top_layout.addWidget(QLabel("Measure (boxplot):"))
        self.measure_selector = QComboBox()
        self.measure_selector.currentIndexChanged.connect(self.update_callback)
        top_layout.addWidget(self.measure_selector)

        utils.add_hint(top_layout, "Durations are in the unit of your table (EyeLink: ms). Coefficient K > 0 means "
                                   "focal viewing (long fixations, short saccades), K &lt; 0 ambient viewing "
                                   "(Krejtz et al. 2016). The group comparison needs groups: assign them below.")

        line1 = QFrame(self)
        line1.setObjectName("sectionSeparator")
        line1.setFrameShape(QFrame.NoFrame)
        line1.setFixedHeight(1)

        middle = QWidget(self)
        middle_layout = QVBoxLayout(middle)
        middle_layout.setContentsMargins(12, 8, 12, 8)
        grouping_title = QLabel("Grouping:")
        grouping_title.setProperty("boldTitle", True)
        middle_layout.addWidget(grouping_title)
        self.grouping_label = QLabel("No groups assigned.")
        self.grouping_label.setWordWrap(True)
        middle_layout.addWidget(self.grouping_label)
        self.groups_btn = QPushButton("Assign Groups...")
        middle_layout.addWidget(self.groups_btn)

        line2 = QFrame(self)
        line2.setObjectName("sectionSeparator")
        line2.setFrameShape(QFrame.NoFrame)
        line2.setFixedHeight(1)

        bottom = QWidget(self)
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(12, 8, 12, 12)
        self.export_btn = QPushButton("Export Table…")
        bottom_layout.addWidget(self.export_btn)
        self.save_btn = QPushButton("Save as Image")
        bottom_layout.addWidget(self.save_btn)

        outer.addWidget(top)
        outer.addWidget(line1)
        outer.addWidget(middle)
        outer.addWidget(line2)
        outer.addWidget(bottom)
        outer.addStretch()
        utils.apply_tooltips(self, dict(glossary.COMMON_TIPS, **glossary.TOOLTIPS['stats']))

    def set_measures(self, measures):
        current = self.measure_selector.currentText()
        self.measure_selector.blockSignals(True)
        self.measure_selector.clear()
        self.measure_selector.addItems(list(measures))
        idx = self.measure_selector.findText(current)
        self.measure_selector.setCurrentIndex(idx if idx >= 0 else 0)
        self.measure_selector.blockSignals(False)

    def get_params(self):
        return {"display": self.display_selector.currentText(),
                "measure": self.measure_selector.currentText()}
