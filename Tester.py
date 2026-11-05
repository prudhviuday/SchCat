# pyqt_charts.py
import sys
import threading
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets

# Replace this import with your real chart data fetcher.
# The code expects a function chartengine.fetch_chart_data(stock_name, timeframe)
# that returns a pandas.DataFrame indexed by datetime (or with 'time' column)
# and columns: open, high, low, close, volume, optionally ema50, ema200.
import chartengine


# -------------------------
# Small candlestick item (from common pyqtgraph examples)
# -------------------------
class CandlestickItem(pg.GraphicsObject):
    """
    Fast candlestick item for pyqtgraph.
    Expects data as a Nx5 array: [x, open, close, min, max]
    x can be numerical (index positions). We'll handle x labels separately.
    """
    def __init__(self, data):
        pg.GraphicsObject.__init__(self)
        self.data = np.asarray(data)
        self.generatePicture()

    def generatePicture(self):
        self.picture = QtGui.QPicture()
        p = QtGui.QPainter(self.picture)
        w = 0.4  # half-width
        for (x, open_, close_, low_, high_) in self.data:
            if close_ >= open_:
                p.setBrush(QtGui.QBrush(QtGui.QColor(0, 160, 0)))  # green
                p.setPen(pg.mkPen('k'))
            else:
                p.setBrush(QtGui.QBrush(QtGui.QColor(200, 0, 0)))  # red
                p.setPen(pg.mkPen('k'))

            # wick
            p.drawLine(QtCore.QPointF(x, low_), QtCore.QPointF(x, high_))
            # body
            rect = QtCore.QRectF(x - w, open_, 2 * w, close_ - open_)
            p.drawRect(rect)
        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        if len(self.data) == 0:
            return QtCore.QRectF()
        xs = self.data[:, 0]
        lows = self.data[:, 3]
        highs = self.data[:, 4]
        return QtCore.QRectF(xs.min() - 1, lows.min() - 1, xs.max() - xs.min() + 2, highs.max() - lows.min() + 2)


# -------------------------
# Worker thread via QObject to safely signal UI thread
# -------------------------
class FetchWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal(str, dict)  # stock, {tf: df}
    error = QtCore.pyqtSignal(str)

    def __init__(self, stock: str, timeframes: list):
        super().__init__()
        self.stock = stock
        self.timeframes = timeframes
        self._stopped = False

    def stop(self):
        self._stopped = True

    @QtCore.pyqtSlot()
    def run(self):
        """Run in background thread, fetch data for all timeframes."""
        try:
            result = {}
            for tf in self.timeframes:
                if self._stopped:
                    return
                # call your chart fetcher here
                # It should return a pandas.DataFrame (or convertible)
                df = chartengine.fetch_chart_data(self.stock, tf)
                df_processed = self._normalize_df(df)
                result[tf] = df_processed
            self.finished.emit(self.stock, result)
        except Exception as e:
            self.error.emit(str(e))

    def _normalize_df(self, df) -> pd.DataFrame:
        """
        Convert different formats to a DataFrame indexed by datetime with columns:
        open, high, low, close, volume, optional ema50, ema200.
        Accepts:
        - pandas.DataFrame with datetime index
        - list of dicts or list-of-lists with 'time' column (epoch or iso)
        """
        if df is None:
            return pd.DataFrame()

        # If already DataFrame, make a copy
        if isinstance(df, pd.DataFrame):
            dff = df.copy()
        else:
            # try to construct DataFrame
            dff = pd.DataFrame(df)

        # If there's a 'time' column, convert it:
        if 'time' in dff.columns:
            # Could be epoch seconds (int) or string datetimes
            try:
                # numeric epoch?
                if np.issubdtype(dff['time'].dtype, np.number):
                    dff['time'] = pd.to_datetime(dff['time'], unit='s', utc=False)
                else:
                    dff['time'] = pd.to_datetime(dff['time'])
            except Exception:
                dff['time'] = pd.to_datetime(dff['time'], errors='coerce')

            dff = dff.set_index('time')

        # If index is numeric epoch
        if not isinstance(dff.index, pd.DatetimeIndex):
            # try to parse index
            try:
                dff.index = pd.to_datetime(dff.index)
            except Exception:
                # Can't parse — create an integer index
                dff.index = pd.Index(range(len(dff)))

        # Keep only expected columns and cast numeric
        for col in ['open', 'high', 'low', 'close', 'volume', 'ema50', 'ema200']:
            if col in dff.columns:
                dff[col] = pd.to_numeric(dff[col], errors='coerce')

        # Drop rows without OHLC
        if 'open' in dff.columns and 'high' in dff.columns and 'low' in dff.columns and 'close' in dff.columns:
            dff = dff.dropna(subset=['open', 'high', 'low', 'close'])
        else:
            # no OHLC -> empty
            return pd.DataFrame()

        return dff


# -------------------------
# Main Chart UI
# -------------------------
class ChartWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PyQtGraph Interactive Charts")
        self.resize(1200, 800)

        layout = QtWidgets.QVBoxLayout(self)

        # Top controls
        top = QtWidgets.QHBoxLayout()
        layout.addLayout(top)

        top.addWidget(QtWidgets.QLabel("Stock:"))
        self.stock_edit = QtWidgets.QLineEdit()
        self.stock_edit.setFixedWidth(180)
        top.addWidget(self.stock_edit)

        self.go_btn = QtWidgets.QPushButton("Go")
        top.addWidget(self.go_btn)

        self.status = QtWidgets.QLabel("")
        top.addWidget(self.status)
        top.addStretch()

        # Tabs for timeframes
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs, stretch=1)

        self.timeframes = ["Weekly", "Daily", "Hourly", "5-min"]
        self.plot_widgets = {}   # tf -> dict of components
        for tf in self.timeframes:
            w = QtWidgets.QWidget()
            vlayout = QtWidgets.QVBoxLayout(w)
            # Graphics layout widget
            gw = pg.GraphicsLayoutWidget()
            vlayout.addWidget(gw, stretch=1)
            self.tabs.addTab(w, tf)
            # Create price plot on top and volume below (shared x)
            price_plot = gw.addPlot(row=0, col=0)
            price_plot.showGrid(x=True, y=True)
            price_plot.setMouseEnabled(x=True, y=True)
            price_plot.setMenuEnabled(True)
            price_plot.setLabel('left', 'Price')

            # Link x-axis range to volume plot
            volume_plot = gw.addPlot(row=1, col=0, rowSpan=1)
            volume_plot.setMaximumHeight(150)
            volume_plot.setLabel('left', 'Volume')
            volume_plot.showGrid(x=True, y=True)
            volume_plot.setMenuEnabled(False)

            # Link x-axis
            volume_plot.setXLink(price_plot)

            # Add crosshair
            vLine = pg.InfiniteLine(angle=90, movable=False)
            price_plot.addItem(vLine, ignoreBounds=True)
            hLine = pg.InfiniteLine(angle=0, movable=False)
            price_plot.addItem(hLine, ignoreBounds=True)

            # store
            self.plot_widgets[tf] = {
                'gw': gw,
                'price': price_plot,
                'volume': volume_plot,
                'vLine': vLine,
                'hLine': hLine,
                'candlestick_item': None,
                'ema50': None,
                'ema200': None,
                'volume_bars': None
            }

            # Enable mouse move for crosshair
            proxy = pg.SignalProxy(price_plot.scene().sigMouseMoved, rateLimit=60, slot=self._mouse_moved(tf))

        # Connect signals
        self.go_btn.clicked.connect(self.on_go)
        self.threadpool = QtCore.QThreadPool()

        self._worker_thread = None
        self._worker_obj = None

    def _mouse_moved(self, tf):
        def handler(evt):
            pos = evt[0]  # QPointF
            plot = self.plot_widgets[tf]['price']
            vb = plot.vb
            if plot.sceneBoundingRect().contains(pos):
                mousePoint = vb.mapSceneToView(pos)
                x = mousePoint.x()
                y = mousePoint.y()
                self.plot_widgets[tf]['vLine'].setPos(x)
                self.plot_widgets[tf]['hLine'].setPos(y)
        return handler

    def on_go(self):
        stock = self.stock_edit.text().strip()
        if not stock:
            self.status.setText("Enter a stock name.")
            return
        self.status.setText("Fetching...")
        self.go_btn.setEnabled(False)
        # start worker thread
        timeframes_map = {
            "Weekly": "1W",   # adapt to chartengine expected TF
            "Daily": "1D",
            "Hourly": "1H",
            "5-min": "5m"
        }
        tfs = [timeframes_map[tf] for tf in self.timeframes]
        # Use FetchWorker with Qt signals
        self._worker_obj = FetchWorker(stock, tfs)
        self._worker_thread = QtCore.QThread()
        self._worker_obj.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker_obj.run)
        self._worker_obj.finished.connect(self.on_fetch_finished)
        self._worker_obj.error.connect(self.on_fetch_error)
        self._worker_obj.finished.connect(lambda *_: self._cleanup_worker())
        self._worker_obj.error.connect(lambda *_: self._cleanup_worker())
        self._worker_thread.start()

    def _cleanup_worker(self):
        try:
            if self._worker_thread:
                self._worker_thread.quit()
                self._worker_thread.wait(2000)
        finally:
            self._worker_thread = None
            self._worker_obj = None
            self.go_btn.setEnabled(True)

    def on_fetch_error(self, err):
        self.status.setText(f"Error: {err}")

    def on_fetch_finished(self, stock, result_dict):
        """
        result_dict: mapping timeframe-string ("1W","1D", etc) -> DataFrame
        We'll map back to displayed tabs order.
        """
        self.status.setText(f"Showing: {stock}")
        # Map the returned keys back to our tab labels (we used 1W,1D,1H,5m)
        mapping_back = {"1W": "Weekly", "1D": "Daily", "1H": "Hourly", "5m": "5-min"}

        for tf_key, df in result_dict.items():
            tf_label = mapping_back.get(tf_key, tf_key)
            if tf_label not in self.plot_widgets:
                continue
            self._update_plot_for_tf(tf_label, df)

    def _update_plot_for_tf(self, tf_label: str, df: pd.DataFrame):
        pw = self.plot_widgets[tf_label]
        price_plot: pg.PlotItem = pw['price']
        volume_plot: pg.PlotItem = pw['volume']

        # Clear previous items
        if pw['candlestick_item'] is not None:
            try:
                price_plot.removeItem(pw['candlestick_item'])
            except Exception:
                pass
            pw['candlestick_item'] = None
        if pw['ema50'] is not None:
            try:
                price_plot.removeItem(pw['ema50'])
            except Exception:
                pass
            pw['ema50'] = None
        if pw['ema200'] is not None:
            try:
                price_plot.removeItem(pw['ema200'])
            except Exception:
                pass
            pw['ema200'] = None
        if pw['volume_bars'] is not None:
            try:
                volume_plot.removeItem(pw['volume_bars'])
            except Exception:
                pass
            pw['volume_bars'] = None

        if df is None or df.empty:
            price_plot.clear()
            volume_plot.clear()
            price_plot.addItem(pw['vLine'])
            price_plot.addItem(pw['hLine'])
            return

        # Prepare numeric x positions
        df = df.copy()
        df = df.sort_index()
        dates = pd.to_datetime(df.index)
        x = np.arange(len(df))  # numeric x

        # Build candlestick data: x, open, close, low, high
        candle_data = np.column_stack([x,
                                       df['open'].astype(float).values,
                                       df['close'].astype(float).values,
                                       df['low'].astype(float).values,
                                       df['high'].astype(float).values])

        # Add CandlestickItem (note: it draws in data coords)
        cs = CandlestickItem(candle_data)
        price_plot.addItem(cs)
        pw['candlestick_item'] = cs

        # Plot EMA lines if present
        if 'ema50' in df.columns and df['ema50'].notnull().any():
            ema50_curve = price_plot.plot(x, df['ema50'].astype(float).values, pen=pg.mkPen('y', width=1.2), name='EMA50')
            pw['ema50'] = ema50_curve
        if 'ema200' in df.columns and df['ema200'].notnull().any():
            ema200_curve = price_plot.plot(x, df['ema200'].astype(float).values, pen=pg.mkPen('c', width=1.2), name='EMA200')
            pw['ema200'] = ema200_curve

        # Volume bars as BarGraphItem
        volumes = df['volume'].fillna(0).astype(float).values
        # color bars green/red based on candle direction
        brushes = []
        for o, c in zip(df['open'].astype(float).values, df['close'].astype(float).values):
            brushes.append(pg.mkBrush('g') if c >= o else pg.mkBrush('r'))
        bg = pg.BarGraphItem(x=x - 0.4, height=volumes, width=0.8, brushes=brushes)
        volume_plot.addItem(bg)
        pw['volume_bars'] = bg

        # X-axis tick labels: use a string axis
        # Create mapping from numeric x to date string for ticks (sparse)
        tx = price_plot.getAxis('bottom')
        # show a readable subset of date ticks
        n = len(x)
        if n <= 10:
            ticks = [(int(xi), dates[i].strftime("%Y-%m-%d")) for i, xi in enumerate(x)]
        else:
            step = max(1, n // 8)
            ticks = [(int(xi), dates[i].strftime("%Y-%m-%d")) for i, xi in enumerate(x) if i % step == 0]
        tx.setTicks([ticks])

        # Set ranges nicely
        price_min = float(df['low'].min())
        price_max = float(df['high'].max())
        price_plot.setYRange(price_min - (price_max - price_min) * 0.1, price_max + (price_max - price_min) * 0.1)
        volume_plot.setYRange(0, max(volumes) * 3 if volumes.size else 1)

        # Add crosshair lines back (they are items in price_plot already)
        price_plot.addItem(pw['vLine'])
        price_plot.addItem(pw['hLine'])

        # Allow mouse wheel zoom & pan (pyqtgraph provides this)
        price_plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=False)

        # final
        price_plot.repaint()
        volume_plot.repaint()


# -------------------------
# Run as standalone
# -------------------------
def main():
    app = QtWidgets.QApplication(sys.argv)

    # Optional: improve default stylesheet slightly
    app.setStyle("Fusion")

    w = ChartWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
