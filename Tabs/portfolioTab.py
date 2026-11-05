# PortfolioTab.py
"""
Portfolio panel that fetches 4 timeframes and displays a synthetic
portfolio candle built from all holdings in util.getPortfolio().

The portfolio candle is based on unrealized P&L:
    qty * (price - buy_price)
for open/high/low/close, similar to your PineScript logic.
"""
import logging
import traceback
from typing import Dict, Optional, List, Tuple, Any

import pandas as pd
from PyQt5.QtCore import QThread, pyqtSignal, QObject, QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QGridLayout

import chartengine
import pyqtgraph as pg
from chartwidget import ChartWidget
from helper import FilterDialog
import util

# IMPORTANT: filemode='w' will overwrite previous log at each program start.
logging.basicConfig(
    filename="PortfolioTab.log",
    filemode="w",
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s: %(message)s"
)


class ChartWorker(QObject):
    finished = pyqtSignal(dict, str)
    errored = pyqtSignal(str)

    def __init__(self, portfolio_name: str, max_points: int = 800):
        super().__init__()
        self.portfolio_name = portfolio_name
        self.max_points = max_points
        self.stockData = util.getPortfolio()  # expected: [['RVNL', 12, 320], ['IRFC', 22, 57]]

    def run(self):
        try:
            prepared: Dict[str, Optional[dict]] = {}

            prepared["Weekly"] = self._prepare_weekly()
            prepared["Daily"] = self._prepare_daily()
            prepared["Hourly"] = self._prepare_hourly()
            prepared["5-min"] = self._prepare_5min()

            self.finished.emit(prepared, self.portfolio_name)

        except Exception as e:
            tb = traceback.format_exc()
            logging.exception("ChartWorker failed: %s", e)
            self.errored.emit(f"{str(e)}\n{tb}")

    def _prepare_weekly(self) -> Optional[dict]:
        return self._build_portfolio_candle("1W")

    def _prepare_daily(self) -> Optional[dict]:
        return self._build_portfolio_candle("1D")

    def _prepare_hourly(self) -> Optional[dict]:
        return self._build_portfolio_candle("1H")

    def _prepare_5min(self) -> Optional[dict]:
        return self._build_portfolio_candle("5m")

    def _normalize_chart_df(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        Convert chartengine output to a normalized dataframe with:
        dt, open, high, low, close, volume
        """
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return None

        df = df.copy().reset_index()

        # find datetime column
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
            return None

        out = pd.DataFrame()
        out["dt"] = pd.to_datetime(df[dt_col], errors="coerce")
        out["open"] = pd.to_numeric(df[open_col], errors="coerce")
        out["high"] = pd.to_numeric(df[high_col], errors="coerce")
        out["low"] = pd.to_numeric(df[low_col], errors="coerce")
        out["close"] = pd.to_numeric(df[close_col], errors="coerce")
        out["volume"] = pd.to_numeric(df[vol_col], errors="coerce") if vol_col else 0.0

        out = out.dropna(subset=["dt"])
        out = out.sort_values("dt")
        out = out.drop_duplicates("dt", keep="last")
        return out

    def _fetch_stock_frame(self, stock_name: str, tf: str) -> Optional[pd.DataFrame]:
        try:
            df = chartengine.fetch_chart_data(stock_name, tf)
        except Exception as e:
            logging.exception("fetch_chart_data error for %s %s: %s", stock_name, tf, e)
            return None

        return self._normalize_chart_df(df)

    def _get_holdings(self) -> List[Tuple[str, float, float]]:
        """
        Convert util.getPortfolio() into a clean list of:
        [(stock, qty, buy_price), ...]
        """
        holdings = self.stockData

        if holdings is None:
            return []

        if isinstance(holdings, pd.DataFrame):
            cols = list(holdings.columns)
            stock_col = "Stock" if "Stock" in cols else cols[0]
            qty_col = "Qty" if "Qty" in cols else cols[1]
            buy_col = "Buy price" if "Buy price" in cols else cols[2]
            rows = holdings[[stock_col, qty_col, buy_col]].values.tolist()
        else:
            rows = holdings

        clean = []
        for row in rows:
            try:
                stock = str(row[0]).strip()
                qty = float(row[1])
                buy = float(row[2])
                if stock:
                    clean.append((stock, qty, buy))
            except Exception:
                continue
        return clean

    def _build_portfolio_candle(self, tf: str) -> Optional[dict]:
        """
        Build a synthetic portfolio OHLC candle series:
            qty * (price - buy_price)
        across all holdings.
        """
        holdings = self._get_holdings()
        if not holdings:
            return None

        per_stock_frames = []

        for stock_name, qty, buy_price in holdings:
            df = self._fetch_stock_frame(stock_name, tf)
            if df is None or df.empty:
                continue

            df = df.copy()
            df = df.set_index("dt")

            # unrealized P&L contribution for this stock
            contrib = pd.DataFrame(index=df.index)
            contrib["open"] = qty * (df["open"] - buy_price)
            contrib["high"] = qty * (df["high"] - buy_price)
            contrib["low"] = qty * (df["low"] - buy_price)
            contrib["close"] = qty * (df["close"] - buy_price)
            contrib["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)

            per_stock_frames.append(contrib)

        if not per_stock_frames:
            return None

        # Build master date index
        master_index = per_stock_frames[0].index
        for f in per_stock_frames[1:]:
            master_index = master_index.union(f.index)
        master_index = master_index.sort_values()

        # Sum all stock contributions
        total = pd.DataFrame(index=master_index)
        total[["open", "high", "low", "close", "volume"]] = 0.0

        for f in per_stock_frames:
            # forward-fill so the portfolio stays continuous between bars
            # and fill initial gaps with 0
            ff = f.reindex(master_index).ffill().fillna(0.0)
            total["open"] += ff["open"]
            total["high"] += ff["high"]
            total["low"] += ff["low"]
            total["close"] += ff["close"]
            total["volume"] += ff["volume"]

        if len(total) > self.max_points:
            total = total.iloc[-self.max_points:].copy()

        try:
            x = list(range(len(total)))
            dates = total.index
            date_labels = [d.strftime("%Y-%m-%d") if not pd.isna(d) else "" for d in dates]

            return {
                "x": x,
                "dates": date_labels,
                "open": total["open"].astype(float).tolist(),
                "high": total["high"].astype(float).tolist(),
                "low": total["low"].astype(float).tolist(),
                "close": total["close"].astype(float).tolist(),
                "volume": total["volume"].astype(float).tolist(),
            }
        except Exception as e:
            logging.exception("Portfolio candle build error for %s: %s", tf, e)
            return None


class PortfolioTab(QWidget):
    def __init__(self, parent=None, max_points: int = 800):
        super().__init__(parent)
        self.max_points = max_points
        self._thread = None
        self._worker = None
        self.advanced_filters = {}
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        self.setLayout(QVBoxLayout())

        top_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Enter stock symbol")
        self.go_btn = QPushButton("Go")

        self.loading = QLabel("")
        self.loading.setFixedWidth(50)

        top_row.addWidget(self.input)
        top_row.addWidget(self.go_btn)

        self.settings_btn = QPushButton("⚙️ Settings")
        self.settings_btn.clicked.connect(self.open_filter_settings)
        top_row.addWidget(self.settings_btn)

        top_row.addWidget(self.loading)
        top_row.addStretch()
        self.layout().addLayout(top_row)

        self.grid = QGridLayout()
        self.layout().addLayout(self.grid)

        self.widgets = []
        titles = ["Weekly", "Daily", "Hourly", "5-min"]
        for i in range(4):
            cw = ChartWidget(title=titles[i])
            r, c = divmod(i, 2)
            self.grid.addWidget(cw, r, c)
            self.widgets.append(cw)

        self._timer = QTimer()
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._tick)
        self._dots = 0

    def _connect_signals(self):
        try:
            self.go_btn.clicked.disconnect()
        except Exception:
            pass
        self.go_btn.clicked.connect(self._on_go)

    # ------------------ Advanced filter dialog handlers ------------------
    def open_filter_settings(self):
        numeric_cols = ["GroupRank", "RS", "EPS", "MasterScore", "AccDis", "FScore", "PE", "PEG", "ROE"]
        dlg = FilterDialog(self, numeric_cols)

        for col in numeric_cols:
            min_w, max_w = dlg.inputs[col]
            prev = self.advanced_filters.get(col, {})
            if "min" in prev:
                min_w.setText(str(prev["min"]))
            if "max" in prev:
                max_w.setText(str(prev["max"]))

        dlg.go_btn.clicked.connect(lambda: self.apply_advanced_filters(dlg))
        dlg.clear_btn.clicked.connect(lambda: self.clear_advanced_filters(dlg))
        dlg.exec_()

    def apply_advanced_filters(self, dlg):
        if getattr(self, "data", None) is None or self.data.empty:
            dlg.reject()
            return

        df = self.data.copy()
        numeric_cols = list(dlg.inputs.keys())
        self.advanced_filters = {}

        for col in numeric_cols:
            min_box, max_box = dlg.inputs[col]
            min_text = min_box.text().strip()
            max_text = max_box.text().strip()

            saved = {}
            if min_text != "":
                try:
                    saved["min"] = float(min_text)
                except Exception:
                    pass
            if max_text != "":
                try:
                    saved["max"] = float(max_text)
                except Exception:
                    pass

            if saved:
                self.advanced_filters[col] = saved

            if col in df.columns:
                try:
                    series = pd.to_numeric(df[col], errors="coerce")
                    if "min" in saved:
                        df = df[series >= saved["min"]]
                    if "max" in saved:
                        df = df[series <= saved["max"]]
                except Exception:
                    pass

        self.filtered_data = df
        self.update_table(df)
        dlg.accept()

    def clear_advanced_filters(self, dlg):
        self.advanced_filters = {}
        for min_box, max_box in dlg.inputs.values():
            min_box.clear()
            max_box.clear()

        self.filtered_data = self.data.copy() if getattr(self, "data", None) is not None else pd.DataFrame()
        self.update_table(self.filtered_data)
        dlg.accept()

    def load_stock(self, portfolio_name: str):
        self.input.setText(portfolio_name)
        self._on_go()

    def _on_go(self):
        stock = self.input.text().strip()
        if not stock:
            self.loading.setText("Enter a stock")
            return

        self._clear_all_charts("Loading...")

        self.loading.setText("Fetching")
        self._dots = 0
        self._timer.start()

        self._worker = ChartWorker(stock, max_points=self.max_points)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_ready)
        self._worker.errored.connect(self._on_error)

        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._worker.errored.connect(self._thread.quit)
        self._worker.errored.connect(self._worker.deleteLater)

        self._thread.start()

    def _clear_all_charts(self, text: str):
        for w in self.widgets:
            w.clear()
            w.price_plot.addItem(pg.TextItem(text, anchor=(0.5, 0.5)))

    def _tick(self):
        self._dots = (self._dots + 1) % 4
        self.loading.setText("Fetching" + "." * self._dots)

    def _on_error(self, text: str):
        self._timer.stop()
        self.loading.setText("Error fetching")
        logging.error("ChartPanel worker error: %s", text)
        self._clear_all_charts("Error")

    def _on_ready(self, prepared: Dict[str, dict], portfolio_name: str):
        self._timer.stop()
        self.loading.setText("Rendering...")
        try:
            self._plot_weekly(prepared.get("Weekly"))
            self._plot_daily(prepared.get("Daily"))
            self._plot_hourly(prepared.get("Hourly"))
            self._plot_5min(prepared.get("5-min"))
            self.loading.setText("Done")
        except Exception as e:
            logging.exception("Error plotting prepared charts: %s", e)
            self.loading.setText("Plot error")

    # --------- individual chart methods ---------

    def _plot_weekly(self, prepared_data: Optional[dict]):
        widget = self.widgets[0]
        widget.clear()
        if prepared_data is None:
            widget.price_plot.addItem(pg.TextItem("No Weekly data", anchor=(0.5, 0.5)))
            return
        widget.plot(prepared_data)

    def _plot_daily(self, prepared_data: Optional[dict]):
        widget = self.widgets[1]
        widget.clear()
        if prepared_data is None:
            widget.price_plot.addItem(pg.TextItem("No Daily data", anchor=(0.5, 0.5)))
            return
        widget.plot(prepared_data)

    def _plot_hourly(self, prepared_data: Optional[dict]):
        widget = self.widgets[2]
        widget.clear()
        if prepared_data is None:
            widget.price_plot.addItem(pg.TextItem("No Hourly data", anchor=(0.5, 0.5)))
            return
        widget.plot(prepared_data)

    def _plot_5min(self, prepared_data: Optional[dict]):
        widget = self.widgets[3]
        widget.clear()
        if prepared_data is None:
            widget.price_plot.addItem(pg.TextItem("No 5-min data", anchor=(0.5, 0.5)))
            return
        widget.plot(prepared_data)

    def _on_industry(self):
        try:
            main = self.parent()
            while main and not hasattr(main, "tab_analysis"):
                main = main.parent()

            if not main or not hasattr(main, "tab_analysis"):
                self.loading.setText("⚠️ No main tab found")
                return

            main.tab_control.setCurrentIndex(2)
            portfolio_name = self.input.text().strip()
            if not portfolio_name or main.data.empty:
                self.loading.setText("⚠️ No stock or data available")
                return

            df = main.data
            if "Stock" not in df.columns or "Industry" not in df.columns:
                self.loading.setText("⚠️ Missing columns")
                return

            row = df[df["Stock"].str.lower() == portfolio_name.lower()]
            if row.empty:
                self.loading.setText("⚠️ Stock not found in data")
                return

            industry_name = row["Industry"].iloc[0]

            self.loading.setText(f"Opening {industry_name}...")
            main.tab_analysis.input.setText(str(industry_name))
            main.tab_analysis._on_go()

        except Exception as e:
            print("Error in _on_industry:", e, traceback.format_exc())
            self.loading.setText("Industry tab error")