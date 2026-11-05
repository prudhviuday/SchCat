"""
AnalysisTab - shows Weekly + Daily charts for multiple stocks (scrollable).
Now supports:
- Safe QThread + worker pattern.
- Autocomplete for industry names.
- Right arrow (→) or '.' key to cycle through next industry.
"""
import logging
import traceback
from typing import Dict, Optional, Iterable, List

import pandas as pd
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QGridLayout, QSizePolicy, QCompleter
)
import pyqtgraph as pg

import chartengine
from chartwidget import ChartWidget

logging.getLogger(__name__).addHandler(logging.NullHandler())


# ---------------- Worker ----------------
class AnalysisWorker(QObject):
    finished = pyqtSignal(dict, str)
    errored = pyqtSignal(str, str)

    def __init__(self, stock_name: str, max_points: int = 800):
        super().__init__()
        self.stock_name = stock_name
        self.max_points = max_points

    def run(self):
        try:
            tf_pairs = [("Weekly", "1W"), ("Daily", "1D")]
            prepared: Dict[str, Optional[dict]] = {}

            for label, tf in tf_pairs:
                try:
                    df = chartengine.fetch_chart_data(self.stock_name, tf)
                except Exception as e:
                    logging.exception("fetch_chart_data error for %s %s: %s", self.stock_name, tf, e)
                    df = None

                if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                    prepared[label] = None
                    continue

                df = df.copy().reset_index()
                dt_col = None
                for c in df.columns:
                    if pd.api.types.is_datetime64_any_dtype(df[c]):
                        dt_col = c
                        break
                if not dt_col:
                    for c in ("date", "Date", "datetime", "time", "index"):
                        if c in df.columns:
                            try:
                                df[c] = pd.to_datetime(df[c], errors="coerce")
                                if df[c].notna().any():
                                    dt_col = c
                                    break
                            except Exception:
                                pass
                if not dt_col:
                    df["_dt"] = pd.date_range(end=pd.Timestamp.now(), periods=len(df))
                    dt_col = "_dt"

                def find_col(cands):
                    for cand in cands:
                        if cand in df.columns:
                            return cand
                    return None

                open_col = find_col(["open", "Open", "OPEN", "o"])
                high_col = find_col(["high", "High", "HIGH", "h"])
                low_col = find_col(["low", "Low", "LOW", "l"])
                close_col = find_col(["close", "Close", "CLOSE", "c"])
                vol_col = find_col(["volume", "Volume", "VOLUME", "vol"])

                if not all([open_col, high_col, low_col, close_col]):
                    prepared[label] = None
                    continue

                if len(df) > self.max_points:
                    df = df.iloc[-self.max_points:].reset_index(drop=True)

                try:
                    x = list(range(len(df)))
                    dates = pd.to_datetime(df[dt_col], errors='coerce')
                    date_labels = [d.strftime("%Y-%m-%d") if not pd.isna(d) else "" for d in dates]

                    prepared[label] = {
                        "x": x,
                        "dates": date_labels,
                        "open": df[open_col].astype(float).tolist(),
                        "high": df[high_col].astype(float).tolist(),
                        "low": df[low_col].astype(float).tolist(),
                        "close": df[close_col].astype(float).tolist(),
                        "volume": (df[vol_col].astype(float).tolist() if vol_col else [0.0]*len(df)),
                    }
                except Exception as e:
                    logging.exception("Data conversion error for %s %s: %s", self.stock_name, tf, e)
                    prepared[label] = None

            self.finished.emit(prepared, self.stock_name)

        except Exception as e:
            tb = traceback.format_exc()
            self.errored.emit(self.stock_name, f"{e}\n{tb}")


# ---------------- Main Tab ----------------
class AnalysisTab(QWidget):
    def __init__(self, parent=None, get_stocks_func=None):
        super().__init__(parent)
        self.get_stocks_func = get_stocks_func

        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(6, 6, 6, 6)

        # top bar
        top = QHBoxLayout()
        top.addWidget(QLabel("Industry / Stock (substring):"))
        self.input = QLineEdit()
        #self.input.setFixedWidth(350)
        top.addWidget(self.input)
        self.go_btn = QPushButton("Go")
        top.addWidget(self.go_btn)
        self.status = QLabel("")
        top.addWidget(self.status)
        self.layout().addLayout(top)

        # autocomplete
        self.completer = QCompleter([], self.input)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.input.setCompleter(self.completer)

        # load industries (initially empty; can refresh after data load)
        self.all_industries: List[str] = []
        self._load_industries_from_excel()

        # scroll area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.container.setLayout(QVBoxLayout())
        self.scroll.setWidget(self.container)
        self.layout().addWidget(self.scroll)

        # chart storage
        self.chart_widgets: Dict[str, Dict[str, ChartWidget]] = {}
        self._threads: Dict[str, QThread] = {}
        self._workers: Dict[str, AnalysisWorker] = {}

        self._loading_timer = QTimer(self)
        self._loading_timer.setInterval(300)
        self._loading_timer.timeout.connect(self._update_loading_dots)
        self._loading_dots = 0

        # track current industry index for cycling
        self._current_industry_index = -1

        # signals
        self.go_btn.clicked.connect(self._on_go)
        self.input.textEdited.connect(self._filter_completer)
        self.destroyed.connect(lambda _: self.stop_all_workers())
        self.input.installEventFilter(self)

    # ---------------- Load industries ----------------
    def _load_industries_from_excel(self):
        try:
            df = pd.read_excel("Data/Industrydata.xlsx")
            if "Industry" in df.columns:
                self.all_industries = df["Industry"].dropna().unique().tolist()
                self.completer.model().setStringList(self.all_industries)
        except Exception:
            logging.exception("Failed to load Industrydata.xlsx")
            self.all_industries = []

    # ---------------- Filter autocomplete ----------------
    def _filter_completer(self, text):
        if not self.all_industries:
            return
        filtered = [i for i in self.all_industries if text.lower() in i.lower()]
        self.completer.model().setStringList(filtered)

    # ---------------- Go button ----------------
    def _on_go(self):
        q = self.input.text().strip()
        if not q:
            return
        self._set_current_industry(q)
        self._load_stocks_for_query(q)

    # ---------------- Key handler ----------------
    def keyPressEvent(self, event):
        """Handle key presses for cycling industries."""
        # Right Arrow or '.' key → cycle to next industry
        if event.key() in (Qt.Key_Right, Qt.Key_Period):
            print("[*] key press logged in") ###################################################
            self._cycle_next_industry()
            event.accept()
        else:
            # Pass other keys to default handler
            super().keyPressEvent(event)

    # ---------------- Cycle industry ----------------
    def _cycle_next_industry(self):
        if not self.all_industries:
            return
        if self._current_industry_index == -1:
            self._current_industry_index = 0
        else:
            self._current_industry_index = (self._current_industry_index + 1) % len(self.all_industries)

        next_ind = self.all_industries[self._current_industry_index]
        self.input.setText(next_ind)
        self._load_stocks_for_query(next_ind)

    def _set_current_industry(self, text: str):
        """Finds and sets the current industry index if exists."""
        if not self.all_industries:
            return
        for i, ind in enumerate(self.all_industries):
            if ind.lower() == text.lower():
                self._current_industry_index = i
                break

    # ---------------- Load stocks ----------------
    def _load_stocks_for_query(self, q: str):
        stocks = []
        if callable(self.get_stocks_func):
            try:
                df = self.get_stocks_func()
                if isinstance(df, pd.DataFrame) and not df.empty:
                    mask = df["Industry"].str.contains(q, case=False, na=False) | df["Stock"].str.contains(q, case=False, na=False)
                    stocks = df[mask]["Stock"].tolist()
            except Exception:
                pass

        if not stocks:
            self.status.setText("No stocks found.")
            return

        max_show = 12
        if len(stocks) > max_show:
            stocks = stocks[:max_show]

        self.load_for_stocks(stocks)

    # ---------------- Load chart workers ----------------
    def load_for_stocks(self, stocks: Iterable[str]):
        self._clear_container()
        if not stocks:
            self.status.setText("No stocks.")
            return

        self.status.setText(f"Preparing {len(stocks)} stocks...")
        self._loading_dots = 0
        self._loading_timer.start()

        for stock in stocks:
            group = QWidget()
            group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            gl = QGridLayout()
            group.setLayout(gl)

            label = QLabel(f"<b>{stock}</b>")
            gl.addWidget(label, 0, 0, 1, 2)

            cw_week = ChartWidget(parent=group, title=f"{stock} - Weekly")
            cw_week.setMinimumHeight(260)
            cw_week.clear()
            cw_week.price_plot.addItem(pg.TextItem("Loading...", anchor=(0.5, 0.5)))
            gl.addWidget(cw_week, 1, 0)

            cw_day = ChartWidget(parent=group, title=f"{stock} - Daily")
            cw_day.setMinimumHeight(260)
            cw_day.clear()
            cw_day.price_plot.addItem(pg.TextItem("Loading...", anchor=(0.5, 0.5)))
            gl.addWidget(cw_day, 1, 1)

            self.container.layout().addWidget(group)
            self.chart_widgets[stock] = {"weekly": cw_week, "daily": cw_day, "group": group}

            QTimer.singleShot(50, lambda s=stock: self._start_worker(s))

    # ---------------- Threaded workers ----------------
    def _start_worker(self, stock_name: str):
        if stock_name in self._workers:
            return
        worker = AnalysisWorker(stock_name)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        worker.finished.connect(self._on_finished)
        worker.errored.connect(self._on_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.errored.connect(thread.quit)
        worker.errored.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._workers[stock_name] = worker
        self._threads[stock_name] = thread
        thread.start()

    # ---------------- Worker signals ----------------
    def _on_finished(self, prepared: Dict[str, dict], stock_name: str):
        widgets = self.chart_widgets.get(stock_name)
        if widgets:
            for tf, key in [("Weekly", "weekly"), ("Daily", "daily")]:
                w = widgets.get(key)
                if w:
                    try:
                        w.plot(prepared.get(tf))
                    except Exception:
                        w.clear()
                        w.price_plot.addItem(pg.TextItem("No data", anchor=(0.5, 0.5)))

        self._cleanup_worker(stock_name)
        if not self._workers:
            self._loading_timer.stop()
            self.status.setText("Done")

    def _on_error(self, stock_name: str, text: str):
        logging.error("Analysis worker error %s: %s", stock_name, text)
        widgets = self.chart_widgets.get(stock_name)
        if widgets:
            for key in ("weekly", "daily"):
                w = widgets.get(key)
                w.clear()
                w.price_plot.addItem(pg.TextItem("Error", anchor=(0.5, 0.5)))

        self._cleanup_worker(stock_name)
        if not self._workers:
            self._loading_timer.stop()
            self.status.setText("Error fetching")

    # ---------------- Cleanup helpers ----------------
    def _cleanup_worker(self, stock_name: str):
        self._workers.pop(stock_name, None)
        self._threads.pop(stock_name, None)

    def _update_loading_dots(self):
        self._loading_dots = (self._loading_dots + 1) % 4
        self.status.setText("Fetching" + "." * self._loading_dots)

    def _clear_container(self):
        layout = self.container.layout()
        for i in reversed(range(layout.count())):
            w = layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        self.chart_widgets.clear()

    def stop_all_workers(self):
        try:
            if self._loading_timer.isActive():
                self._loading_timer.stop()
        except Exception:
            pass
        for thread in self._threads.values():
            try:
                if thread.isRunning():
                    thread.quit()
            except Exception:
                pass
        for thread in self._threads.values():
            try:
                thread.wait(2000)
            except Exception:
                pass
        self._workers.clear()
        self._threads.clear()

