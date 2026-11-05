# ChartTab.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel
from PyQt5.QtCore import Qt
import pyqtgraph as pg
import threading
import pandas as pd
import chartengine  # your module to fetch chart data

class ChartTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # Title label
        self.title_label = QLabel("📊 Enter stock name and press Go")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.title_label)

        # Grid layout for 4 charts (2x2)
        self.chart_grid = QGridLayout()
        self.layout.addLayout(self.chart_grid)
        self.charts = []

    # -------------------------- Load charts --------------------------
    def load_charts(self, stock_name):
        """Fetch chart data in a background thread."""
        threading.Thread(target=self._fetch_and_plot, args=(stock_name,), daemon=True).start()

    def _fetch_and_plot(self, stock_name):
        try:
            data_dict = {
                "Weekly": chartengine.fetch_chart_data(stock_name, "1W"),
                "Daily": chartengine.fetch_chart_data(stock_name, "1D"),
                "Hourly": chartengine.fetch_chart_data(stock_name, "1H"),
                "5-min": chartengine.fetch_chart_data(stock_name, "5m"),
            }
            self._plot_all_charts(stock_name, data_dict)
        except Exception as e:
            self.title_label.setText(f"⚠️ Error: {e}")

    # -------------------------- Plot all charts --------------------------
    def _plot_all_charts(self, stock_name, data_dict):
        # Clear existing charts
        for chart in self.charts:
            self.chart_grid.removeWidget(chart)
            chart.deleteLater()
        self.charts.clear()

        self.title_label.setText(f"✅ Showing charts for: {stock_name}")

        # Create charts in 2x2 grid
        for i, (tf, df) in enumerate(data_dict.items()):
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            if not all(c in df.columns for c in ['open', 'high', 'low', 'close']):
                continue

            chart_widget = self._create_chart(df, tf)
            r, c = divmod(i, 2)
            self.chart_grid.addWidget(chart_widget, r, c)
            self.charts.append(chart_widget)

    # -------------------------- Create a single chart --------------------------
    def _create_chart(self, df, title):
        """Interactive OHLC chart with zoom & pan using PyQtGraph."""
        df = df.copy()
        df.reset_index(inplace=True)

        plot = pg.PlotWidget(title=title)
        plot.showGrid(x=True, y=True)
        plot.setLabel('left', 'Price')
        plot.setLabel('bottom', 'Time')

        candle_width = 0.6
        for i, row in df.iterrows():
            open_, high, low, close = row['open'], row['high'], row['low'], row['close']
            color = 'g' if close >= open_ else 'r'

            # Wick
            plot.addItem(pg.PlotDataItem([i, i], [low, high], pen=pg.mkPen(color=color, width=1)))
            # Candle body
            plot.addItem(pg.BarGraphItem(x=[i], height=[close - open_], width=candle_width, brushes=color, y0=open_))

        # Enable mouse interactions
        plot.setMouseEnabled(x=True, y=True)
        plot.setMenuEnabled(True)

        return plot
