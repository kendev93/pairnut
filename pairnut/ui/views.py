"""PySide6 main window and widgets."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from ..database import repositories
from ..domain.models import DefectLevel, SerialMode
from ..services.matching import get_candidates_for_variety
from ..services.serials import next_serial_no


APP_STYLESHEET = """
QMainWindow {
    background: #f5efe8;
}
QWidget {
    color: #241a11;
    font-size: 14px;
}
QMenuBar {
    background: transparent;
    border: none;
}
QMenuBar::item {
    background: transparent;
    padding: 6px 10px;
    border-radius: 8px;
}
QMenuBar::item:selected {
    background: #eadfce;
}
QStatusBar {
    background: #f0e6da;
    color: #6f5a4a;
    border-top: 1px solid #e0d1bd;
}
QLabel[role="eyebrow"] {
    color: #8a6d54;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
QLabel[role="headline"] {
    font-size: 32px;
    font-weight: 700;
    color: #2f2015;
}
QLabel[role="subtle"] {
    color: #7a6554;
}
QLabel[role="metricValue"] {
    font-size: 18px;
    font-weight: 700;
    color: #2f2015;
}
QLabel[role="metricLabel"] {
    color: #7a6554;
    font-size: 12px;
}
QFrame[card="true"] {
    background: #fffdf9;
    border: 1px solid #e7dac8;
    border-radius: 20px;
}
QFrame[candidate="true"] {
    background: #fcf8f2;
    border: 1px solid #eadcca;
    border-radius: 16px;
}
QPushButton {
    background: #f0e6da;
    border: 1px solid #deceb9;
    border-radius: 12px;
    padding: 10px 16px;
    font-weight: 600;
}
QPushButton[tableAction="true"] {
    min-width: 58px;
    min-height: 28px;
    padding: 4px 10px;
    font-size: 12px;
    border-radius: 10px;
}
QPushButton:hover {
    background: #e7d7c3;
}
QPushButton:pressed {
    background: #dac7b0;
}
QPushButton[variant="primary"] {
    background: #bc7b35;
    color: white;
    border: none;
}
QPushButton[variant="primary"]:hover {
    background: #a96d2f;
}
QPushButton[variant="danger"] {
    background: #fff4f0;
    color: #b34b34;
    border: 1px solid #efc4b8;
}
QLineEdit, QComboBox, QDoubleSpinBox, QTextEdit {
    background: white;
    border: 1px solid #ddcfbd;
    border-radius: 12px;
    padding: 10px 12px;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {
    border: 1px solid #bc7b35;
}
QComboBox {
    padding-right: 40px;
}
QComboBox::drop-down {
    width: 34px;
    border: none;
    border-left: 1px solid #ddcfbd;
    background: #f4ebde;
    border-top-right-radius: 12px;
    border-bottom-right-radius: 12px;
}
QComboBox::drop-down:hover {
    background: #eadcca;
}
QComboBox QAbstractItemView {
    background: #fffdf9;
    border: 1px solid #ddcfbd;
    border-radius: 12px;
    outline: none;
    padding: 6px;
    selection-background-color: #f0e6da;
    selection-color: #2f2015;
}
QWidget[comboField="true"] {
    background: #fff6ea;
    border: 1px solid #d8b990;
    border-radius: 12px;
}
QComboBox[comboVariant="embedded"] {
    border: none;
    background: #fff6ea;
    padding: 10px 12px;
    color: #2f2015;
    font-weight: 600;
}
QComboBox[comboVariant="embedded"]:focus {
    border: none;
}
QComboBox[comboVariant="embedded"]::drop-down {
    width: 0px;
    border: none;
    background: transparent;
}
QToolButton[stepperRole="button"] {
    min-width: 28px;
    max-width: 28px;
    min-height: 22px;
    max-height: 22px;
    padding: 0;
    border: none;
    border-left: 1px solid #ddcfbd;
    background: #f4ebde;
    color: #6d5746;
    font-size: 13px;
    font-weight: 700;
}
QToolButton[stepperDirection="up"] {
    border-top-right-radius: 12px;
    border-bottom: 1px solid #e7dac8;
}
QToolButton[stepperDirection="down"] {
    border-bottom-right-radius: 12px;
}
QToolButton[stepperRole="button"]:hover {
    background: #eadcca;
}
QTableWidget {
    background: #fffdf9;
    border: 1px solid #e6d8c8;
    border-radius: 16px;
    gridline-color: #eee2d3;
    alternate-background-color: #faf5ee;
}
QHeaderView::section {
    background: #f5ede1;
    color: #6d5746;
    padding: 12px 10px;
    border: none;
    border-bottom: 1px solid #e6d8c8;
    font-weight: 700;
}
QTableWidget::item {
    padding: 10px;
}
QTableWidget::item:selected {
    background: #eadcca;
    color: #241a11;
}
QTableWidget::item:selected:active {
    background: #eadcca;
    color: #241a11;
}
QTableWidget::item:selected:!active {
    background: #f0e6da;
    color: #241a11;
}
QScrollArea {
    background: #fffdf9;
    border: none;
}
QScrollArea QWidget {
    background: #fffdf9;
}
QListWidget[nav="true"] {
    background: transparent;
    border: none;
    outline: none;
}
QListWidget[nav="true"]::item {
    padding: 14px 16px;
    margin: 4px 0;
    border-radius: 14px;
    color: #644e3c;
}
QListWidget[nav="true"]::item:selected {
    background: #fff8f0;
    color: #2f2015;
    font-weight: 700;
}
QGroupBox {
    border: 1px solid #e6d8c8;
    border-radius: 16px;
    margin-top: 16px;
    font-weight: 700;
    background: #fffdf9;
}
QGroupBox:title {
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 6px;
    color: #4d3828;
}
"""


def create_card() -> QFrame:
    frame = QFrame()
    frame.setProperty("card", True)
    return frame


def create_candidate_card() -> QFrame:
    frame = QFrame()
    frame.setProperty("candidate", True)
    return frame


def create_metric(label: str, value: str) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    value_label = QLabel(value)
    value_label.setProperty("role", "metricValue")
    title_label = QLabel(label)
    title_label.setProperty("role", "metricLabel")
    layout.addWidget(value_label)
    layout.addWidget(title_label)
    return widget


def create_chip(text: str, background: str = "#f2e7d7", foreground: str = "#6d5746") -> QLabel:
    chip = QLabel(text)
    chip.setAlignment(Qt.AlignCenter)
    chip.setStyleSheet(
        f"background: {background}; color: {foreground}; border-radius: 11px; padding: 6px 12px; font-weight: 600;"
    )
    return chip


@dataclass(slots=True)
class VarietyFormData:
    name: str
    code_prefix: str
    tolerance_mm: float


@dataclass(slots=True)
class WalnutFormData:
    variety_id: int
    serial_mode: str
    serial_no: str
    edge_mm: float
    belly_mm: float
    height_mm: float
    weight_g: float
    defect_level: str
    notes: str | None


class StepperSpinBox(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.spin = QDoubleSpinBox()
        self.spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin.setFrame(False)
        self.spin.setStyleSheet("QDoubleSpinBox { border: none; background: transparent; padding: 0 12px; }")

        self.up_button = QToolButton()
        self.up_button.setText("+")
        self.up_button.setProperty("stepperRole", "button")
        self.up_button.setProperty("stepperDirection", "up")
        self.down_button = QToolButton()
        self.down_button.setText("−")
        self.down_button.setProperty("stepperRole", "button")
        self.down_button.setProperty("stepperDirection", "down")

        self.up_button.clicked.connect(self.spin.stepUp)
        self.down_button.clicked.connect(self.spin.stepDown)

        buttons = QWidget()
        buttons_layout = QVBoxLayout(buttons)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(0)
        buttons_layout.addWidget(self.up_button)
        buttons_layout.addWidget(self.down_button)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.spin)
        layout.addWidget(buttons)

        self.setStyleSheet("StepperSpinBox { background: white; border: 1px solid #ddcfbd; border-radius: 12px; }")
        self.setFocusProxy(self.spin)

    def setRange(self, minimum: float, maximum: float) -> None:
        self.spin.setRange(minimum, maximum)

    def setDecimals(self, decimals: int) -> None:
        self.spin.setDecimals(decimals)

    def setValue(self, value: float) -> None:
        self.spin.setValue(value)

    def value(self) -> float:
        return float(self.spin.value())

    def setSingleStep(self, step: float) -> None:
        self.spin.setSingleStep(step)


class ComboField(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("comboField", True)

        self.combo = QComboBox()
        self.combo.setProperty("comboVariant", "embedded")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.combo)

        self.setFocusProxy(self.combo)

    def setMinimumWidth(self, width: int) -> None:  # type: ignore[override]
        super().setMinimumWidth(width)
        self.combo.setMinimumWidth(width)


class VarietyDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, variety: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("编辑品种" if variety else "新增品种")
        self.resize(420, 220)

        self.name_edit = QLineEdit(variety["name"] if variety else "")
        self.prefix_edit = QLineEdit(variety["code_prefix"] if variety else "")
        self.tolerance_spin = StepperSpinBox()
        self.tolerance_spin.setRange(0.1, 10.0)
        self.tolerance_spin.setDecimals(2)
        self.tolerance_spin.setValue(float(variety["tolerance_mm"]) if variety else 1.0)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("品种名称", self.name_edit)
        form.addRow("编号前缀", self.prefix_edit)
        form.addRow("统一偏差 (mm)", self.tolerance_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_button = buttons.button(QDialogButtonBox.Ok)
        ok_button.setText("保存")
        ok_button.setProperty("variant", "primary")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        body = create_card()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 20, 20, 20)
        body_layout.addLayout(form)

        layout = QVBoxLayout(self)
        layout.addWidget(body)
        layout.addWidget(buttons)

    def data(self) -> VarietyFormData:
        return VarietyFormData(
            name=self.name_edit.text().strip(),
            code_prefix=self.prefix_edit.text().strip(),
            tolerance_mm=float(self.tolerance_spin.value()),
        )


class WalnutDialog(QDialog):
    def __init__(self, parent: QWidget | None, variety_id: int, walnut: dict | None = None):
        super().__init__(parent)
        self.variety_id = variety_id
        self.walnut = walnut
        self.setWindowTitle("编辑核桃" if walnut else "新增核桃")
        self.resize(520, 420)

        self.serial_mode = QComboBox()
        self.serial_mode.addItem("自动生成", SerialMode.AUTO.value)
        self.serial_mode.addItem("手动输入", SerialMode.MANUAL.value)

        self.serial_no_edit = QLineEdit()
        self.edge_spin = self._create_measurement_spinbox()
        self.belly_spin = self._create_measurement_spinbox()
        self.height_spin = self._create_measurement_spinbox()
        self.weight_spin = self._create_measurement_spinbox(maximum=500.0)

        self.defect_combo = QComboBox()
        self.defect_combo.addItem("无", DefectLevel.NONE.value)
        self.defect_combo.addItem("轻", DefectLevel.LIGHT.value)
        self.defect_combo.addItem("中", DefectLevel.MEDIUM.value)
        self.defect_combo.addItem("重", DefectLevel.HEAVY.value)

        self.notes_edit = QTextEdit()
        self.notes_edit.setFixedHeight(96)

        self.serial_mode.currentIndexChanged.connect(self._refresh_serial_field)

        if walnut:
            self._load_walnut()
        else:
            self.serial_mode.setCurrentIndex(0)
            self._refresh_serial_field()

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.addRow("编号方式", self.serial_mode)
        form.addRow("编号", self.serial_no_edit)
        form.addRow("边 (mm)", self.edge_spin)
        form.addRow("肚 (mm)", self.belly_spin)
        form.addRow("高 (mm)", self.height_spin)
        form.addRow("克重 (g)", self.weight_spin)
        form.addRow("瑕疵", self.defect_combo)
        form.addRow("备注", self.notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_button = buttons.button(QDialogButtonBox.Ok)
        ok_button.setText("保存")
        ok_button.setProperty("variant", "primary")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        body = create_card()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 20, 20, 20)
        body_layout.addLayout(form)

        layout = QVBoxLayout(self)
        layout.addWidget(body)
        layout.addWidget(buttons)

    def _create_measurement_spinbox(self, maximum: float = 100.0) -> StepperSpinBox:
        spin = StepperSpinBox()
        spin.setRange(0.01, maximum)
        spin.setDecimals(2)
        spin.setSingleStep(0.1)
        return spin

    def _load_walnut(self) -> None:
        mode_index = 0 if self.walnut["serial_mode"] == SerialMode.AUTO.value else 1
        self.serial_mode.setCurrentIndex(mode_index)
        self.serial_no_edit.setText(self.walnut["serial_no"])
        self.edge_spin.setValue(float(self.walnut["edge_mm"]))
        self.belly_spin.setValue(float(self.walnut["belly_mm"]))
        self.height_spin.setValue(float(self.walnut["height_mm"]))
        self.weight_spin.setValue(float(self.walnut["weight_g"]))
        self.defect_combo.setCurrentIndex(max(0, self.defect_combo.findData(self.walnut["defect_level"])))
        self.notes_edit.setPlainText(self.walnut["notes"] or "")
        self.serial_no_edit.setReadOnly(self.walnut["serial_mode"] == SerialMode.AUTO.value)

    def _refresh_serial_field(self) -> None:
        serial_mode = self.serial_mode.currentData()
        is_manual = serial_mode == SerialMode.MANUAL.value
        self.serial_no_edit.setReadOnly(not is_manual)
        if is_manual:
            if self.walnut and self.walnut["serial_mode"] == SerialMode.MANUAL.value:
                self.serial_no_edit.setText(self.walnut["serial_no"])
            elif not self.walnut:
                self.serial_no_edit.clear()
        else:
            if self.walnut and self.walnut["serial_mode"] == SerialMode.AUTO.value:
                self.serial_no_edit.setText(self.walnut["serial_no"])
            elif not self.walnut:
                self.serial_no_edit.setText(next_serial_no(self.variety_id))

    def data(self) -> WalnutFormData:
        serial_mode = self.serial_mode.currentData()
        if serial_mode == SerialMode.MANUAL.value:
            serial_no = self.serial_no_edit.text().strip()
        elif self.walnut and self.walnut["serial_mode"] == SerialMode.AUTO.value:
            serial_no = self.walnut["serial_no"]
        else:
            serial_no = next_serial_no(self.variety_id)
        return WalnutFormData(
            variety_id=self.variety_id,
            serial_mode=serial_mode,
            serial_no=serial_no,
            edge_mm=float(self.edge_spin.value()),
            belly_mm=float(self.belly_spin.value()),
            height_mm=float(self.height_spin.value()),
            weight_g=float(self.weight_spin.value()),
            defect_level=self.defect_combo.currentData(),
            notes=self.notes_edit.toPlainText().strip() or None,
        )


class VarietyTab(QWidget):
    def __init__(self, window: "PairNutMainWindow"):
        super().__init__()
        self.window = window
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["品种", "前缀", "偏差(mm)"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._sync_action_state)

        hero = create_card()
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 20, 24, 20)
        eyebrow = QLabel("Varieties")
        eyebrow.setProperty("role", "eyebrow")
        title = QLabel("按品种管理规则")
        title.setProperty("role", "headline")
        subtitle = QLabel("每个品种维护自己的编号前缀和统一偏差值，后续核桃录入和配对都基于这里。")
        subtitle.setProperty("role", "subtle")
        self.add_button = QPushButton("新增品种")
        self.add_button.setProperty("variant", "primary")
        self.add_button.clicked.connect(self.create_variety)
        self.use_button = QPushButton("设为当前品种")
        self.use_button.clicked.connect(self.use_selected_variety)
        self.edit_button = QPushButton("编辑")
        self.edit_button.clicked.connect(self.edit_selected_variety)
        self.delete_button = QPushButton("删除")
        self.delete_button.setProperty("variant", "danger")
        self.delete_button.clicked.connect(self.delete_selected_variety)
        action_row = QHBoxLayout()
        action_row.addWidget(self.add_button)
        action_row.addWidget(self.use_button)
        action_row.addWidget(self.edit_button)
        action_row.addWidget(self.delete_button)
        action_row.addStretch(1)
        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        hero_layout.addLayout(action_row)

        table_card = create_card()
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(18, 18, 18, 18)
        table_layout.addWidget(self.table)

        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.addWidget(hero)
        layout.addWidget(table_card)
        self._sync_action_state()

    def refresh(self) -> None:
        varieties = repositories.list_varieties()
        self.table.setRowCount(len(varieties))
        for row, variety in enumerate(varieties):
            self.table.setItem(row, 0, QTableWidgetItem(variety["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(variety["code_prefix"]))
            self.table.setItem(row, 2, QTableWidgetItem(f'{variety["tolerance_mm"]:.2f}'))
        self.table.resizeRowsToContents()
        self._restore_selected_variety()
        self._sync_action_state()

    def _selected_variety_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        name_item = self.table.item(row, 0)
        prefix_item = self.table.item(row, 1)
        if name_item is None or prefix_item is None:
            return None
        for variety in repositories.list_varieties():
            if variety["name"] == name_item.text() and variety["code_prefix"] == prefix_item.text():
                return int(variety["id"])
        return None

    def _restore_selected_variety(self) -> None:
        current_id = self.window.selected_variety_id
        if current_id is None:
            if self.table.rowCount():
                self.table.selectRow(0)
            return
        varieties = repositories.list_varieties()
        for row, variety in enumerate(varieties):
            if variety["id"] == current_id:
                self.table.selectRow(row)
                break

    def _sync_action_state(self) -> None:
        has_selection = self._selected_variety_id() is not None
        self.use_button.setEnabled(has_selection)
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def use_selected_variety(self) -> None:
        variety_id = self._selected_variety_id()
        if variety_id is not None:
            self.window.set_selected_variety(variety_id)

    def edit_selected_variety(self) -> None:
        variety_id = self._selected_variety_id()
        if variety_id is not None:
            self.edit_variety(variety_id)

    def delete_selected_variety(self) -> None:
        variety_id = self._selected_variety_id()
        if variety_id is not None:
            self.delete_variety(variety_id)

    def create_variety(self) -> None:
        dialog = VarietyDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            data = dialog.data()
            repositories.create_variety(data.name, data.code_prefix, data.tolerance_mm)
            self.window.show_message("品种已创建")
            self.window.refresh_all()
        except Exception as exc:
            self.window.show_error(f"创建品种失败: {exc}")

    def edit_variety(self, variety_id: int) -> None:
        variety = repositories.get_variety(variety_id)
        if not variety:
            return
        dialog = VarietyDialog(self, variety=variety)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            data = dialog.data()
            repositories.update_variety(variety_id, data.name, data.code_prefix, data.tolerance_mm)
            self.window.show_message("品种已更新")
            self.window.refresh_all()
        except Exception as exc:
            self.window.show_error(f"更新品种失败: {exc}")

    def delete_variety(self, variety_id: int) -> None:
        if QMessageBox.question(self, "删除品种", "删除品种会同时删除该品种下的核桃数据，继续吗？") != QMessageBox.Yes:
            return
        try:
            repositories.delete_variety(variety_id)
            self.window.show_message("品种已删除")
            self.window.refresh_all()
        except Exception as exc:
            self.window.show_error(f"删除品种失败: {exc}")


class VarietyScopedWidget(QWidget):
    def __init__(self, window: "PairNutMainWindow"):
        super().__init__()
        self.window = window
        self.variety_combo = self._create_variety_combo()

    def _create_variety_combo(self) -> QWidget:
        field = ComboField()
        field.setMinimumWidth(220)
        self.combo_box = field.combo
        self.combo_box.currentIndexChanged.connect(self._handle_variety_change)
        return field

    def refresh_variety_combo(self) -> None:
        current_id = self.window.selected_variety_id
        self.combo_box.blockSignals(True)
        self.combo_box.clear()
        for variety in repositories.list_varieties():
            self.combo_box.addItem(variety["name"], variety["id"])
        if self.combo_box.count():
            index = self.combo_box.findData(current_id)
            if index < 0:
                index = 0
            self.combo_box.setCurrentIndex(index)
        self.combo_box.blockSignals(False)

    def _handle_variety_change(self, index: int) -> None:
        if index >= 0:
            self.window.set_selected_variety(int(self.combo_box.currentData()))


class WalnutTab(VarietyScopedWidget):
    def __init__(self, window: "PairNutMainWindow"):
        super().__init__(window)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["编号", "边", "肚", "高", "克重", "瑕疵", "状态"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._sync_action_state)

        hero = create_card()
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 20, 24, 20)
        eyebrow = QLabel("Walnuts")
        eyebrow.setProperty("role", "eyebrow")
        title = QLabel("录入与维护核桃数据")
        title.setProperty("role", "headline")
        subtitle = QLabel("按品种录入核桃的边、肚、高、克重和瑕疵情况，自动编号与手动编号都支持。")
        subtitle.setProperty("role", "subtle")
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("当前品种"))
        toolbar.addWidget(self.variety_combo)
        toolbar.addStretch(1)
        self.add_button = QPushButton("新增核桃")
        self.add_button.setProperty("variant", "primary")
        self.add_button.clicked.connect(self.create_walnut)
        self.edit_button = QPushButton("编辑选中")
        self.edit_button.clicked.connect(self.edit_selected_walnut)
        self.delete_button = QPushButton("删除选中")
        self.delete_button.setProperty("variant", "danger")
        self.delete_button.clicked.connect(self.delete_selected_walnut)
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(self.delete_button)
        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        hero_layout.addLayout(toolbar)

        table_card = create_card()
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(18, 18, 18, 18)
        table_layout.addWidget(self.table)

        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.addWidget(hero)
        layout.addWidget(table_card)
        self._sync_action_state()

    def refresh(self) -> None:
        self.refresh_variety_combo()
        variety_id = self.window.selected_variety_id
        walnuts = repositories.list_walnuts(variety_id=variety_id, include_locked=True) if variety_id else []
        self.table.setRowCount(len(walnuts))
        for row, walnut in enumerate(walnuts):
            values = [
                walnut["serial_no"],
                f'{walnut["edge_mm"]:.2f}',
                f'{walnut["belly_mm"]:.2f}',
                f'{walnut["height_mm"]:.2f}',
                f'{walnut["weight_g"]:.2f}',
                walnut["defect_level"],
                "已锁定" if walnut["is_locked"] else "未锁定",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                if column == 0:
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                self.table.setItem(row, column, item)
        self.table.resizeRowsToContents()
        self._restore_selected_walnut()
        self._sync_action_state()

    def _selected_walnut_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        serial_item = self.table.item(row, 0)
        if serial_item is None:
            return None
        walnut = repositories.get_walnut_by_serial(serial_item.text())
        return int(walnut["id"]) if walnut else None

    def _restore_selected_walnut(self) -> None:
        row_to_select = 0 if self.table.rowCount() else -1
        self.table.clearSelection()
        if row_to_select >= 0:
            self.table.selectRow(row_to_select)

    def _sync_action_state(self) -> None:
        has_selection = self._selected_walnut_id() is not None
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def edit_selected_walnut(self) -> None:
        walnut_id = self._selected_walnut_id()
        if walnut_id is not None:
            self.edit_walnut(walnut_id)

    def delete_selected_walnut(self) -> None:
        walnut_id = self._selected_walnut_id()
        if walnut_id is not None:
            self.delete_walnut(walnut_id)

    def create_walnut(self) -> None:
        variety_id = self.window.selected_variety_id
        if not variety_id:
            self.window.show_error("请先创建并选中一个品种。")
            return
        dialog = WalnutDialog(self, variety_id=variety_id)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            repositories.create_walnut(asdict(dialog.data()))
            self.window.show_message("核桃已创建")
            self.window.refresh_all()
        except Exception as exc:
            self.window.show_error(f"保存核桃失败: {exc}")

    def edit_walnut(self, walnut_id: int) -> None:
        walnut = repositories.get_walnut(walnut_id)
        if not walnut:
            return
        dialog = WalnutDialog(self, variety_id=walnut["variety_id"], walnut=walnut)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            repositories.update_walnut(walnut_id, asdict(dialog.data()))
            self.window.show_message("核桃已更新")
            self.window.refresh_all()
        except Exception as exc:
            self.window.show_error(f"更新核桃失败: {exc}")

    def delete_walnut(self, walnut_id: int) -> None:
        if QMessageBox.question(self, "删除核桃", "确定删除这颗核桃吗？") != QMessageBox.Yes:
            return
        try:
            repositories.delete_walnut(walnut_id)
            self.window.show_message("核桃已删除")
            self.window.refresh_all()
        except Exception as exc:
            self.window.show_error(f"删除核桃失败: {exc}")


class MatchingTab(VarietyScopedWidget):
    def __init__(self, window: "PairNutMainWindow"):
        super().__init__(window)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        self.scroll_layout.setSpacing(16)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.scroll_content)
        scroll.setFrameShape(QFrame.NoFrame)

        hero = create_card()
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 20, 24, 20)
        eyebrow = QLabel("Matching")
        eyebrow.setProperty("role", "eyebrow")
        title = QLabel("候选配对看板")
        title.setProperty("role", "headline")
        subtitle = QLabel("每颗核桃显示 3 个最高分候选，你可以锁定最满意的一对，或直接拉黑不合适的组合。")
        subtitle.setProperty("role", "subtle")
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("当前品种"))
        toolbar.addWidget(self.variety_combo)
        toolbar.addStretch(1)
        refresh_button = QPushButton("刷新候选")
        refresh_button.setProperty("variant", "primary")
        refresh_button.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_button)
        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        hero_layout.addLayout(toolbar)

        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.addWidget(hero)
        layout.addWidget(scroll)

    def clear_cards(self) -> None:
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def refresh(self) -> None:
        self.refresh_variety_combo()
        self.clear_cards()
        variety_id = self.window.selected_variety_id
        if not variety_id:
            self.scroll_layout.addWidget(QLabel("请先创建并选中一个品种。"))
            return

        candidates_by_walnut = get_candidates_for_variety(variety_id)
        walnuts = repositories.list_walnuts(variety_id=variety_id, include_locked=True)
        if not walnuts:
            self.scroll_layout.addWidget(QLabel("当前品种还没有核桃。"))
            return

        for walnut in walnuts:
            self.scroll_layout.addWidget(self._create_walnut_group(variety_id, walnut, candidates_by_walnut.get(walnut["id"], [])))

    def _create_walnut_group(self, variety_id: int, walnut: dict, candidates: list) -> QGroupBox:
        title = (
            f'{walnut["serial_no"]}   ·   '
            f'三维 {walnut["edge_mm"]:.2f}/{walnut["belly_mm"]:.2f}/{walnut["height_mm"]:.2f}   ·   '
            f'克重 {walnut["weight_g"]:.2f}g'
        )
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        meta_row = QHBoxLayout()
        meta_row.addWidget(create_chip(f'瑕疵 {walnut["defect_level"]}', "#efe4d4", "#6d5746"))
        meta_row.addWidget(create_chip("已锁定" if walnut["is_locked"] else "可参与推荐", "#f6f0e5", "#7a6554"))
        meta_row.addStretch(1)
        layout.addLayout(meta_row)

        active_lock = repositories.get_active_lock_for_walnut(walnut["id"])
        if active_lock:
            partner_id = active_lock["walnut_id_2"] if active_lock["walnut_id_1"] == walnut["id"] else active_lock["walnut_id_1"]
            partner = repositories.get_walnut(partner_id)
            lock_card = create_candidate_card()
            lock_layout = QHBoxLayout(lock_card)
            lock_layout.setContentsMargins(16, 14, 16, 14)
            lock_layout.addWidget(QLabel(f'已锁定配对：{partner["serial_no"]}'))
            unlock_button = QPushButton("解除锁定")
            unlock_button.clicked.connect(lambda _=False, pair_id=active_lock["id"]: self._unlock_pair(pair_id))
            lock_layout.addStretch(1)
            lock_layout.addWidget(unlock_button)
            layout.addWidget(lock_card)
            return group

        if not candidates:
            empty_card = create_candidate_card()
            empty_layout = QVBoxLayout(empty_card)
            empty_layout.setContentsMargins(16, 14, 16, 14)
            empty_layout.addWidget(QLabel("没有满足偏差条件的候选。"))
            layout.addWidget(empty_card)
            return group

        for candidate in candidates:
            layout.addWidget(self._create_candidate_card(variety_id, walnut["id"], candidate))
        return group

    def _create_candidate_card(self, variety_id: int, walnut_id: int, candidate) -> QFrame:
        card = create_candidate_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(10)

        top_row = QHBoxLayout()
        code = QLabel(candidate.serial_no)
        code.setStyleSheet("font-size: 18px; font-weight: 700; color: #2f2015;")
        top_row.addWidget(code)
        top_row.addStretch(1)
        score_chip = create_chip(f"{candidate.total_score:.1f} 分", "#bc7b35", "white")
        top_row.addWidget(score_chip)
        card_layout.addLayout(top_row)

        metrics = QHBoxLayout()
        metrics.addWidget(create_metric("边差", f"{candidate.edge_diff:.2f}"))
        metrics.addWidget(create_metric("肚差", f"{candidate.belly_diff:.2f}"))
        metrics.addWidget(create_metric("高差", f"{candidate.height_diff:.2f}"))
        metrics.addWidget(create_metric("重差", f"{candidate.weight_diff:.2f}"))
        metrics.addWidget(create_metric("瑕疵扣分", f"{candidate.defect_penalty:.1f}"))
        card_layout.addLayout(metrics)

        tags = QHBoxLayout()
        tags.addWidget(create_chip(f'瑕疵 {candidate.defect_level}', "#efe4d4", "#6d5746"))
        tags.addWidget(create_chip(f'尺寸分 {candidate.dimension_score:.1f}', "#ecf1e8", "#4b6847"))
        tags.addWidget(create_chip(f'克重加分 {candidate.weight_bonus:.1f}', "#eef2f8", "#4f6480"))
        tags.addStretch(1)
        card_layout.addLayout(tags)

        button_row = QHBoxLayout()
        lock_button = QPushButton("锁定")
        lock_button.setProperty("variant", "primary")
        lock_button.clicked.connect(lambda _=False, left_id=walnut_id, right_id=candidate.walnut_id: self._lock_pair(variety_id, left_id, right_id))
        blacklist_button = QPushButton("拉黑")
        blacklist_button.setProperty("variant", "danger")
        blacklist_button.clicked.connect(lambda _=False, left_id=walnut_id, right_id=candidate.walnut_id: self._blacklist_pair(variety_id, left_id, right_id))
        button_row.addWidget(lock_button)
        button_row.addWidget(blacklist_button)
        button_row.addStretch(1)
        card_layout.addLayout(button_row)
        return card

    def _lock_pair(self, variety_id: int, walnut_id_1: int, walnut_id_2: int) -> None:
        try:
            repositories.lock_pair(variety_id, walnut_id_1, walnut_id_2)
            self.window.show_message("配对已锁定")
            self.window.refresh_all()
        except Exception as exc:
            self.window.show_error(f"锁定失败: {exc}")

    def _unlock_pair(self, pair_id: int) -> None:
        repositories.unlock_pair(pair_id)
        self.window.show_message("配对已解除锁定")
        self.window.refresh_all()

    def _blacklist_pair(self, variety_id: int, walnut_id_1: int, walnut_id_2: int) -> None:
        try:
            repositories.create_blacklist_pair(variety_id, walnut_id_1, walnut_id_2)
            self.window.show_message("已加入拉黑列表")
            self.window.refresh_all()
        except Exception as exc:
            self.window.show_error(f"拉黑失败: {exc}")


class PairNutMainWindow(QMainWindow):
    def __init__(self, icon_path: Path | None = None):
        super().__init__()
        self.icon_path = icon_path
        self.selected_variety_id: int | None = None
        self.setWindowTitle("PairNut")
        self.resize(1440, 920)
        self.setMinimumSize(1280, 820)
        self.setStyleSheet(APP_STYLESHEET)
        if icon_path and icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.stack = QStackedWidget()
        self.variety_tab = VarietyTab(self)
        self.walnut_tab = WalnutTab(self)
        self.matching_tab = MatchingTab(self)
        self.stack.addWidget(self.variety_tab)
        self.stack.addWidget(self.walnut_tab)
        self.stack.addWidget(self.matching_tab)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(18)

        root_layout.addWidget(self._build_sidebar(), 0)
        root_layout.addWidget(self._build_content_area(), 1)
        self.setCentralWidget(root)

        self._build_menu()
        self.refresh_all()

    def _build_sidebar(self) -> QFrame:
        sidebar = create_card()
        sidebar.setFixedWidth(280)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(18)

        logo_label = QLabel()
        logo_label.setFixedSize(84, 84)
        logo_label.setAlignment(Qt.AlignCenter)
        if self.icon_path and self.icon_path.exists():
            pixmap = QPixmap(str(self.icon_path)).scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)

        brand_eyebrow = QLabel("PairNut")
        brand_eyebrow.setProperty("role", "eyebrow")
        brand_title = QLabel("本地核桃配对工具")
        brand_title.setStyleSheet("font-size: 24px; font-weight: 700; color: #2f2015;")
        brand_subtitle = QLabel("适合录入、筛选、推荐、锁定和拉黑的桌面工作流。")
        brand_subtitle.setWordWrap(True)
        brand_subtitle.setProperty("role", "subtle")

        layout.addWidget(logo_label, alignment=Qt.AlignLeft)
        layout.addWidget(brand_eyebrow)
        layout.addWidget(brand_title)
        layout.addWidget(brand_subtitle)

        self.nav = QListWidget()
        self.nav.setProperty("nav", True)
        self.nav.setSpacing(2)
        for title in ["品种管理", "核桃管理", "候选配对"]:
            QListWidgetItem(title, self.nav)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        layout.addWidget(self.nav)

        stats_card = create_candidate_card()
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.setContentsMargins(16, 16, 16, 16)
        stats_layout.addWidget(QLabel("当前概览"))

        self.variety_count_label = create_metric("品种数量", "0")
        self.walnut_count_label = create_metric("核桃数量", "0")
        self.locked_count_label = create_metric("锁定配对", "0")
        stats_layout.addWidget(self.variety_count_label)
        stats_layout.addWidget(self.walnut_count_label)
        stats_layout.addWidget(self.locked_count_label)
        layout.addWidget(stats_card)
        layout.addStretch(1)
        return sidebar

    def _build_content_area(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        top_card = create_card()
        top_layout = QHBoxLayout(top_card)
        top_layout.setContentsMargins(24, 20, 24, 20)

        title_column = QVBoxLayout()
        eyebrow = QLabel("Dashboard")
        eyebrow.setProperty("role", "eyebrow")
        self.page_title_label = QLabel("品种管理")
        self.page_title_label.setProperty("role", "headline")
        self.page_subtitle_label = QLabel("先维护品种与偏差规则，再进入核桃录入和配对流程。")
        self.page_subtitle_label.setProperty("role", "subtle")
        title_column.addWidget(eyebrow)
        title_column.addWidget(self.page_title_label)
        title_column.addWidget(self.page_subtitle_label)

        self.current_variety_chip = create_chip("未选中品种", "#f2e7d7", "#6d5746")
        self.flow_chip = create_chip("同品种匹配", "#ecf1e8", "#4b6847")

        chip_column = QVBoxLayout()
        chip_row = QHBoxLayout()
        chip_row.addWidget(self.current_variety_chip)
        chip_row.addWidget(self.flow_chip)
        chip_row.addStretch(1)
        chip_column.addStretch(1)
        chip_column.addLayout(chip_row)
        chip_column.addStretch(1)

        top_layout.addLayout(title_column, 1)
        top_layout.addLayout(chip_column)

        layout.addWidget(top_card)
        layout.addWidget(self.stack, 1)
        return content

    def _build_menu(self) -> None:
        refresh_action = QAction("刷新全部", self)
        refresh_action.triggered.connect(self.refresh_all)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.close)

        menu = self.menuBar().addMenu("文件")
        menu.addAction(refresh_action)
        menu.addSeparator()
        menu.addAction(quit_action)

    def set_selected_variety(self, variety_id: int | None) -> None:
        self.selected_variety_id = variety_id
        self.refresh_all()

    def refresh_all(self) -> None:
        varieties = repositories.list_varieties()
        if self.selected_variety_id is None or not any(v["id"] == self.selected_variety_id for v in varieties):
            self.selected_variety_id = varieties[0]["id"] if varieties else None

        self.variety_tab.refresh()
        self.walnut_tab.refresh()
        self.matching_tab.refresh()

        selected_variety = repositories.get_variety(self.selected_variety_id) if self.selected_variety_id else None
        self.current_variety_chip.setText(selected_variety["name"] if selected_variety else "未选中品种")

        current_index = self.nav.currentRow() if self.nav.currentRow() >= 0 else 0
        titles = [
            ("品种管理", "先维护品种与偏差规则，再进入核桃录入和配对流程。"),
            ("核桃管理", "按品种维护核桃基础数据，保持编号、尺寸和瑕疵信息一致。"),
            ("候选配对", "查看每颗核桃的高分候选，按你的业务判断锁定或拉黑。"),
        ]
        self.page_title_label.setText(titles[current_index][0])
        self.page_subtitle_label.setText(titles[current_index][1])

        walnuts = repositories.list_walnuts(include_locked=True)
        locked_pairs = repositories.list_locked_pairs(active_only=True)
        self._update_metric_widget(self.variety_count_label, str(len(varieties)))
        self._update_metric_widget(self.walnut_count_label, str(len(walnuts)))
        self._update_metric_widget(self.locked_count_label, str(len(locked_pairs)))

    def _update_metric_widget(self, widget: QWidget, value: str) -> None:
        layout = widget.layout()
        if layout and layout.count() > 0:
            item = layout.itemAt(0)
            label = item.widget()
            if isinstance(label, QLabel):
                label.setText(value)

    def show_message(self, message: str) -> None:
        self.status_bar.showMessage(message, 5000)

    def show_error(self, message: str) -> None:
        QMessageBox.critical(self, "PairNut", message)
        self.status_bar.showMessage(message, 8000)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._teardown_ui()
        super().closeEvent(event)

    def _teardown_ui(self) -> None:
        if getattr(self, "_ui_teardown_done", False):
            return
        self._ui_teardown_done = True

        # On macOS with PySide6/Python 3.13, explicit teardown avoids
        # wrapper/child deletion happening in an unsafe order during GC.
        for attr_name in ("variety_tab", "walnut_tab", "matching_tab", "stack", "nav"):
            widget = getattr(self, attr_name, None)
            if widget is not None and isValid(widget):
                widget.setParent(None)
                widget.deleteLater()
            setattr(self, attr_name, None)

        central = self.centralWidget()
        if central is not None and isValid(central):
            self.setCentralWidget(QWidget())
            central.deleteLater()
