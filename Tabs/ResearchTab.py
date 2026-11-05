# ResearchTab.py
import os
import threading
import traceback
import pandas as pd
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import util  # uses your existing query logic


class ResearchTab(QWidget):
    # signal used to safely update progress from background thread
    progress_signal = pyqtSignal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.performance_file = ""
        self.queries_file = ""
        self.performance_df = pd.DataFrame()
        self.queries_df = pd.DataFrame()
        self.results_df = pd.DataFrame()

        self._worker_thread = None

        self.init_ui()

        # connect progress signal -> UI slot
        self.progress_signal.connect(self._on_progress_update)

    def init_ui(self):
        layout = QVBoxLayout(self)

        # --- File selection row 1 ---
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("📈 Performance Excel:"))
        self.perf_label = QLabel("(none)")
        self.perf_label.setStyleSheet("color: gray;")
        btn_perf = QPushButton("Browse...")
        btn_perf.clicked.connect(self.select_perf_file)
        row1.addWidget(self.perf_label)
        row1.addWidget(btn_perf)
        layout.addLayout(row1)

        # --- File selection row 2 ---
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("🧩 Queries Excel:"))
        self.query_label = QLabel("(none)")
        self.query_label.setStyleSheet("color: gray;")
        btn_query = QPushButton("Browse...")
        btn_query.clicked.connect(self.select_query_file)
        row2.addWidget(self.query_label)
        row2.addWidget(btn_query)
        layout.addLayout(row2)

        # --- Action buttons ---
        row3 = QHBoxLayout()
        self.run_btn = QPushButton("▶️ Run Research")
        self.run_btn.clicked.connect(self.run_research)
        self.status_label = QLabel("Status: Idle")
        row3.addWidget(self.run_btn)
        row3.addWidget(self.status_label)
        layout.addLayout(row3)

        # --- Progress Bar ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # --- Table to show results ---
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Query", "Matches", "Total", "Match %"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        # --- Matplotlib figure ---
        self.figure = Figure(figsize=(6, 3))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

    # ---------------------------------------------------
    # FILE SELECTION
    # ---------------------------------------------------
    def select_perf_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select Performance Excel", "",
                                               "Excel Files (*.xlsx *.xls);;CSV Files (*.csv)")
        if fname:
            self.performance_file = fname
            self.perf_label.setText(os.path.basename(fname))
            self.perf_label.setStyleSheet("color: black;")

    def select_query_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select Queries Excel", "",
                                               "Excel Files (*.xlsx *.xls);;CSV Files (*.csv)")
        if fname:
            self.queries_file = fname
            self.query_label.setText(os.path.basename(fname))
            self.query_label.setStyleSheet("color: black;")

    # ---------------------------------------------------
    # MAIN LOGIC
    # ---------------------------------------------------
    def run_research(self):
        if not self.performance_file or not self.queries_file:
            QMessageBox.warning(self, "Missing File", "Please select both files first.")
            return

        self.status_label.setText("⏳ Running research...")
        self.run_btn.setEnabled(False)
        self.table.setRowCount(0)
        self.figure.clear()
        self.canvas.draw()
        self.progress_bar.setValue(0)

        print("[*] running thread ")
        self._worker_thread = threading.Thread(target=self._run_research_thread, daemon=True)
        self._worker_thread.start()

    def _read_table_file(self, path):
        """Read excel or csv into DataFrame (helper to support both file types)."""
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext in (".csv",):
                return pd.read_csv(path)
            else:
                return pd.read_excel(path)
        except Exception:
            # re-raise to be handled by caller
            raise

    def _run_research_thread(self):
        try:
            perf_df = self._read_table_file(self.performance_file)
            queries_df = self._read_table_file(self.queries_file)
            print("[*] read files ")

            # Accept either 'symbol' or 'Stock' column names for compatibility
            if "symbol" in perf_df.columns:
                symbol_col = "symbol"
            elif "Stock" in perf_df.columns:
                symbol_col = "Stock"
            else:
                raise ValueError("Performance file must contain a 'symbol' or 'Stock' column")

            success_stocks = set(perf_df[symbol_col].astype(str).str.strip().str.upper())
            results = []

            total_queries = len(queries_df)
            if total_queries == 0:
                QTimer.singleShot(0, lambda: self._show_error("Queries file contains no rows"))
                return

            done = 0
            print(f"[Research] Starting evaluation of {total_queries} queries...")

            for _, row in queries_df.iterrows():
                qname = str(row.get("QueryName") or row.get("Name") or "Unnamed")
                query_data = row.get("QueryCode") or row.get("Query") or None

                if not query_data:
                    # still update progress so UI doesn't hang
                    done += 1
                    percent = int((done / total_queries) * 100)
                    self._update_progress(percent, f"⏳ Running research... {done}/{total_queries}")
                    continue

                try:
                    stocks = set(util.getHistoryfromQuery(query_data))
                    matches = success_stocks.intersection(stocks)
                    match_count = len(matches)
                    total = len(success_stocks)
                    pct = round((match_count / len(stocks)) * 100, 2) if len(stocks) > 0 else 0
                    results.append([qname, match_count, total, pct])
                    print(f"[Research] -> {qname}: {match_count}/{len(stocks)} matches ({pct}%)")
                except Exception as e:
                    print(f"[Research] Error running query {qname}: {e}")
                    results.append([qname, 0, len(success_stocks), 0])

                # ---- progress update ----
                done += 1
                progress_value = int((done / total_queries) * 100)
                self._update_progress(progress_value, f"⏳ Running research... {done}/{total_queries}")

            print("[Research] All queries evaluated. Updating UI...")

            self.results_df = pd.DataFrame(results, columns=["Query", "Matches", "Total", "Match %"])
            QTimer.singleShot(0, self._update_results_ui)

        except Exception as e:
            tb = traceback.format_exc()
            QTimer.singleShot(0, lambda: self._show_error(f"{e}\n{tb}"))

    # ---------------------------------------------------
    # UPDATE UI
    # ---------------------------------------------------
    def _update_results_ui(self):
        try:
            df = self.results_df
            self.table.setRowCount(len(df))
            for i, (_, row) in enumerate(df.iterrows()):
                for j, col in enumerate(df.columns):
                    item = QTableWidgetItem(str(row[col]))
                    item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(i, j, item)

            # Plot results
            ax = self.figure.add_subplot(111)
            ax.clear()
            ax.bar(df["Query"], df["Match %"])
            ax.set_xlabel("Query")
            ax.set_ylabel("Match %")
            ax.set_title("Query vs Match Percentage")
            ax.tick_params(axis='x', rotation=45)
            self.figure.tight_layout()
            self.canvas.draw()

            self.status_label.setText("✅ Research completed.")
        except Exception as e:
            self.status_label.setText(f"⚠️ Error updating UI: {e}")
        finally:
            self.run_btn.setEnabled(True)
            self.progress_bar.setValue(100)

    def _update_progress(self, value, text=None):
        """
        Emit a signal from the worker thread; the connected slot will update the UI
        in the main thread. This prevents recursive repaint and cross-thread UI access.
        """
        try:
            # ensure numeric value
            v = int(value) if value is not None else 0
            txt = str(text) if text else ""
            # emit thread-safe signal; connected slot runs in main thread
            self.progress_signal.emit(v, txt)
        except Exception:
            # fallback scheduling on main thread
            QTimer.singleShot(0, lambda: self.progress_bar.setValue(int(value)))
            if text:
                QTimer.singleShot(0, lambda: self.status_label.setText(text))

    def _on_progress_update(self, value, text=""):
        """Slot that updates UI widgets in the main thread."""
        try:
            v = max(0, min(100, int(value)))
        except Exception:
            v = 0
        self.progress_bar.setValue(v)
        if text:
            self.status_label.setText(text)

    def _show_error(self, msg):
        QMessageBox.critical(self, "Error", msg)
        self.status_label.setText("⚠️ Error occurred.")
        self.run_btn.setEnabled(True)
