from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QBrush, QFont
import pandas as pd

import chartink


DEFAULT_RULES = {
    "4% bull": [["VVgood", 170, 1000000, "#339966"], ["vgood", 75, 170, "#00FF00"], ["blowavg", 30, 60, "#F4CCCC"], ["worst", 0, 30, "#E06666"]],
    "4% bear": [["VVgood", 0, 12, "#339966"], ["vgood", 12, 35, "#00FF00"], ["blowavg", 35, 150, "#F4CCCC"], ["worst", 150, 100000, "#E06666"]],
    "5-day ratio": [["VVgood", 4, 10000, "#339966"], ["vgood", 1.5, 4, "#00FF00"], ["blowavg", 1, 1.5, "#F4CCCC"], ["worst", 0, 1.5, "#E06666"]],
    "10-day ratio": [["VVgood", 4, 10000, "#339966"], ["vgood", 1.5, 4, "#00FF00"], ["blowavg", 1, 1.5, "#F4CCCC"], ["worst", 0, 1.5, "#E06666"]],
    
    "q25 bull": [["vgood", 450, 100000, "#00FF00"], ["blowavg", 300, 450, "#F4CCCC"], ["worst", 0, 300, "#E06666"]],
    "q25 bear": [["vgood", 0, 150, "#00FF00"], ["blowavg", 150, 450, "#F4CCCC"], ["worst", 450, 100000, "#E06666"]],
    "m25 bull": [["vgood", 55, 100000, "#00FF00"], ["blowavg", 40, 55, "#F4CCCC"], ["worst", 0, 40, "#E06666"]],
    "m25 bear": [["vgood", 0, 10, "#00FF00"], ["blowavg", 10, 45, "#F4CCCC"], ["worst", 45, 100000, "#E06666"]],
    "m50 bull": [["vgood", 9, 100000, "#00FF00"], ["blowavg", 4, 9, "#F4CCCC"], ["worst", 0, 4, "#E06666"]],
    "m50 bear": [["vgood", 0, 1, "#00FF00"], ["blowavg", 1, 4, "#F4CCCC"], ["worst", 4, 100000, "#E06666"]],
    
    "34/13 bull": [["vgood", 310, 100000, "#00FF00"], ["blowavg", 250, 310, "#F4CCCC"], ["worst", 0, 250, "#E06666"]],
    "34/13 bear": [["vgood", 0, 270, "#00FF00"], ["blowavg", 270, 350, "#F4CCCC"], ["worst", 350, 100000, "#E06666"]]
}

DEFAULT_CELL_COLOR = "#FFFFFF"



class MarketPulseTab(QWidget):
    """
    MarketPulse tab with optional auto-refresh.
    """

    def __init__(self, parent=None, auto_refresh=False, refresh_interval=60000, rules=None, default_color=None):
        super().__init__(parent)
        self.parent = parent

        self.columns = [
            "Date", "4% bull", "4% bear", "5-day ratio", "10-day ratio",
            "q25 bull", "q25 bear", "m25 bull", "m25 bear",
            "m50 bull", "m50 bear",
            "34/13 bull", "34/13 bear"
        ]

        self.RULES = rules if rules is not None else DEFAULT_RULES
        self.default_color = default_color if default_color is not None else DEFAULT_CELL_COLOR

        self._setup_ui()

        self._refresh_interval = int(refresh_interval)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.load_data)
        if auto_refresh:
            self._timer.start(self._refresh_interval)
        self.auto_cb.toggled.connect(self._on_auto_toggled)

        self.load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_data)
        controls.addWidget(self.refresh_btn)

        self.auto_cb = QCheckBox("Auto-refresh")
        controls.addWidget(self.auto_cb)

        controls.addStretch(1)
        layout.addLayout(controls)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

    def _on_auto_toggled(self, checked: bool):
        if checked:
            self._timer.start(self._refresh_interval)
        else:
            self._timer.stop()

    # ----------------- Rule helpers -----------------
    def set_rules(self, rules: dict, default_color: str = None):
        self.RULES = rules
        if default_color is not None:
            self.default_color = default_color

    def _find_rule_color(self, col_name: str, raw_value) -> str:
        if col_name not in self.RULES:
            return self.default_color

        try:
            val = float(raw_value)
        except Exception:
            return self.default_color

        rules_for_col = self.RULES.get(col_name, [])
        for rule in rules_for_col:
            if len(rule) < 4:
                continue
            _, rmin, rmax, color = rule
            try:
                if rmin is None and val <= float(rmax):
                    return color
                if rmax is None and val >= float(rmin):
                    return color
                if rmin is not None and rmax is not None and float(rmin) <= val <= float(rmax):
                    return color
            except Exception:
                continue

        return self.default_color

    def _text_color_for_bg(self, hexcolor: str) -> str:
        try:
            c = QColor(hexcolor)
            r, g, b, _ = c.getRgb()
            lum = 0.299*r + 0.587*g + 0.114*b
            return "#000000" if lum > 186 else "#FFFFFF"
        except Exception:
            return "#000000"

    # --------------------------------------------------------
    # NEW — Apply uniform font style to every cell
    # --------------------------------------------------------
    def _apply_uniform_text_style(self, item: QTableWidgetItem):
        font = QFont("Calibri", 11)       # You can adjust here
        font.setBold(False)
        font.setItalic(False)
        item.setFont(font)
    # --------------------------------------------------------

    def load_data(self):
        try:
            raw = chartink.chartinkDashboard()

            if raw is None:
                rows = []
            elif isinstance(raw, pd.DataFrame):
                rows = raw.values.tolist()
            elif isinstance(raw, list):
                if len(raw) > 0 and all(isinstance(r, (list, tuple)) for r in raw):
                    rows = [list(r) for r in raw]
                else:
                    rows = [list(raw)]
            elif isinstance(raw, tuple):
                rows = [list(raw)]
            else:
                rows = [[str(raw)]]

            norm_rows = []
            for r in rows:
                rlist = ["" if v is None else v for v in r]
                if len(rlist) < len(self.columns):
                    rlist += [""] * (len(self.columns) - len(rlist))
                elif len(rlist) > len(self.columns):
                    rlist = rlist[: len(self.columns)]
                norm_rows.append(rlist)

            self._populate_table(norm_rows)

        except Exception as e:
            QMessageBox.warning(self, "MarketPulseTab - Load error", f"Failed to load dashboard data:\n{e}")

    def _populate_table(self, rows):
        self.table.setRowCount(len(rows))

        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                text = "" if value is None else str(value)
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)

                # NEW — Apply uniform text style
                self._apply_uniform_text_style(item)

                # Background color based on rules
                col_name = self.columns[j]
                color_hex = self._find_rule_color(col_name, value)
                try:
                    brush = QBrush(QColor(color_hex))
                    item.setBackground(brush)
                    text_color = self._text_color_for_bg(color_hex)
                    item.setForeground(QBrush(QColor(text_color)))
                except Exception:
                    pass

                self.table.setItem(i, j, item)

    def get_dataframe(self) -> pd.DataFrame:
        rows = []
        for r in range(self.table.rowCount()):
            row = [
                self.table.item(r, c).text() if self.table.item(r, c) is not None else ""
                for c in range(self.table.columnCount())
            ]
            rows.append(row)
        return pd.DataFrame(rows, columns=self.columns)
