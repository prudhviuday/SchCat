# guimain2.py
import sys
import threading
import traceback
import pandas as pd
import subprocess
import os
import socket
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QAbstractItemView,
    QDialog, QGridLayout, QSizePolicy, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer

from Tabs.rightpanel import RightPanel
from Tabs.chartpanel import ChartPanel
from Tabs.portfolioTab import PortfolioTab
from Tabs.AnalysisTab import AnalysisTab   # <<< Analysis tab import
from Tabs.ResearchTab import ResearchTab
from Tabs.IndustryAnalysisTab import IndustryAnalysisTab
from Tabs.MarketPulseTab import MarketPulseTab

import helper  # <-- moved util/helper logic here
from helper import FilterDialog


# ---------------- Worker (runs in QThread) ----------------
class FetchDataWorker(QObject):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(list, dict)
    error = pyqtSignal(str)

    def __init__(self, max_workers=8):
        super().__init__()
        self.max_workers = max_workers

    def run(self):
        """Runs in background QThread to fetch all stocks concurrently."""
        try:
            helper.run_fetch_data_worker(
                self.max_workers, self.progress, self.finished, self.error
            )
        except Exception as e:
            tb = traceback.format_exc()
            self.error.emit(f"{e}\n{tb}")


# ---------------- Main GUI ----------------
class MarketSmithGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SchCAT Market Analyzer")
        self.setGeometry(50, 50, 1400, 750)

        self.active_query = None
        self.active_watchlist = None
        self.layout = QVBoxLayout(self)
        self.tab_control = QTabWidget(self)
        self.layout.addWidget(self.tab_control)

        self.tab_stocks = QWidget()
        self.tab_chart = QWidget()
        self.tab_control.addTab(self.tab_stocks, "Stocks")
        self.tab_control.addTab(self.tab_chart, "Chart")
        
        # Analysis tab will be created in setup_analysis_tab
        self.tab_analysis = None

        self._sort_state = {}
        self._fade_timer = None
        self._fade_steps = 20
        self._fade_step_idx = 0

        self._spinner_timer = QTimer()
        self._spinner_timer.setInterval(350)
        self._spinner_timer.timeout.connect(self._advance_spinner)
        self._spinner_state = 0

        # Node process attributes (kept simple)
        self._node_process = None
        self._node_check_timer = QTimer()
        self._node_check_timer.timeout.connect(self._check_node_status)
        # start checks (5s initial interval; _check_node_status will switch to 60s after first run)
        self._node_check_timer.start(5000)
        self._node_probe_port = 3000  # CHANGE THIS if your Node app listens on a different port

        self.setup_stocks_tab()
        self.setup_chart_tab()
        self.setup_analysis_tab()   # << added Analysis tab setup
        
        self.tab_industry = IndustryAnalysisTab(self)  # Industry Stocks
        self.tab_control.addTab(self.tab_industry, "Industry Analysis")
        
        self.tab_research = ResearchTab(self)
        self.tab_control.addTab(self.tab_research, "Querys")
        
        self.tab_market = MarketPulseTab(self)
        self.tab_control.addTab(self.tab_market, "Market")
        
        self.portfolio_chart = QWidget()
        self.tab_control.addTab(self.portfolio_chart, "Portfolio")
        self.setup_portfolio_tab()
        
        # advanced filter storage (so dialog can pre-populate if needed)
        self.advanced_filters = {}

    # ------------------ Stocks Tab ------------------
    def setup_stocks_tab(self):
        layout = QVBoxLayout(self.tab_stocks)
        control_layout = QHBoxLayout()
        layout.addLayout(control_layout)

        # ---- Controls ----
        self.start_btn = QPushButton("Start Fetching Data")
        self.start_btn.clicked.connect(self.start_fetch)
        control_layout.addWidget(self.start_btn)

        self.spinner_label = QLabel("")
        self.spinner_label.setFixedWidth(60)
        control_layout.addWidget(self.spinner_label)

        control_layout.addWidget(QLabel("🔍 Search Stock:"))
        self.search_input = QLineEdit()
        self.search_input.setFixedWidth(350)
        self.search_input.textChanged.connect(self.filter_table)
        control_layout.addWidget(self.search_input)
        
        self.settings_btn = QPushButton("⚙️ Settings")
        self.settings_btn.clicked.connect(self.open_filter_settings)
        control_layout.addWidget(self.settings_btn)

        self.download_btn = QPushButton("⬇️ Download")
        self.download_btn.clicked.connect(self.download_filtered_list)
        control_layout.addWidget(self.download_btn)

        # ---- Node Server Button (compact) ----
        self.node_btn = QPushButton("⚡ Start Node Server")
        self.node_btn.setStyleSheet("background-color: red; color: white; font-weight:bold;")
        self.node_btn.setToolTip("Start/Stop node server (CRIP4/catserver.exe or node app.js)")
        self.node_btn.clicked.connect(self.toggle_node_server)
        control_layout.addWidget(self.node_btn)

        # ---- Multi-select Query ----
        control_layout.addWidget(QLabel("             Query:"))
        self.allqueries = helper.getAllQueries()
        self.query_combo = helper.MultiSelectDropdown(list(self.allqueries.keys()))
        control_layout.addWidget(self.query_combo)

        self.query_btn = QPushButton("Go")
        self.query_btn.clicked.connect(self.toggle_query)
        control_layout.addWidget(self.query_btn)

        control_layout.addWidget(QLabel("             Watchlist:"))
        self.watch_combo = QComboBox()
        self.watch_combo.addItem("None")
        self.allwatchlists = helper.getAllWatchlists()
        self.watch_combo.addItems(list(self.allwatchlists.keys()))
        control_layout.addWidget(self.watch_combo)
        self.watch_btn = QPushButton("Go")
        self.watch_btn.clicked.connect(self.toggle_watchlist)
        control_layout.addWidget(self.watch_btn)

        # ---- Status + Visible count on same line ----
        status_row = QHBoxLayout()
        self.status_label = QLabel("Status: Idle")
        status_row.addWidget(self.status_label)

        status_row.addStretch(1)  # pushes count to the right

        # visible / total counter (right side)
        self.stock_count_label = QLabel("0/0")
        self.stock_count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.stock_count_label.setStyleSheet("color: #333333; font-weight:bold;")
        status_row.addWidget(self.stock_count_label)

        layout.addLayout(status_row)

        # ---- Main Content ----
        main_layout = QHBoxLayout()
        layout.addLayout(main_layout)

        # Left Table
        self.table = QTableWidget()
        self.columns = ["Stock", "Industry", "GroupRank", "RS", "EPS", "MasterScore", "AccDis", "PE", "PEG", "FScore", "ROCE", "NikScore"]
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)  # make non-editable
        self.table.itemSelectionChanged.connect(self.on_row_select)
        self.table.cellDoubleClicked.connect(self.on_row_double_click)  # new line
        main_layout.addWidget(self.table)

        header = self.table.horizontalHeader()
        header.sectionClicked.connect(self.on_header_clicked)

        self.right_panel = RightPanel()
        main_layout.addWidget(self.right_panel)

        main_layout.setStretch(0, 5)  # left = index 0
        main_layout.setStretch(1, 5)  # right = index 1

        self.data = pd.DataFrame()
        self.filtered_data = pd.DataFrame()

        self._fetch_thread = None
        self._fetch_worker = None
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.table.installEventFilter(self)

    # ------------------ Chart Tab ------------------
    def setup_chart_tab(self):
        layout = QVBoxLayout(self.tab_chart)
        self.chart_panel = ChartPanel()
        layout.addWidget(self.chart_panel)
        
    # ------------------ Portfolio Tab ------------------
    def setup_portfolio_tab(self):
        layout = QVBoxLayout(self.portfolio_chart)
        self.portfolio_panel = PortfolioTab()
        layout.addWidget(self.portfolio_panel)

    # ------------------ Analysis Tab (minimal integration) ------------------
    def setup_analysis_tab(self):
        """
        Create and add the AnalysisTab. It expects a callable that returns the main DataFrame.
        We pass a lambda returning self.data so AnalysisTab can filter by industry/stock.
        """
        try:
            # pass a callable returning the main dataframe
            self.tab_analysis = AnalysisTab(parent=self, get_stocks_func=lambda: self.data)
            self.tab_control.addTab(self.tab_analysis, "Industry Stocks")
        except Exception as e:
            # if AnalysisTab import / init fails, log and continue (do not break other functionality)
            print("Could not initialize AnalysisTab:", e)

    # ------------------ Fetch Data (QThread) ------------------
    def start_fetch(self):
        helper.start_fetch_thread(
            self, FetchDataWorker, self._on_fetch_progress, self._on_fetch_finished, self._on_fetch_error
        )

    def _on_fetch_progress(self, done, total):
        self.status_label.setText(f"⏳ Fetching data... {done}/{total}")

    def _on_fetch_error(self, text):
        helper.handle_fetch_error(self, text)

    def _on_fetch_finished(self, results, market_ids):
        helper.handle_fetch_finished(self, results, market_ids)
        # If analysis tab exists, let it refresh its completer / UI if implemented
        try:
            if self.tab_analysis and hasattr(self.tab_analysis, "update_industry_completer"):
                self.tab_analysis.update_industry_completer()
        except Exception:
            pass

    # ---------------- spinner ----------------
    def _advance_spinner(self):
        self._spinner_state = (self._spinner_state + 1) % 4
        self.spinner_label.setText("." * self._spinner_state)

    # ---------------- fade animation ----------------
    def _fade_to_green(self, text):
        helper.fade_to_green(self, text)

    def _fade_step(self):
        helper.fade_step(self)
        
    def download_filtered_list(self):
        try:
            df = getattr(self, "filtered_data", None)

            if df is None or df.empty:
                df = getattr(self, "data", None)

            if df is None or df.empty:
                QMessageBox.information(self, "No data", "There is no filtered data to download.")
                return

            file_path, selected_filter = QFileDialog.getSaveFileName(
                self,
                "Save filtered list",
                "filtered_list.xlsx",
                "Excel Files (*.xlsx);;CSV Files (*.csv)"
            )

            if not file_path:
                return

            if file_path.lower().endswith(".csv"):
                df.to_csv(file_path, index=False)
            else:
                if not file_path.lower().endswith(".xlsx"):
                    file_path += ".xlsx"
                df.to_excel(file_path, index=False)

            QMessageBox.information(self, "Saved", f"Filtered list saved to:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{e}")

    # ------------------ Table ------------------
    def update_table(self, df):
        # Call helper's update routine (keeps all previous functionality unchanged)
        helper.update_table(self, df)

        # Now update visible / total counter
        try:
            total = len(self.data) if getattr(self, "data", None) is not None else 0
            visible = len(df) if df is not None else 0
            # update label
            self.stock_count_label.setText(f"{visible}/{total}")
        except Exception:
            # be resilient — don't let UI break
            pass

    def filter_table(self):
        helper.filter_table(self)

    # ------------------ Query / Watchlist ------------------
    def toggle_query(self):
        helper.toggle_query(self)

    def toggle_watchlist(self):
        helper.toggle_watchlist(self)

    def refresh_watchlists(self):
        helper.refresh_watchlists(self)

    def apply_filters(self):
        helper.apply_filters(self)

    # ------------------ Row Selection ------------------
    def on_row_select(self):
        helper.on_row_select(self)

    # ------------------ Row double click ------------------
    def on_row_double_click(self, row, column):
        helper.on_row_double_click(self, row, column)

    # ------------------ Sorting ------------------
    def on_header_clicked(self, logicalIndex):
        helper.on_header_clicked(self, logicalIndex)

    # ------------------ Add to watchlist ------------------
    def eventFilter(self, source, event):
        return helper.eventFilter(self, source, event)

    def add_to_watchlist_on_keypress(self, watchlist_number=0):
        helper.add_to_watchlist_on_keypress(self, watchlist_number=watchlist_number)

    def _add_to_watchlist_thread(self, watchlist, stock_name):
        helper.add_to_watchlist_thread(self, watchlist, stock_name)

    def _fade_status(self, text):
        helper.fade_status(self, text)

    # ------------------ Advanced filter dialog handlers ------------------
    def open_filter_settings(self):
        numeric_cols = ["GroupRank", "RS", "EPS", "MasterScore", "AccDis", "FScore", "PE", "PEG", "ROCE", "NikScore"]
        dlg = FilterDialog(self, numeric_cols)

        # pre-populate if we have previous values
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
        """
        Read min/max from dialog and filter self.data accordingly.
        Keeps filtered_data updated and updates table.
        """
        if self.data is None or self.data.empty:
            dlg.reject()
            return

        df = self.data.copy()

        numeric_cols = list(dlg.inputs.keys())
        # store filters chosen
        self.advanced_filters = {}

        for col in numeric_cols:
            min_box, max_box = dlg.inputs[col]
            min_text = min_box.text().strip()
            max_text = max_box.text().strip()
            # save for future
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

            # apply to df if column exists
            if col in df.columns:
                # coerce to numeric safely
                try:
                    series = pd.to_numeric(df[col], errors="coerce")
                    if "min" in saved:
                        df = df[series >= saved["min"]]
                    if "max" in saved:
                        df = df[series <= saved["max"]]
                except Exception:
                    # ignore a bad column conversion
                    pass

        # update filtered_data and table
        self.filtered_data = df
        self.update_table(df)
        dlg.accept()

    def clear_advanced_filters(self, dlg):
        # clear stored filters
        self.advanced_filters = {}
        # clear dialog boxes
        for min_box, max_box in dlg.inputs.values():
            min_box.clear()
            max_box.clear()
        # restore full data list
        self.filtered_data = self.data.copy() if self.data is not None else pd.DataFrame()
        self.update_table(self.filtered_data)
        dlg.accept()

    # ------------------ Node server controls (compact + robust) ------------------
    def toggle_node_server(self):
        """Start or stop the node server (CRIP4/catserver.exe preferred, fallback to node app.js)."""
        # if running -> stop
        if self._node_process is not None and self._node_process.poll() is None:
            try:
                self._node_process.terminate()
            except Exception:
                pass
            # don't block; leave monitor/checker to update UI
            self.status_label.setText("🛑 Stopping Node server...")
            # mark UI immediately
            self.node_btn.setText("⚡ Stopping...")
            self.node_btn.setStyleSheet("background-color: orange; color: black; font-weight:bold;")
            return

        # otherwise start
        self.node_btn.setText("⚡ Starting...")
        self.node_btn.setStyleSheet("background-color: orange; color: black; font-weight:bold;")
        self.status_label.setText("🚀 Starting Node server...")

        try:
            cwd = os.path.join(os.getcwd(), "CRIP4")
            exe_path = os.path.join(cwd, "catserver.exe")
            app_path = os.path.join(cwd, "app.js")

            # choose command: prefer catserver.exe if present
            if os.path.exists(exe_path):
                cmd = [exe_path]
            elif os.path.exists(app_path):
                cmd = ["node", "app.js"]
            else:
                self.status_label.setText(f"⚠️ CRIP4/catserver.exe or CRIP4/app.js not found in {cwd}")
                self.node_btn.setText("⚡ Start Node Server")
                self.node_btn.setStyleSheet("background-color: red; color: white; font-weight:bold;")
                return

            # Hide console window on Windows
            creation_flags = 0
            if os.name == "nt":
                creation_flags = subprocess.CREATE_NO_WINDOW

            # start process (non-blocking)
            self._node_process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags
            )

            # UI remains "starting" until _check_node_status verifies port listening
            # ensure timer runs (already started in __init__, but restart to check more often initially)
            self._node_check_timer.start(5000)

        except Exception as e:
            self.status_label.setText(f"❌ Failed to start node/catserver: {e}")
            self.node_btn.setText("⚡ Start Node Server")
            self.node_btn.setStyleSheet("background-color: red; color: white; font-weight:bold;")

    def _check_node_status(self):
        """
        Periodic poll: check whether the configured port is listening.
        Updates button colour/text accordingly.
        After first run, interval switches to 60s (less frequent).
        """
        try:
            port_ok = self._is_port_in_use(self._node_probe_port)
        except Exception:
            port_ok = False

        proc_running = (self._node_process is not None and self._node_process.poll() is None)

        if port_ok:
            # server reachable -> mark running
            self.node_btn.setText("🟢 Node Running")
            self.node_btn.setStyleSheet("background-color: green; color: white; font-weight:bold;")
            self.status_label.setText("Node server running.")
            # if process reference is missing but port open, leave process as None (server may be external)
            # keep timer at longer interval
        else:
            # not reachable
            if proc_running:
                # process alive but not yet listening -> startup in progress
                self.node_btn.setText("⚡ Starting...")
                self.node_btn.setStyleSheet("background-color: orange; color: black; font-weight:bold;")
                self.status_label.setText("Node starting (waiting for port)...")
            else:
                # stopped
                self.node_btn.setText("⚡ Start Node Server")
                self.node_btn.setStyleSheet("background-color: red; color: white; font-weight:bold;")
                # if process finished unexpectedly, clear reference
                if self._node_process is not None and self._node_process.poll() is not None:
                    self._node_process = None
                # Update status label only if it was previously showing node messages
                # leave whatever current status_label (do not overwrite benign user messages)

        # after initial checks, slow down polling
        if self._node_check_timer.interval() != 60000:
            self._node_check_timer.start(60000)

    def _is_port_in_use(self, port: int) -> bool:
        """Return True if localhost:port accepts TCP connections."""
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.8):
                return True
        except Exception:
            return False

    # ---------------- Close event (safe shutdown) ----------------
    def closeEvent(self, event):
        # Try to stop node server if running (graceful)
        try:
            if self._node_process is not None and self._node_process.poll() is None:
                try:
                    self._node_process.terminate()
                    self._node_process.wait(timeout=2)
                except Exception:
                    try:
                        self._node_process.kill()
                    except Exception:
                        pass
                finally:
                    self._node_process = None
        except Exception:
            pass

        # delegate to helper for safe shutdown (if implemented), otherwise default
        try:
            if hasattr(helper, "handle_close_event"):
                helper.handle_close_event(self, event)
                return
        except Exception:
            pass
        super().closeEvent(event)


# ---- Main ----
if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = MarketSmithGUI()
    gui.show()
    sys.exit(app.exec_())
