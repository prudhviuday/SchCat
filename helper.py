# helper.py
import threading
import concurrent.futures
import traceback
import pandas as pd
from PyQt5.QtCore import Qt, QThread, QTimer, QEvent
from PyQt5.QtWidgets import QTableWidgetItem, QComboBox, QStyledItemDelegate, QDialog
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QAbstractItemView,
    QDialog, QGridLayout
)
import util

# ---------------- Worker Logic ----------------
def run_fetch_data_worker(max_workers, progress_signal, finished_signal, error_signal):
    """Runs threaded stock data fetching, emitting progress and results."""
    try:
        market_ids = util.load_market_ids()
        total = len(market_ids)
        results = []

        def fetch_one(item):
            name, id_ = item
            return util.fetch_stock_data_from_MS((name, id_))

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_name = {
                executor.submit(fetch_one, (name, id_)): (name, id_)
                for name, id_ in market_ids.items()
            }

            done_count = 0
            for fut in concurrent.futures.as_completed(future_to_name):
                try:
                    res = fut.result()
                    results.append(res)
                except Exception as e:
                    print("fetch error:", e)
                done_count += 1
                progress_signal.emit(done_count, total)

        finished_signal.emit(results, market_ids)

    except Exception as e:
        tb = traceback.format_exc()
        error_signal.emit(f"{e}\n{tb}")


# ---------------- Thread Handling ----------------
def start_fetch_thread(gui, WorkerClass, progress_fn, finished_fn, error_fn):
    """Starts fetch worker in QThread with spinner and signal connections."""
    gui.start_btn.setEnabled(False)
    gui.status_label.setText("⏳ Starting fetch...")
    gui.spinner_label.setText("")
    gui._spinner_state = 0
    gui._spinner_timer.start()

    gui._fetch_worker = WorkerClass(max_workers=8)
    gui._fetch_thread = QThread()
    gui._fetch_worker.moveToThread(gui._fetch_thread)
    gui._fetch_thread.started.connect(gui._fetch_worker.run)

    gui._fetch_worker.progress.connect(progress_fn)
    gui._fetch_worker.finished.connect(finished_fn)
    gui._fetch_worker.error.connect(error_fn)

    gui._fetch_worker.finished.connect(gui._fetch_thread.quit)
    gui._fetch_worker.finished.connect(gui._fetch_worker.deleteLater)
    gui._fetch_thread.finished.connect(gui._fetch_thread.deleteLater)
    gui._fetch_worker.error.connect(gui._fetch_thread.quit)
    gui._fetch_worker.error.connect(gui._fetch_worker.deleteLater)

    gui._fetch_thread.start()


# ---------------- Fetch Data Handlers ----------------
def handle_fetch_error(gui, text):
    gui._spinner_timer.stop()
    gui.spinner_label.setText("")
    gui.status_label.setText(f"⚠️ Error: {text}")
    gui.start_btn.setEnabled(True)


def handle_fetch_finished(gui, results, market_ids):
    gui._spinner_timer.stop()
    gui.spinner_label.setText("")

    try:
        gui.data = pd.DataFrame(results)
        gui.filtered_data = gui.data.copy()
        gui.market_ids = market_ids
        gui.update_table(gui.filtered_data)
        final_text = f"✅ Completed! {len(results)} stocks loaded."
        gui._fade_to_green(final_text)
    except Exception as e:
        gui.status_label.setText(f"⚠️ Error processing results: {e}")
        print("Fetch finished processing error:", e)
    finally:
        gui.start_btn.setEnabled(True)


# ---------------- Fade Animations ----------------
def fade_to_green(gui, text):
    gui._fade_step_idx = 0
    gui.final_status_text = text
    if gui._fade_timer:
        gui._fade_timer.stop()
    gui._fade_timer = QTimer()
    gui._fade_timer.setInterval(30)
    gui._fade_timer.timeout.connect(gui._fade_step)
    gui._fade_timer.start()


def fade_step(gui):
    steps = gui._fade_steps
    i = gui._fade_step_idx
    if i >= steps:
        gui._fade_timer.stop()
        gui.status_label.setText(gui.final_status_text)
        gui.status_label.setStyleSheet("color: #00a000;")
        return
    start_g = 80
    end_g = 160
    g = int(start_g + (i / steps) * (end_g - start_g))
    color = f"#{0:02x}{g:02x}{0:02x}"
    gui.status_label.setStyleSheet(f"color: {color};")
    gui.status_label.setText(gui.final_status_text)
    gui._fade_step_idx += 1


# ---------------- Table Handling ----------------
def update_table(gui, df):
    gui.table.setRowCount(len(df))
    for i, (_, row) in enumerate(df.iterrows()):
        for j, col in enumerate(gui.columns):
            item = QTableWidgetItem(str(row[col]))
            item.setTextAlignment(Qt.AlignCenter)
            gui.table.setItem(i, j, item)


def filter_table(gui):
    query = gui.search_input.text().strip().lower()
    if query == "":
        filtered = gui.filtered_data
    else:
        filtered = gui.filtered_data[
            gui.filtered_data["Stock"].str.lower().str.contains(query)
        ]
    gui.update_table(filtered)


# ---------------- Multi-select dropdown ----------------
class MultiSelectDropdown(QComboBox):
    """
    QComboBox with multiple checkable items.
    Use get_selected_items() to retrieve selected items as a list.
    (Prevents popup from closing on each click.)
    """
    def __init__(self, items=None):
        super().__init__()
        self.setEditable(False)
        self.items_checked = {}
        if items:
            for item in items:
                self.addItem(item)
                self.setItemChecked(item, False)

        self.setItemDelegate(QStyledItemDelegate())
        # intercept mouse clicks on the view's viewport
        self.view().viewport().installEventFilter(self)

    def handle_item_pressed(self, index):
        # Clear selection highlight (visual only)
        try:
            self.view().selectionModel().clearSelection()
        except Exception:
            pass
        text = self.itemText(index.row())
        checked = not self.items_checked.get(text, False)
        self.setItemChecked(text, checked)

    def setItemChecked(self, text, checked):
        self.items_checked[text] = bool(checked)
        idx = self.findText(text)
        if idx >= 0:
            it = self.model().item(idx)
            if it is not None:
                it.setCheckState(Qt.Checked if checked else Qt.Unchecked)

    def get_selected_items(self):
        return [k for k, v in self.items_checked.items() if v]

    def eventFilter(self, obj, event):
        # Only intercept clicks on viewport to toggle items and prevent default closing
        if obj == self.view().viewport() and event.type() == QEvent.MouseButtonRelease:
            index = self.view().indexAt(event.pos())
            if index.isValid():
                self.handle_item_pressed(index)
            # Return True prevents the default processing that would close the popup
            return True
        return super().eventFilter(obj, event)


# ---------------- Query & Watchlist ----------------
def getAllQueries():
    return util.getAllQueries()


def getAllWatchlists():
    return util.getAllWatchlists()


def toggle_query(gui):
    """
    Toggle query selection: if the same selection is already active => drop it.
    Expects gui.query_combo to be a MultiSelectDropdown (get_selected_items()).
    """
    # try to obtain list of selected items; fallback to single text
    selected = None
    try:
        selected = gui.query_combo.get_selected_items()
    except Exception:
        # fallback for plain QComboBox (single selection)
        try:
            txt = gui.query_combo.currentText()
            selected = [txt] if txt and txt != "None" else []
        except Exception:
            selected = []

    # Normalize empty selection
    if not selected:
        selected = []

    if gui.active_query == selected:
        gui.active_query = None
        gui.query_btn.setText("Go")
    else:
        gui.active_query = selected
        gui.query_btn.setText("Drop")
    gui.apply_filters()


def toggle_watchlist(gui):
    """
    Toggle watchlist filter. Supports:
      - gui.watch_combo being a plain QComboBox (single-select)
      - or a MultiSelectDropdown (multi-select)
    We keep gui.active_watchlist as a list (or None).
    """
    # get selection list (if possible)
    selected = None
    if hasattr(gui.watch_combo, "get_selected_items"):
        try:
            selected = gui.watch_combo.get_selected_items()
        except Exception:
            selected = []
    else:
        # plain QComboBox
        try:
            txt = gui.watch_combo.currentText()
            if txt == "None" or txt == "":
                selected = []
            else:
                selected = [txt]
        except Exception:
            selected = []

    # normalize
    if not selected:
        selected = []

    if gui.active_watchlist == selected:
        # Same selection: treat as drop
        gui.active_watchlist = None
        gui.watch_btn.setText("Go")
    else:
        gui.active_watchlist = selected
        gui.watch_btn.setText("Drop")

    gui.apply_filters()


def refresh_watchlists(gui):
    """
    Rebuild watchlist combo while attempting to preserve previous selection(s).
    Works for both plain QComboBox and MultiSelectDropdown.
    """
    new_watchlists = util.getAllWatchlists()
    gui.allwatchlists = new_watchlists

    # Preserve selection
    prev_selected = []
    if hasattr(gui.watch_combo, "get_selected_items"):
        try:
            prev_selected = gui.watch_combo.get_selected_items()
        except Exception:
            prev_selected = []
    else:
        try:
            cur = gui.watch_combo.currentText()
            prev_selected = [cur] if cur and cur != "None" else []
        except Exception:
            prev_selected = []

    # Rebuild widget contents
    if hasattr(gui.watch_combo, "setItemChecked"):
        # MultiSelectDropdown style
        try:
            gui.watch_combo.blockSignals(True)
            gui.watch_combo.clear()
            for name in list(new_watchlists.keys()):
                gui.watch_combo.addItem(name)
                gui.watch_combo.setItemChecked(name, False)
            gui.watch_combo.blockSignals(False)

            # restore checked items (best-effort)
            for name in prev_selected:
                try:
                    gui.watch_combo.setItemChecked(name, True)
                except Exception:
                    pass
        except Exception:
            pass
    else:
        # plain QComboBox
        try:
            gui.watch_combo.blockSignals(True)
            gui.watch_combo.clear()
            gui.watch_combo.addItem("None")
            for name in list(new_watchlists.keys()):
                gui.watch_combo.addItem(name)
            gui.watch_combo.blockSignals(False)

            # restore previous (best-effort)
            if prev_selected:
                try:
                    val = prev_selected[0]
                    idx = gui.watch_combo.findText(val)
                    if idx >= 0:
                        gui.watch_combo.setCurrentIndex(idx)
                except Exception:
                    pass
        except Exception:
            pass

    gui.status_label.setText("🔄 Watchlists refreshed.")


def apply_filters(gui):
    """
    Apply active_query (AND across selected queries) and active_watchlist filters.
    Leaves gui.filtered_data and table updated.
    """
    base = gui.data.copy() if gui.data is not None else pd.DataFrame()
    if base.empty:
        gui.status_label.setText("⚠️ No data available.")
        return

    # ----- Multi-query AND logic -----
    if gui.active_query and len(gui.active_query) > 0:
        sets = []
        for q in gui.active_query:
            # guard against bad keys
            try:
                q_def = gui.allqueries.get(q) if isinstance(gui.allqueries, dict) else None
                if q_def is None:
                    # if gui.allqueries stores strings differently, try direct q value
                    q_def = gui.allqueries[q] if (isinstance(gui.allqueries, dict) and q in gui.allqueries) else None
            except Exception:
                q_def = None

            if q_def is None:
                # If key not found, skip this query
                continue

            try:
                q_stocks = set(util.getCIfromQuery(q_def))
                sets.append(q_stocks)
            except Exception as e:
                print(f"[apply_filters] error getting stocks for query {q}: {e}")

        if sets:
            try:
                inter = set.intersection(*sets)
                base = base[base["Stock"].isin(inter)]
            except Exception:
                # fallback: no intersection possible
                pass

    # ----- Watchlist filter (single watchlist is supported) -----
    if gui.active_watchlist and len(gui.active_watchlist) > 0:
        # only use first selected watchlist to filter (behavior you had previously)
        wl_name = gui.active_watchlist[0]
        try:
            watch_stocks = gui.allwatchlists.get(wl_name, [])
            base = base[base["Stock"].isin(watch_stocks)]
        except Exception as e:
            print(f"[apply_filters] error applying watchlist {wl_name}: {e}")

    gui.filtered_data = base
    gui.update_table(base)
    gui.status_label.setText(f"✅ Filtered: {len(base)} stocks visible.")


# ---------------- Row Selection ----------------
def on_row_select(gui):
    selected = gui.table.selectedItems()
    if not selected:
        return
    row_index = selected[0].row()
    stock_name = gui.table.item(row_index, 0).text()
    row_data = gui.data[gui.data["Stock"] == stock_name].iloc[0]
    gui.right_panel.update(stock_name, row_data, getattr(gui, "market_ids", {}))


# ---------------- Row double click ----------------
def on_row_double_click_on_othercell(gui, row, column):
    """When a stock is double-clicked, open Chart tab for that stock."""
    try:
        if row < 0 or row >= len(gui.filtered_data):
            return
        stock_name = gui.table.item(row, 0).text()
        gui.chart_panel.load_stock(stock_name)
        gui.tab_control.setCurrentIndex(1)
    except Exception as e:
        print("Error opening chart tab:", e)
        

def on_row_double_click(gui, row, column):
    """
    Double-click behavior:
    - If Stock column → open Chart tab (existing behavior)
    - If Industry column → toggle filter for that industry
    """
    try:
        col_name = gui.columns[column]
        if col_name == "Industry":
            # Get industry name from clicked cell
            industry_name = gui.table.item(row, column).text().strip()
            if not industry_name:
                return

            # If we’re already showing filtered view of that industry → revert
            if hasattr(gui, "_industry_filter_active") and gui._industry_filter_active:
                gui.filtered_data = gui._previous_filtered_data.copy()
                gui.update_table(gui.filtered_data)
                gui._industry_filter_active = False
                gui._fade_status("🔙 Showing all filtered stocks again")
                return

            # Otherwise, filter current visible list by industry
            gui._previous_filtered_data = gui.filtered_data.copy() if not gui.filtered_data.empty else gui.data.copy()
            df = gui._previous_filtered_data
            df_ind = df[df["Industry"] == industry_name].copy()

            if df_ind.empty:
                gui._fade_status(f"⚠️ No stocks found in {industry_name}")
                return

            gui.filtered_data = df_ind
            gui.update_table(df_ind)
            gui._industry_filter_active = True
            gui._fade_status(f"✅ Showing only industry: {industry_name}")
            return

        # Otherwise, default behavior (double-click stock → open Chart tab)
        on_row_double_click_on_othercell(gui, row, column)

    except Exception as e:
        print("Error in on_row_double_click:", e)


# ---------------- Sorting ----------------
def on_header_clicked(gui, logicalIndex):
    col_name = gui.columns[logicalIndex]
    asc = gui._sort_state.get(logicalIndex, True)
    df_source = gui.filtered_data if not gui.filtered_data.empty else gui.data
    if df_source is None or df_source.empty:
        return

    df_copy = df_source.copy()
    try:
        df_copy[col_name] = pd.to_numeric(df_copy[col_name], errors="coerce")
        sorted_df = df_copy.sort_values(
            by=col_name, ascending=asc, na_position="last"
        )
    except Exception:
        sorted_df = df_copy.sort_values(
            by=col_name, ascending=asc, key=lambda s: s.astype(str)
        )

    gui._sort_state[logicalIndex] = not asc
    gui.filtered_data = sorted_df
    gui.update_table(sorted_df)
    direction = "ascending" if asc else "descending"
    gui.status_label.setText(f"🔽 Sorted by {col_name} ({direction})")


# ---------------- Watchlist Add ----------------
def add_to_watchlist_on_keypress(gui, watchlist_number=None):
    """
    Adds the currently selected stock to a watchlist.
    - If watchlist_number provided (1-based), pick the corresponding watchlist from gui.allwatchlists keys.
    - Otherwise use the currently selected item in gui.watch_combo (supports both QComboBox and MultiSelectDropdown).
    """
    selected_row = gui.table.currentRow()
    if selected_row < 0:
        gui._fade_status("⚠️ Please select a stock first.")
        return

    stock_name = gui.table.item(selected_row, 0).text()

    # numeric mapping case
    if watchlist_number is not None:
        try:
            watchlist_keys = list(gui.allwatchlists.keys())
            if 1 <= watchlist_number <= len(watchlist_keys):
                wl_key = watchlist_keys[watchlist_number - 1]
                # run add in background (do not change active filter)
                threading.Thread(target=add_to_watchlist_thread, args=(gui, wl_key, stock_name), daemon=True).start()
                gui._fade_status(f"✅ {stock_name} added to {wl_key}")
            else:
                gui._fade_status("⚠️ No watchlist for that number.")
        except Exception as e:
            gui._fade_status(f"⚠️ Error adding to watchlist: {e}")
        return

    # normal case: use current selection in the combo
    # If the widget supports get_selected_items(), prefer that (multi-select scenario)
    if hasattr(gui.watch_combo, "get_selected_items"):
        try:
            sel = gui.watch_combo.get_selected_items()
            if not sel:
                gui._fade_status("⚠️ Please select a watchlist first.")
                return
            # use first selected for add action (keep behaviour same as before)
            watchlist = sel[0]
        except Exception:
            gui._fade_status("⚠️ Please select a watchlist first.")
            return
    else:
        # plain QComboBox
        try:
            watchlist = gui.watch_combo.currentText()
            if watchlist == "None" or not watchlist:
                gui._fade_status("⚠️ Please select a watchlist first.")
                return
        except Exception:
            gui._fade_status("⚠️ Please select a watchlist first.")
            return

    # add in background thread
    threading.Thread(target=add_to_watchlist_thread, args=(gui, watchlist, stock_name), daemon=True).start()



def add_to_watchlist_thread(gui, watchlist, stock_name):
    try:
        util.addStToWatchlists(watchlist, stock_name)

        # preserve current selection(s)
        prev_selected = []
        if hasattr(gui.watch_combo, "get_selected_items"):
            try:
                prev_selected = gui.watch_combo.get_selected_items()
            except Exception:
                prev_selected = []
        else:
            try:
                cur = gui.watch_combo.currentText()
                prev_selected = [cur] if cur and cur != "None" else []
            except Exception:
                prev_selected = []

        # rebuild list
        refresh_watchlists(gui)

        # restore selection (best-effort)
        if prev_selected:
            if hasattr(gui.watch_combo, "setItemChecked"):
                try:
                    for name in prev_selected:
                        gui.watch_combo.setItemChecked(name, True)
                except Exception:
                    pass
            else:
                try:
                    idx = gui.watch_combo.findText(prev_selected[0])
                    if idx >= 0:
                        gui.watch_combo.setCurrentIndex(idx)
                except Exception:
                    pass

        gui._fade_status(f"✅ Added \"{stock_name}\" to Watchlist: {watchlist}")
    except Exception as e:
        gui._fade_status(f"⚠️ Failed to add {stock_name}: {e}")


# ---------------- Small Fade Helper ----------------
def fade_status(gui, text):
    def start():
        gui.status_label.setText(text)
        if text.startswith("✅"):
            gui._fade_to_green(text)

    QTimer.singleShot(0, start)


def eventFilter(gui, source, event):
    if source is gui.table and event.type() == event.KeyPress:
        key = event.key()

        # Right arrow → existing behavior
        if key == Qt.Key_Right:
            gui.add_to_watchlist_on_keypress()
            return True

        # Numeric keys 1–9 → send to watchlist by number
        if Qt.Key_1 <= key <= Qt.Key_9:
            num = key - Qt.Key_0  # converts Qt.Key_1..9 → 1..9
            add_to_watchlist_on_keypress(gui, watchlist_number=num)
            return True

    # 👇 ensure the function *always* returns a boolean
    return False

# helper.py
from PyQt5.QtCore import QThread

def handle_close_event(gui, event):
    """
    Gracefully stop all background threads before exiting.
    """
    # 1) Stop AnalysisTab workers (if present)
    try:
        tab = getattr(gui, "tab_analysis", None)
        if tab and hasattr(tab, "stop_all_workers"):
            tab.stop_all_workers(timeout_ms=3000)
    except Exception:
        pass

    # 2) Stop ChartPanel's worker/thread (if running)
    try:
        cp = getattr(gui, "chart_panel", None)
        if cp is not None:
            th = getattr(cp, "_thread", None)
            if isinstance(th, QThread) and th.isRunning():
                try:
                    th.quit()
                    th.wait(3000)
                except Exception:
                    pass
            if hasattr(cp, "_worker"):
                try:
                    cp._worker = None
                except Exception:
                    pass
    except Exception:
        pass

    # 3) Stop fetch-data worker/thread if running
    try:
        th = getattr(gui, "_fetch_thread", None)
        if isinstance(th, QThread) and th.isRunning():
            try:
                th.quit()
                th.wait(3000)
            except Exception:
                pass
    except Exception:
        pass

    # Allow normal close to proceed
    try:
        super(type(gui), gui).closeEvent(event)
    except Exception:
        event.accept()




# ---------------- Filter Dialog ----------------
class FilterDialog(QDialog):
    """
    Dialog for advanced numeric filters (min/max) for several numeric columns.
    """
    def __init__(self, parent, columns):
        super().__init__(parent)
        self.setWindowTitle("Filter Settings")
        self.resize(420, 320)
        self.columns = columns
        self.inputs = {}  # col -> (min_widget, max_widget)

        layout = QVBoxLayout(self)

        grid = QGridLayout()
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        # header
        grid.addWidget(QLabel("<b>Field</b>"), 0, 0)
        grid.addWidget(QLabel("<b>Min</b>"), 0, 1)
        grid.addWidget(QLabel("<b>Max</b>"), 0, 2)

        for i, col in enumerate(columns, start=1):
            lbl = QLabel(col)
            min_box = QLineEdit()
            max_box = QLineEdit()
            min_box.setPlaceholderText("min")
            max_box.setPlaceholderText("max")
            # restrict to numeric-like input visually (not enforced)
            min_box.setFixedWidth(100)
            max_box.setFixedWidth(100)
            grid.addWidget(lbl, i, 0)
            grid.addWidget(min_box, i, 1)
            grid.addWidget(max_box, i, 2)
            self.inputs[col] = (min_box, max_box)

        layout.addLayout(grid)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.go_btn = QPushButton("Go")
        self.clear_btn = QPushButton("Clear")
        self.cancel_btn = QPushButton("Cancel")
        btn_row.addWidget(self.go_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        # signals
        self.cancel_btn.clicked.connect(self.reject)
        # go/clear will be connected by caller to appropriate handlers
