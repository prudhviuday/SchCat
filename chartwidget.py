# chartwidget.py
"""
Reusable ChartWidget: candlestick + volume chart using pyqtgraph
Features:
 - Last N candles visible by default
 - Candlestick color-coded (green=up, red=down)
 - Volume bars below price chart
 - Separate vertical and horizontal zoom/pan
 - Limits on zooming and panning (X/Y)
 - Sparse X-axis labels
"""
import logging
from typing import Optional, Dict

import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import Qt

# Ensure consistent pyqtgraph styling
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

logging.getLogger(__name__).addHandler(logging.NullHandler())


class ChartWidget(QWidget):
    def __init__(self, parent=None, title: str = "", default_visible: int = 200):
        super().__init__(parent)
        self.default_visible = int(default_visible)

        # GraphicsLayoutWidget holds 2 plots: price (top) and volume (bottom)
        self.container = pg.GraphicsLayoutWidget(parent=self)

        # Top: price plot
        self.price_plot = self.container.addPlot(row=0, col=0)
        self.price_plot.showGrid(x=True, y=True)
        self.price_plot.setLabel("left", "Price")
        self.price_plot.setMouseEnabled(x=True, y=True)

        # Bottom: volume plot
        self.vol_plot = self.container.addPlot(row=1, col=0)
        self.vol_plot.setXLink(self.price_plot)
        self.vol_plot.setMaximumHeight(110)
        self.vol_plot.setLabel("left", "Vol")
        self.vol_plot.setMouseEnabled(x=False, y=False)

        # Arrange stretch factors
        try:
            self.container.ci.layout.setRowStretchFactor(0, 3)
            self.container.ci.layout.setRowStretchFactor(1, 1)
        except Exception:
            pass

        # Keep track of items
        self._price_items = []
        self._vol_items = []
        self._title = title
        if title:
            self.setTitle(title)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.container)

    def setTitle(self, title: str):
        self._title = title
        self.price_plot.setTitle(title)

    def clear(self):
        try:
            for it in self._price_items:
                self.price_plot.removeItem(it)
            for it in self._vol_items:
                self.vol_plot.removeItem(it)
        except Exception:
            self.price_plot.clear()
            self.vol_plot.clear()
        self._price_items = []
        self._vol_items = []

    def plot(self, prepared: Optional[Dict]):
        """
        prepared: dict with keys 'x','dates','open','high','low','close','volume'
        """
        if not prepared:
            self.clear()
            self.price_plot.addItem(pg.TextItem("No data", anchor=(0.5, 0.5)))
            return

        try:
            x = np.array(prepared["x"], dtype=float)
            open_a = np.array(prepared["open"], dtype=float)
            high_a = np.array(prepared["high"], dtype=float)
            low_a = np.array(prepared["low"], dtype=float)
            close_a = np.array(prepared["close"], dtype=float)
            vol_a = np.array(prepared["volume"], dtype=float)
            labels = prepared.get("dates", None)
        except Exception as e:
            logging.exception("ChartWidget.plot: invalid prepared data: %s", e)
            self.clear()
            self.price_plot.addItem(pg.TextItem("Invalid data", anchor=(0.5, 0.5)))
            return

        self.clear()
        n = len(x)
        if n == 0:
            self.price_plot.addItem(pg.TextItem("No points", anchor=(0.5, 0.5)))
            return

        # -------- Wicks --------
        wicks_x = np.empty(n * 3)
        wicks_y = np.empty(n * 3)
        for i in range(n):
            wicks_x[3 * i] = x[i]
            wicks_x[3 * i + 1] = x[i]
            wicks_x[3 * i + 2] = np.nan
            wicks_y[3 * i] = low_a[i]
            wicks_y[3 * i + 1] = high_a[i]
            wicks_y[3 * i + 2] = np.nan
        wick_pen = pg.mkPen(color=(100, 100, 100), width=1)
        wick_item = self.price_plot.plot(wicks_x, wicks_y, pen=wick_pen)
        self._price_items.append(wick_item)

        # -------- Candles --------
        candle_w = 0.6
        body_height = np.abs(close_a - open_a)
        y0 = np.minimum(open_a, close_a)

        bull_mask = close_a >= open_a
        bear_mask = ~bull_mask

        if bull_mask.any():
            xb = x[bull_mask]
            hb = body_height[bull_mask]
            y0b = y0[bull_mask]
            bar_bull = pg.BarGraphItem(x=xb, height=hb, width=candle_w, y0=y0b, brush=(0, 180, 0))
            self.price_plot.addItem(bar_bull)
            self._price_items.append(bar_bull)

        if bear_mask.any():
            xr = x[bear_mask]
            hr = body_height[bear_mask]
            y0r = y0[bear_mask]
            bar_bear = pg.BarGraphItem(x=xr, height=hr, width=candle_w, y0=y0r, brush=(200, 0, 0))
            self.price_plot.addItem(bar_bear)
            self._price_items.append(bar_bear)

        # -------- Volume --------
        vol_bar = pg.BarGraphItem(x=x, height=vol_a, width=candle_w * 0.9, y0=0,
                                  brush=(120, 120, 120, 200))
        self.vol_plot.addItem(vol_bar)
        self._vol_items.append(vol_bar)

        # -------- X-axis ticks --------
        if labels:
            step = max(1, len(labels) // 8)
            ticks = [(int(xi), labels[i]) for i, xi in enumerate(x) if i % step == 0]
            self.price_plot.getAxis("bottom").setTicks([ticks])

        # -------- ViewBox limits and default ranges --------
        vb = self.price_plot.getViewBox()

        # X-limits
        x_min = float(np.min(x)) - 0.5
        x_max = float(np.max(x)) + 0.5
        min_visible = 3
        minXRange = max(1.0, min_visible - 0.1)
        maxXRange = max(1.0, (x_max - x_min) + 1.0)

        # Y-limits (20% padding)
        price_min = float(np.min(low_a))
        price_max = float(np.max(high_a))
        price_range = price_max - price_min
        y_min_limit = price_min - price_range * 0.2
        y_max_limit = price_max + price_range * 0.2
        pad = price_range * 0.12  # initial padding for display

        # Apply limits to ViewBox
        vb.setLimits(
            xMin=x_min, xMax=x_max,
            minXRange=minXRange, maxXRange=maxXRange,
            yMin=y_min_limit, yMax=y_max_limit
        )

        # Default visible last N candles
        default_n = min(self.default_visible, n)
        last_idx = int(np.max(x))
        left = float(max(x_min, last_idx - default_n + 1)) - 0.2
        right = float(x_max)
        vb.setXRange(left, right, padding=0)
        vb.setYRange(price_min - pad, price_max + pad, padding=0)

        # Volume Y-range
        max_vol = float(np.max(vol_a)) if vol_a.size > 0 else 0.0
        vol_top = max_vol * 1.15 if max_vol > 0 else 1.0
        self.vol_plot.setYRange(0, vol_top, padding=0)
