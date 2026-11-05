# rightpanel.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QFrame
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import pyqtgraph as pg
import util
from datetime import datetime
import traceback
import os

# ------------------ Worker Thread ------------------
class RightPanelWorker(QThread):
    data_ready = pyqtSignal(dict)  # emits {"roce":..., "delivery":..., "revenue":..., "eps":...}
    error_occurred = pyqtSignal(str)

    def __init__(self, stock_info):
        super().__init__()
        self.stock_info = stock_info

    def run(self):
        try:
            stock_name, stock_id = self.stock_info
            roce = util.fetch_ROCE_from_MS(self.stock_info)
            delivery = util.getInstitutionOwnershipFromMs(self.stock_info)
            revenue = util.fetch_Sales_acc_from_MS(self.stock_info)
            eps = util.fetch_EPS_acc_from_MS(self.stock_info)
            self.data_ready.emit({
                "roce": roce,
                "delivery": delivery,
                "revenue": revenue,
                "eps": eps
            })
        except Exception as e:
            self.error_occurred.emit(str(e))
            traceback.print_exc()


# ------------------ Right Panel ------------------
class RightPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        self.frame = QFrame(self)
        self.layout().addWidget(self.frame)
        self.frame.setLayout(QVBoxLayout())

        # ---- Stock Details Labels ----
        self.info_labels = {}
        info_fields = ["Stock", "Industry", "MasterScore", "RS", "EPS",
                       "AccDis", "PE", "ROE", "EPSGrowth", "CashFlow", "Stability", "NikScore"]
        details_grid = QGridLayout()
        self.frame.layout().addLayout(details_grid)
        for i, field in enumerate(info_fields):
            lbl_name = QLabel(f"{field}:")
            lbl_name.setStyleSheet("font-weight:bold;")
            lbl_value = QLabel("—")
            details_grid.addWidget(lbl_name, i // 3, (i % 3) * 2)
            details_grid.addWidget(lbl_value, i // 3, (i % 3) * 2 + 1)
            self.info_labels[field] = lbl_value

        # ---- ROCE Graph ----
        self.roce_plot = pg.PlotWidget(title="ROCE (%)")
        self.frame.layout().addWidget(self.roce_plot)

        # ---- Delivery % Graph ----
        self.delivery_plot = pg.PlotWidget(title="Institution Ownership %")
        self.frame.layout().addWidget(self.delivery_plot)

        # ---- Revenue / EPS Graph ----
        self.revenue_plot = pg.PlotWidget(title="Revenue / EPS")
        self.frame.layout().addWidget(self.revenue_plot)

    # ------------------ Update RightPanel ------------------
    def update(self, stock_name, row, market_ids, chart_info_labels=None):
        try:
            # ---- Update Labels ----
            for field, lbl in self.info_labels.items():
                val = row.get(field, "—")
                lbl.setText(str(val))
                lbl.setStyleSheet(f"color:{self.get_color_for_field(field, val)}; font-weight:bold;")

            # ---- Start background worker ----
            stock_info = (stock_name, market_ids.get(stock_name))
            self.worker = RightPanelWorker(stock_info)
            self.worker.data_ready.connect(self.plot_all_graphs)
            self.worker.error_occurred.connect(lambda e: print(f"RightPanel error: {e}"))
            self.worker.start()
        except Exception as e:
            print(f"Error updating RightPanel: {e}")
            traceback.print_exc()

    # ------------------ Color Logic ------------------
    def get_color_for_field(self, field, value):
        try:
            num = float(value)
        except:
            return "black"

        if field in ["RS", "EPS"]:
            if num < 70: return "red"
            elif num < 80: return "orange"
            else: return "green"
        if field == "PE":
            return "green" if 0 < num < 25 else "red"
        if field == "ROE":
            return "green" if num >= 15 else "red"
        if field == "EPSGrowth":
            return "green" if num >= 25 else "red"
        if field in ["MasterScore", "AccDis", "CashFlow", "Stability"]:
            if num >= 70: return "green"
            elif num >= 50: return "orange"
            else: return "red"
        return "black"

    # ------------------ Plotting ------------------
    def plot_all_graphs(self, data):
        self.plot_roce(data["roce"])
        self.plot_delivery(data["delivery"])
        self.plot_revenue_eps(data["revenue"], data["eps"])

    # ---- ROCE ----
    def plot_roce(self, roce_data):
        self.roce_plot.clear()
        if not roce_data:
            self.roce_plot.addItem(pg.TextItem("No ROCE data available", anchor=(0.5,0.5)))
            return
        roce_data_sorted = sorted([(int(y), float(r)) for y, r in roce_data], key=lambda x: x[0])
        years = [y for y,r in roce_data_sorted]
        values = [r for y,r in roce_data_sorted]
        color_list = [(0,200,0) if r>=15 else (255,165,0) if r>=10 else (200,0,0) for r in values]
        color_list = color_list[1:]+[(255,165,0)]
        for i in range(1, len(years)):
            self.roce_plot.plot([years[i-1], years[i]], [values[i-1], values[i]],
                                pen=pg.mkPen(color=color_list[i-1], width=2), symbol='o')

    # ---- Delivery ----
    def plot_delivery(self, delivery_data):
        self.delivery_plot.clear()
        if not delivery_data:
            self.delivery_plot.addItem(pg.TextItem("No Ownership % data", anchor=(0.5,0.5)))
            return
        date_val_pairs = [(datetime.strptime(d,"%d-%b-%y"), float(v)) for d,v in delivery_data if v is not None]
        date_val_pairs.sort()
        x_vals = list(range(len(date_val_pairs)))
        y_vals = [v for d,v in date_val_pairs]
        bar = pg.BarGraphItem(x=x_vals, height=y_vals, width=0.8, brush=(31,119,180))
        self.delivery_plot.addItem(bar)
        # X-axis labels
        x_axis = self.delivery_plot.getAxis('bottom')
        labels = [(i, d.strftime("%d-%b-%y")) for i,(d,_) in enumerate(date_val_pairs)]
        x_axis.setTicks([labels[::max(1,len(labels)//10)]])

    # ---- Revenue / EPS ----

    def plot_revenue_eps(self, revenue_data, eps_data):
        try:
            # Clear previous plots
            self.revenue_plot.clear()

            # Filter valid revenue and EPS data
            rev_valid = [(d, float(v)) for d, v in revenue_data if v is not None]
            eps_valid = [(d, float(v)) for d, v in eps_data if v is not None]

            if not rev_valid and not eps_valid:
                self.revenue_plot.addItem(pg.TextItem("No Revenue or EPS data", anchor=(0.5, 0.5)))
                return

            # X positions (numeric)
            x_rev = list(range(len(rev_valid)))
            y_rev = [v for _, v in rev_valid]

            x_eps = list(range(len(eps_valid)))
            y_eps = [v for _, v in eps_valid]

            # Plot revenue line
            if rev_valid:
                rev_curve = pg.PlotDataItem(
                    x_rev, y_rev,
                    pen=pg.mkPen(color='purple', width=2),
                    symbol='o', symbolBrush='purple',
                    name='Sales'
                )
                self.revenue_plot.addItem(rev_curve)

            # Plot EPS line
            if eps_valid:
                eps_curve = pg.PlotDataItem(
                    x_eps, y_eps,
                    pen=pg.mkPen(color='orange', width=2),
                    symbol='s', symbolBrush='orange',
                    name='EPS'
                )
                self.revenue_plot.addItem(eps_curve)

            # X-axis labels as dates
            axis = self.revenue_plot.getAxis('bottom')
            if rev_valid:
                # Show every nth label if too many
                step = max(1, len(x_rev)//10)
                ticks = [(i, d.strftime("%Y-%m-%d")) for i, (d, _) in enumerate(rev_valid)][::step]
                axis.setTicks([ticks])

            self.revenue_plot.setLabel('left', 'Value')
            self.revenue_plot.setLabel('bottom', 'Year')
            self.revenue_plot.showGrid(x=True, y=True, alpha=0.3)
            self.revenue_plot.addLegend(offset=(10,10))

        except Exception as e:
            print(f"Error plotting Revenue/EPS: {e}")

