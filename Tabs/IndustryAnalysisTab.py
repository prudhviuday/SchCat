# IndustryAnalysisTab.py
import threading
import traceback
import numpy as np
import os
import json
from datetime import datetime
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QProgressBar,
    QScrollArea, QSizePolicy, QFrame, QHBoxLayout, QFileDialog, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
import pyqtgraph as pg
import util


class IndustryWorker(QObject):
    progress = pyqtSignal(int, int, str)  # done, total, current industry
    finished = pyqtSignal(list)  # list of (industry_name, ownership_data, sales_data)
    error = pyqtSignal(str)

    def __init__(self, data, market_ids):
        super().__init__()
        self.data = data
        self.market_ids = market_ids
        self._abort = False

    def stop(self):
        self._abort = True

    def run(self):
        try:
            results = []
            industries = sorted(self.data["Industry"].dropna().unique().tolist())
            industries = [s for s in industries if not s.startswith("BSE")]
            total = len(industries)
            for i, industry in enumerate(industries, start=1):
                if self._abort:
                    break

                stocks = self.data[self.data["Industry"] == industry]["Stock"].tolist()

                # Initialize accumulators
                all_ownership = []
                all_sales = []
                all_delivery = []
                all_traded = []
                all_RsList = []
                print(stocks)

                for stock in stocks:
                    stock_info = (stock, self.market_ids.get(stock))
                    try:
                        # util functions used as in your project (no functionality change)
                        ownership = util.getInstitutionCostFromMs(stock_info, False)
                        #print(str(stock_info)+" -> "+str(ownership))
                        sales = util.fetch_closexvol_for_stock(stock_info, False)  ####===========>fetch_Revenue_from_MS================<<<
                        #print("Here i am")
                        delivery = util.fetch_DeliveryPerc_from_NSE(stock_info, False)
                        
                        Rsgraph = util.fetch_RS_graph_from_MS(stock_info, True)
                        #print(1)
                        #print("stock RS :"+str(stock_info)+" -> "+str(Rsgraph))
                        #print("************************************************")
                    except Exception:
                        print("some error kame difficult only ")
                        continue

                    # Clean and convert ownership list
                    if ownership:
                        vals = [float(v) for _, v in ownership if v is not None]
                        if vals:
                            all_ownership.append(vals)

                    # Clean and convert sales list
                    if sales:
                        vals = [float(v) for _, v in sales if v is not None]
                        if vals:
                            all_sales.append(vals)
                            
                    # Clean and convert delivery list
                    if delivery and len(delivery)>0:
                        delvals = [float(dq) for _, dq, tq, prc in delivery if dq is not None]
                        trdvals = [float(tq) for _, dq, tq, prc in delivery if tq is not None]
                        if delvals:
                            all_delivery.append(delvals)
                            all_traded.append(trdvals)
                            
                    # Clean and convert RS list
                    if Rsgraph:
                        vals = [round(float(v),2) for v in Rsgraph if v is not None]
                        if vals:
                            all_RsList.append(vals)

                def pad_and_sum(series_list):
                    if not series_list:
                        return []
                    max_len = max(len(s) for s in series_list)
                    padded = []
                    for s in series_list:
                        if len(s) < max_len:
                            s = [s[0]] * (max_len - len(s)) + s  # <-- here last element array is added
                        padded.append(s)
                        #print(s)
                    return list(np.sum(np.array(padded), axis=0))
                    
                def Delivery_process(series_list):
                    if not series_list:
                        return []
                    max_len = max(len(s) for s in series_list)
                    padded = []
                    for s in series_list:
                        if len(s) < max_len:
                            s = [0] * (max_len - len(s)) + s  # <-- here 0 array is added
                        padded.append(s)
                        #print(s)
                    return list(np.sum(np.array(padded), axis=0))
                    
                def getTotalIndCap():
                    allcap = 1
                    for stock in stocks:
                        allcap = allcap + util.get_market_cap_of(stock)
                    return allcap
                        


                total_ownership = pad_and_sum(all_ownership)
                total_sales = pad_and_sum(all_sales)
                #print(all_sales)
                #print("[*]========================================")
                #print(total_sales)
                #print(2)
                #print("[*]========================================")
                #print("All traded "+str(all_traded))
                #print("[*]========================================")
                #print("All del "+str(all_delivery))
                #print("[*]========================================")
                #print("lengths traded "+str(len(all_traded)))
                #print("lengths delivered "+str(len(all_delivery)))
                #print("[*]======================================== starting")
                
                total_delivery_val = Delivery_process(all_delivery)
                total_traded_val = Delivery_process(all_traded)
                
                #print(3)
                total_Temp_RSLists = pad_and_sum(all_RsList)
                #print(4)
                total_indcap = getTotalIndCap()
                #print(5)
                total_RSLists = [i/total_indcap for i in total_Temp_RSLists]
                #print(6)
                
                #print("Total CAP : "+str(total_indcap))
                #print("[*]========================================")
                #print("all stock_RSLists : "+str(all_RsList))
                #print("[*]========================================")
                #print("Total total_RSLists "+str(total_RSLists))
                #print("[*]========================================")
                #print("Total delivered "+str(total_delivery_val))
                #print("[*]========================================")
                #print(7)
                
                total_delevery_perc_industry = [round(float(a*100 / b),2) for a, b in zip(total_delivery_val, total_traded_val)]
                
                #print(total_delevery_perc_industry)
                

                # convert numpy types to native python (if any)
                total_ownership = [float(x) for x in total_ownership]
                total_sales = [float(x) for x in total_sales]
                total_Rs = [round(float(x), 2) for x in total_RSLists]
                #print(8)
                results.append((industry, total_ownership, total_sales, total_delevery_perc_industry, total_Rs))
                #print(9)
                self.progress.emit(i, total, industry)

            self.finished.emit(results)

        except Exception as e:
            print(str(e))
            self.error.emit(f"IndustryWorker Error: {e}\n{traceback.format_exc()}")


class IndustryAnalysisTab(QWidget):
    """
    IndustryAnalysisTab:
     - Has file picker + Load button + Start Industry Analysis button on one row.
     - If user selects a saved results file (JSON), clicking Load loads results
       and plots them immediately without downloading.
     - If user clicks Start Industry Analysis, it runs the worker, and on finish
       the results are saved automatically to ./data/IndustryAnalysis/<ddmmyy-HHMMSS>.json
     - Adds an industry filter box to show/hide industries by typed text (partial, case-insensitive).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.gui = parent
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        # Config
        self.save_dir = Path("data") / "IndustryAnalysis"
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # ---- Top row: file selector, load, start ----
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        top_row.addWidget(QLabel("Saved results:"))

        self.file_label = QLabel("(none)")
        self.file_label.setStyleSheet("color: gray;")
        self.file_label.setMinimumWidth(250)
        top_row.addWidget(self.file_label)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.select_results_file)
        top_row.addWidget(self.browse_btn)

        self.load_btn = QPushButton("Load")
        self.load_btn.clicked.connect(self.load_results_file)
        top_row.addWidget(self.load_btn)

        # spacer
        top_row.addStretch(1)

        # Start analysis button (kept to right)
        self.start_btn = QPushButton("Start Industry Analysis")
        self.start_btn.clicked.connect(self.start_analysis)
        top_row.addWidget(self.start_btn)

        self.layout.addLayout(top_row)

        # status & progress
        status_row = QHBoxLayout()
        self.status_label = QLabel("Status: Idle")
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)

        progress_layout = QHBoxLayout()
        progress_label = QLabel("Progress:")
        progress_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        #self.progress_bar.setFixedWidth(260)
        progress_layout.addWidget(progress_label)
        progress_layout.addWidget(self.progress_bar, 1)  # stretch to fill available space

        self.layout.addLayout(progress_layout)

        # --- Industry filter input (new) ---
        filter_layout = QHBoxLayout()
        filter_label = QLabel("Filter industry:")
        filter_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.filter_box = QLineEdit()
        self.filter_box.setPlaceholderText("Type to filter industries (partial match)...")
        self.filter_box.textChanged.connect(self.filter_industries)
        # keep small width by default, but stretch as needed
        self.filter_box.setMinimumWidth(200)
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.filter_box, 1)
        self.layout.addLayout(filter_layout)

        # Scroll area that will contain the industry charts (two charts per row)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(8, 8, 8, 8)
        self.scroll_layout.setSpacing(12)
        self.scroll_content.setLayout(self.scroll_layout)
        self.scroll.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll)

        # keep references
        self.worker = None
        self.worker_thread = None

        # UI tuning constants (easy to tweak)
        self._chart_min_height = 140       # reduced height
        self._chart_max_height = 180
        self._bar_width = 0.7             # width of ownership bars

        # currently selected results file path
        self.selected_results_path = None

        # list of tuples (industry_lower, container_widget) used for filtering
        self.industry_widgets = []

    # ---------------- file selection / load ----------------
    def select_results_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select saved industry results", str(self.save_dir),
                                              "JSON Files (*.json);;All Files (*)")
        if fname:
            self.selected_results_path = fname
            self.file_label.setText(os.path.basename(fname))
            self.file_label.setStyleSheet("color: black;")

    def load_results_file(self):
        if not self.selected_results_path:
            self.status_label.setText("⚠️ No file selected.")
            return
        try:
            with open(self.selected_results_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # data expected: list of [industry, ownership_list, sales_list]
            results = []
            for item in data:
                if not isinstance(item, list) or len(item) < 3:
                    continue
                industry = item[0]
                ownership = [float(x) for x in item[1]] if item[1] else []
                sales = [float(x) for x in item[2]] if item[2] else []
                delevery_perc = [float(x) for x in item[3]] if item[3] else []
                Industry_rs = [float(x) for x in item[4]] if item[4] else []
                results.append((industry, ownership, sales, delevery_perc, Industry_rs))

            # clear UI and plot
            self._clear_plots()
            self.status_label.setText(f"🔁 Loaded results from {os.path.basename(self.selected_results_path)}")
            self.progress_bar.setValue(100)
            self.plot_industry_results(results)
        except Exception as e:
            self.status_label.setText(f"⚠️ Failed to load file: {e}")
            traceback.print_exc()

    # ---------------- start analysis ----------------
    def start_analysis(self):
        if not hasattr(self.gui, "data") or self.gui.data.empty:
            self.status_label.setText("⚠️ No data available. Please fetch stock data first.")
            return

        # disable load while running
        self.load_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.start_btn.setEnabled(False)

        self.status_label.setText("Starting analysis...")
        self.progress_bar.setValue(0)

        # Clear previous charts from scroll content
        self._clear_plots()

        # setup worker
        self.worker = IndustryWorker(self.gui.data, getattr(self.gui, "market_ids", {}))
        # connect signals
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)

        # run worker in plain thread (worker emits PyQt signals thread-safely)
        self.worker_thread = threading.Thread(target=self.worker.run, daemon=True)
        self.worker_thread.start()

    def _clear_plots(self):
        # clear any stored references for filtering
        self.industry_widgets = []
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def on_progress(self, done, total, industry):
        pct = int((done / total) * 100) if total else 0
        self.progress_bar.setValue(pct)
        self.status_label.setText(f"Analyzing {industry}... ({done}/{total})")

    def on_finished(self, results):
        # Re-enable buttons
        self.load_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.start_btn.setEnabled(True)

        self.status_label.setText("✅ Industry Analysis Complete.")
        self.progress_bar.setValue(100)

        # Save results to file for later reuse
        try:
            safe_results = []
            for industry, ownership, sales, delivery_perc, Industry_rs in results:
                # ensure python types
                o = [float(x) for x in ownership] if ownership else []
                s = [float(x) for x in sales] if sales else []
                d = [float(x) for x in delivery_perc] if delivery_perc else []
                rs = [float(x) for x in Industry_rs] if Industry_rs else []
                safe_results.append([industry, o, s, d, rs])

            ts = datetime.now().strftime("%d-%m-%Y-%H%M%S")
            fname = self.save_dir / f"industry_{ts}.json"
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(safe_results, f, ensure_ascii=False, indent=2)

            self.selected_results_path = str(fname)
            self.file_label.setText(os.path.basename(fname))
            self.file_label.setStyleSheet("color: black;")
            self.status_label.setText(f"✅ Analysis complete — saved to {os.path.basename(fname)}")
        except Exception as e:
            # non-fatal; continue to plotting
            self.status_label.setText(f"⚠️ Analysis done but failed to save: {e}")
            traceback.print_exc()

        # plot results
        self.plot_industry_results(results)

    def on_error(self, text):
        # Re-enable buttons
        self.load_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.start_btn.setEnabled(True)

        self.status_label.setText(f"⚠️ Error: {text}")

    def plot_industry_results(self, results):
        """
        Build a scrollable list where each industry has a 2x2 panel:
            Top row:    [Ownership (bars)] | [Delivery % (line)]
            Bottom row: [Sales (line)]     | [Industry RS (line)]
        """
        try:
            i = 1

            def _setup_locked_plot(plot_widget):
                """Disable user interactions and forward wheel scroll to the main scroll area."""
                plot_widget.setMouseEnabled(x=False, y=False)
                plot_widget.wheelEvent = lambda event: self.scroll.wheelEvent(event)
                plot_widget.setMenuEnabled(False)
                vb = plot_widget.getViewBox()
                try:
                    vb.setMouseEnabled(x=False, y=False)
                except Exception:
                    pass
                return vb

            def _set_sparse_ticks(axis, n):
                if n > 0:
                    step = max(1, n // 8)
                    ticks = [(idx, str(idx)) for idx in range(n)][::step]
                    axis.setTicks([ticks])

            def _plot_line(plot_widget, data, pen_color, fixed_y=None):
                """
                Plot a line series and lock axes.
                fixed_y: tuple(min_y, max_y) or None
                """
                vb = _setup_locked_plot(plot_widget)

                if data is not None and len(data) > 0:
                    xs = list(range(len(data)))
                    ys = list(data)

                    plot_widget.plot(
                        xs, ys,
                        pen=pg.mkPen(color=pen_color, width=2),
                        #symbol='o'
                    )

                    axis = plot_widget.getAxis('bottom')
                    _set_sparse_ticks(axis, len(xs))

                    x_min, x_max = 0, max(0, len(xs) - 1)

                    if fixed_y is not None:
                        y_min, y_max = fixed_y
                    else:
                        y_min = min(ys)
                        y_max = max(ys) * 1.1 if max(ys) != 0 else 1.0

                    vb.setXRange(x_min, x_max, padding=0)
                    vb.setYRange(y_min, y_max, padding=0)

                    try:
                        vb.setLimits(
                            xMin=x_min, xMax=x_max,
                            minXRange=max(1, x_max - x_min),
                            maxXRange=(x_max - x_min + 1),
                            yMin=y_min, yMax=y_max
                        )
                    except Exception:
                        pass
                else:
                    no_data = pg.TextItem("No data", anchor=(0.5, 0.5))
                    plot_widget.addItem(no_data)
                    no_data.setPos(0.5, 0.5)
                    try:
                        vb.setRange(xRange=(0, 1), yRange=(0, 1), padding=0)
                    except Exception:
                        pass

            def _plot_bar(plot_widget, data, brush_color):
                """Plot bar chart and lock axes."""
                vb = _setup_locked_plot(plot_widget)

                if data is not None and len(data) > 0:
                    x = list(range(len(data)))
                    heights = list(data)

                    bar = pg.BarGraphItem(
                        x=x,
                        height=heights,
                        width=self._bar_width,
                        brush=brush_color
                    )
                    plot_widget.addItem(bar)

                    axis = plot_widget.getAxis('bottom')
                    _set_sparse_ticks(axis, len(x))

                    x_min, x_max = 0, max(0, len(x) - 1)
                    y_min = min(0, min(heights))
                    y_max = max(heights) * 1.1 if max(heights) != 0 else 1.0

                    vb.setXRange(x_min, x_max, padding=0)
                    vb.setYRange(y_min, y_max, padding=0)

                    try:
                        vb.setLimits(
                            xMin=x_min, xMax=x_max,
                            minXRange=max(1, x_max - x_min),
                            maxXRange=(x_max - x_min + 1),
                            yMin=y_min, yMax=y_max
                        )
                    except Exception:
                        pass
                else:
                    no_data = pg.TextItem("No data", anchor=(0.5, 0.5))
                    plot_widget.addItem(no_data)
                    no_data.setPos(0.5, 0.5)
                    try:
                        vb.setRange(xRange=(0, 1), yRange=(0, 1), padding=0)
                    except Exception:
                        pass

            for industry, ownership, sales, delivery_perc, Industry_rs in results:
                # container per industry
                container = QFrame()
                container.setFrameShape(QFrame.StyledPanel)
                container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

                outer_layout = QVBoxLayout(container)
                outer_layout.setContentsMargins(6, 6, 6, 6)
                outer_layout.setSpacing(10)

                # ---------------------------
                # Top row: Ownership | Delivery
                # ---------------------------
                top_row = QHBoxLayout()
                top_row.setContentsMargins(0, 0, 0, 0)
                top_row.setSpacing(12)

                own_plot = pg.PlotWidget(title=f"{i} {industry} - Institutional Ownership (%)")
                own_plot.setMinimumHeight(self._chart_min_height)
                own_plot.setMaximumHeight(self._chart_max_height)
                own_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                own_plot.showGrid(x=True, y=True, alpha=0.3)
                _plot_bar(own_plot, ownership, brush_color=(31, 119, 180))

                delivery_plot = pg.PlotWidget(title=f"Delivery %")
                delivery_plot.setMinimumHeight(self._chart_min_height)
                delivery_plot.setMaximumHeight(self._chart_max_height)
                delivery_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                delivery_plot.showGrid(x=True, y=True, alpha=0.3)
                _plot_line(delivery_plot, delivery_perc, pen_color=(0, 150, 0))

                top_row.addWidget(own_plot, 1)
                top_row.addWidget(delivery_plot, 1)

                # ---------------------------
                # Bottom row: Sales | Industry RS
                # ---------------------------
                bottom_row = QHBoxLayout()
                bottom_row.setContentsMargins(0, 0, 0, 0)
                bottom_row.setSpacing(12)

                sales_plot = pg.PlotWidget(title=f"Revenue (Total)")
                sales_plot.setMinimumHeight(self._chart_min_height)
                sales_plot.setMaximumHeight(self._chart_max_height)
                sales_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                sales_plot.showGrid(x=True, y=True, alpha=0.3)
                _plot_line(sales_plot, sales, pen_color=(128, 0, 128))
                
                
                latestRs = Industry_rs[-1] if len(Industry_rs)>0 else 1
                rs_plot = pg.PlotWidget(title=f"RS : {latestRs}/100(D)")
                rs_plot.setMinimumHeight(self._chart_min_height)
                rs_plot.setMaximumHeight(self._chart_max_height)
                rs_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                rs_plot.showGrid(x=True, y=True, alpha=0.3)
                _plot_line(rs_plot, Industry_rs, pen_color=(255, 140, 0), fixed_y=(0, 100))

                bottom_row.addWidget(sales_plot, 1)
                bottom_row.addWidget(rs_plot, 1)

                # add rows to industry container
                outer_layout.addLayout(top_row)
                outer_layout.addLayout(bottom_row)

                # add the container to the scroll area
                self.scroll_layout.addWidget(container)

                # store for filtering
                self.industry_widgets.append((industry.lower(), container))

                i += 1

            # add stretch at the end to push items up
            self.scroll_layout.addStretch(1)

        except Exception as e:
            self.status_label.setText(f"⚠️ Error plotting results: {e}")
            traceback.print_exc()

    # ---------------- industry filter ----------------
    def filter_industries(self, text):
        """
        Show/hide industry containers based on partial, case-insensitive match.
        If text is empty, all industries are shown.
        """
        q = (text or "").strip().lower()
        if not hasattr(self, "industry_widgets") or not self.industry_widgets:
            return
        for name, widget in self.industry_widgets:
            if not q:
                widget.setVisible(True)
            else:
                widget.setVisible(q in name)

