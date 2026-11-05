# chartpanel.py
"""
Chart panel that fetches 4 timeframes and displays them using reusable ChartWidget.
"""
import logging
import traceback
from typing import Dict, Optional

import pandas as pd
from PyQt5.QtCore import QThread, pyqtSignal, QObject, QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QGridLayout

import chartengine
import pyqtgraph as pg
from chartwidget import ChartWidget

# <<-- IMPORTANT: filemode='w' will overwrite previous log at each program start.
# Set level to WARNING to reduce log volume; change to INFO if you want more details.
logging.basicConfig(
    filename="chartpanel.log",
    filemode="w",
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s: %(message)s"
)


# Worker runs in QThread and emits prepared plain data
class ChartWorker(QObject):
    finished = pyqtSignal(dict, str)
    errored = pyqtSignal(str)

    def __init__(self, stock_name: str, max_points: int = 800):
        super().__init__()
        self.stock_name = stock_name
        self.max_points = max_points

    def run(self):
        try:
            tf_pairs = [("Weekly", "1W"), ("Daily", "1D"), ("Hourly", "1H"), ("5-min", "5m")]
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

                # find datetime column; fallback synthetic if needed
                dt_col = None
                for c in df.columns:
                    if pd.api.types.is_datetime64_any_dtype(df[c]):
                        dt_col = c
                        break
                if dt_col is None:
                    for c in ("date", "Date", "datetime", "time", "index"):
                        if c in df.columns:
                            try:
                                df[c] = pd.to_datetime(df[c], errors="coerce")
                                if df[c].notna().any():
                                    dt_col = c
                                    break
                            except Exception:
                                pass
                if dt_col is None:
                    df["_dt"] = pd.date_range(end=pd.Timestamp.now(), periods=len(df))
                    dt_col = "_dt"

                # find OHLC and volume columns
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
                    logging.warning("Missing OHLC columns for %s %s - cols: %s", self.stock_name, tf, df.columns.tolist())
                    prepared[label] = None
                    continue

                # downsample if too large
                if len(df) > self.max_points:
                    df = df.iloc[-self.max_points :].reset_index(drop=True)

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
            logging.exception("ChartWorker failed: %s", e)
            self.errored.emit(f"{str(e)}\n{tb}")


# ChartPanel: composes 4 ChartWidget instances
class ChartPanel(QWidget):
    def __init__(self, parent=None, max_points: int = 800):
        super().__init__(parent)
        self.max_points = max_points
        self._thread = None
        self._worker = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        self.setLayout(QVBoxLayout())

        top_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Enter stock symbol")
        self.go_btn = QPushButton("Go")

        # 👇 add this new button
        self.industry_btn = QPushButton("Industry")

        self.loading = QLabel("")
        self.loading.setFixedWidth(140)

        top_row.addWidget(self.input)
        top_row.addWidget(self.go_btn)
        top_row.addWidget(self.industry_btn)   # 👈 add it in the same row
        top_row.addWidget(self.loading)
        top_row.addStretch()
        self.layout().addLayout(top_row)


        # grid of ChartWidget children
        self.grid = QGridLayout()
        self.layout().addLayout(self.grid)
        self.widgets = []
        titles = ["Weekly", "Daily", "Hourly", "5-min"]
        for i in range(4):
            cw = ChartWidget(title=titles[i])
            r, c = divmod(i, 2)
            self.grid.addWidget(cw, r, c)
            self.widgets.append(cw)

        # loading animation timer
        self._timer = QTimer()
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._tick)
        self._dots = 0

    def _connect_signals(self):
        # Connect buttons
        try:
            self.go_btn.clicked.disconnect()
        except Exception:
            pass
        self.go_btn.clicked.connect(self._on_go)

        try:
            self.industry_btn.clicked.disconnect()
        except Exception:
            pass
        self.industry_btn.clicked.connect(self._on_industry)

        
    def load_stock(self, stock_name: str):
        self.input.setText(stock_name)
        self._on_go()

    def _on_go(self):
        stock = self.input.text().strip()
        if not stock:
            self.loading.setText("Enter a stock")
            return

        # clear charts visibly
        for w in self.widgets:
            w.clear()
            w.price_plot.addItem(pg.TextItem("Loading...", anchor=(0.5, 0.5)))

        self.loading.setText("Fetching")
        self._dots = 0
        self._timer.start()

        # spawn worker thread
        self._worker = ChartWorker(stock, max_points=self.max_points)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_ready)
        self._worker.errored.connect(self._on_error)
        # cleanup
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._worker.errored.connect(self._thread.quit)
        self._worker.errored.connect(self._worker.deleteLater)

        self._thread.start()

    def _tick(self):
        self._dots = (self._dots + 1) % 4
        self.loading.setText("Fetching" + "." * self._dots)

    def _on_error(self, text: str):
        self._timer.stop()
        self.loading.setText("Error fetching")
        logging.error("ChartPanel worker error: %s", text)
        for w in self.widgets:
            w.clear()
            w.price_plot.addItem(pg.TextItem("Error", anchor=(0.5, 0.5)))

    def _on_ready(self, prepared: Dict[str, dict], stock_name: str):
        self._timer.stop()
        self.loading.setText("Rendering...")
        try:
            timeframes = ["Weekly", "Daily", "Hourly", "5-min"]
            for i, tf in enumerate(timeframes):
                prepared_data = prepared.get(tf)
                widget = self.widgets[i]
                widget.plot(prepared_data)
            self.loading.setText("Done")
        except Exception as e:
            logging.exception("Error plotting prepared charts: %s", e)
            self.loading.setText("Plot error")

    def _on_industry(self):
        try:
            # Step 1: find the main GUI object (MarketSmithGUI)
            main = self.parent()
            while main and not hasattr(main, "tab_analysis"):
                main = main.parent()

            if not main or not hasattr(main, "tab_analysis"):
                self.loading.setText("⚠️ No main tab found")
                return

            # Step 2: get the currently selected stock name from the chart input
            main.tab_control.setCurrentIndex(2)
            stock_name = self.input.text().strip()
            if not stock_name or main.data.empty:
                self.loading.setText("⚠️ No stock or data available")
                return

            # Step 3: find industry name of that stock from main.data
            df = main.data
            if "Stock" not in df.columns or "Industry" not in df.columns:
                self.loading.setText("⚠️ Missing columns")
                return

            row = df[df["Stock"].str.lower() == stock_name.lower()]
            if row.empty:
                self.loading.setText("⚠️ Stock not found in data")
                return

            industry_name = row["Industry"].iloc[0]

            # Step 4: send to Analysis tab
            self.loading.setText(f"Opening {industry_name}...")
            main.tab_analysis.input.setText(str(industry_name))
            main.tab_analysis._on_go()
            

        except Exception as e:
            import traceback
            print("Error in _on_industry:", e, traceback.format_exc())
            self.loading.setText("Industry tab error")
