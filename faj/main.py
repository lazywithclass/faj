from __future__ import annotations
import sys
from typing import Any, Optional, List
import pandas as pd
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QVariant
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QTableView, QLineEdit, QStatusBar, QLabel, QFileDialog, QMessageBox, QToolBar, QInputDialog
from PyQt6.QtGui import QAction

class DataFrameModel(QAbstractTableModel):
    def __init__(self, df: Optional[pd.DataFrame] = None):
        super().__init__()
        self._df = df if df is not None else pd.DataFrame()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._df)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._df.columns)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return QVariant()
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            v = self._df.iat[index.row(), index.column()]
            return "" if pd.isna(v) else str(v)
        return QVariant()

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return QVariant()
        if orientation == Qt.Orientation.Horizontal:
            try:
                return str(self._df.columns[section])
            except Exception:
                return QVariant()
        return str(section)

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable

    def setData(self, index: QModelIndex, value: Any, role=Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        col = self._df.columns[index.column()]
        text = None if value is None else str(value)
        try:
            if pd.api.types.is_numeric_dtype(self._df[col].dtype) and text != "":
                cast_val = pd.to_numeric([text], errors="raise")[0]
            elif pd.api.types.is_bool_dtype(self._df[col].dtype):
                cast_val = str(text).strip().lower() in {"1", "true", "t", "yes", "y"}
            else:
                cast_val = None if text == "" else text
        except Exception:
            cast_val = text
        self._df.iat[index.row(), index.column()] = cast_val
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
        return True

    def insertRows(self, position: int, rows: int = 1, parent=QModelIndex()) -> bool:
        self.beginInsertRows(QModelIndex(), position, position + rows - 1)
        for _ in range(rows):
            self._df.loc[len(self._df)] = [pd.NA] * len(self._df.columns)
        self.endInsertRows()
        return True

    def removeRows(self, position: int, rows: int = 1, parent=QModelIndex()) -> bool:
        if rows <= 0:
            return False
        self.beginRemoveRows(QModelIndex(), position, position + rows - 1)
        idx = list(range(position, position + rows))
        self._df.drop(self._df.index[idx], inplace=True)
        self._df.reset_index(drop=True, inplace=True)
        self.endRemoveRows()
        return True

    def insertColumn(self, name: str, position: Optional[int] = None) -> None:
        if position is None:
            position = len(self._df.columns)
        cols = list(self._df.columns)
        cols.insert(position, name)
        self._df[name] = pd.NA
        self._df = self._df[cols]
        self.layoutChanged.emit()

    def removeColumns(self, positions: List[int]) -> None:
        names = [self._df.columns[p] for p in sorted(set(positions))]
        self._df.drop(columns=names, inplace=True, errors="ignore")
        self.layoutChanged.emit()

    def set_dataframe(self, df: pd.DataFrame) -> None:
        self.beginResetModel()
        self._df = df
        self.endResetModel()

    def dataframe(self) -> pd.DataFrame:
        return self._df


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parquet Editor")
        self.resize(1200, 700)

        self.view = QTableView()
        self.model = DataFrameModel(pd.DataFrame())
        self.view.setModel(self.model)
        self.view.setSortingEnabled(True)
        self.setCentralWidget(self.view)

        self.path: Optional[str] = None
        self._original_on_disk: Optional[pd.DataFrame] = None

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter (contains, case-insensitive)")
        self.filter_input.returnPressed.connect(self.apply_filter)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.info_label = QLabel("Rows: 0  Cols: 0")
        self.status.addPermanentWidget(self.info_label)

        tb = QToolBar("Main")
        self.addToolBar(tb)

        def act(text, slot, shortcut=None):
            a = QAction(text, self)
            if shortcut:
                a.setShortcut(shortcut)
            a.triggered.connect(slot)
            tb.addAction(a)
            return a

        act("Open", self.open_file, "Ctrl+O")
        act("Save", self.save, "Ctrl+S")
        act("Save As", self.save_as)
        tb.addSeparator()
        act("Add Row", self.add_row, "Ctrl+N")
        act("Delete Row(s)", self.del_rows, "Del")
        act("Add Column", self.add_column)
        act("Delete Column(s)", self.del_columns)
        tb.addSeparator()
        tb.addWidget(QLabel("  "))
        tb.addWidget(self.filter_input)
        act("Clear Filter", self.clear_filter)

        self.update_stats()

    # --- file ops (Parquet only)
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Parquet", "", "Parquet (*.parquet);;All files (*)"
        )
        if not path:
            return
        try:
            df = pd.read_parquet(path)
        except Exception as e:
            QMessageBox.critical(self, "Open failed", str(e))
            return
        self.model.set_dataframe(df)
        self._original_on_disk = df.copy()
        self.path = path
        self.setWindowTitle(f"Parquet Editor — {path}")
        self.clear_filter()
        self.update_stats()

    def save(self):
        if not self.path:
            return self.save_as()
        try:
            self.model.dataframe().to_parquet(self.path, index=False)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))
            return
        self.status.showMessage(f"Saved to {self.path}", 3000)

    def save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Parquet As", "", "Parquet (*.parquet);;All files (*)"
        )
        if not path:
            return
        self.path = path
        self.save()
        self.setWindowTitle(f"Parquet Editor — {path}")

    # --- edits
    def add_row(self):
        self.model.insertRows(self.model.rowCount(), 1)
        self.update_stats()

    def del_rows(self):
        sel = self.view.selectionModel().selectedRows()
        if not sel:
            return
        rows = sorted({i.row() for i in sel})
        for offset, r in enumerate(rows):
            self.model.removeRows(r - offset, 1)
        self.update_stats()

    def add_column(self):
        name, ok = QInputDialog.getText(self, "Add column", "Column name:")
        if not ok or not name:
            return
        cols = list(self.model.dataframe().columns)
        pos, ok2 = QInputDialog.getInt(
            self, "Position", f"0..{len(cols)}", value=len(cols), min=0, max=len(cols)
        )
        if not ok2:
            return
        if name in cols:
            QMessageBox.warning(self, "Exists", "Column already exists.")
            return
        self.model.insertColumn(name, pos)
        self.update_stats()

    def del_columns(self):
        sel = self.view.selectionModel().selectedColumns()
        if not sel:
            return
        positions = [i.column() for i in sel]
        self.model.removeColumns(positions)
        self.update_stats()

    # --- filter
    def apply_filter(self):
        text = self.filter_input.text().strip().lower()
        if text == "":
            self.clear_filter()
            return
        df = self.model.dataframe()
        try:
            mask = pd.Series(False, index=df.index)
            for col in df.columns:
                vals = df[col].astype(str).str.lower()
                mask = mask | vals.str.contains(text, na=False)
            filtered = df[mask].reset_index(drop=True)
        except Exception as e:
            QMessageBox.critical(self, "Filter error", str(e))
            return
        self.model.set_dataframe(filtered)
        self.update_stats(tag=f"Filtered: {len(filtered)} rows")

    def clear_filter(self):
        if self._original_on_disk is not None:
            self.model.set_dataframe(self._original_on_disk.copy())
        self.update_stats()

    def update_stats(self, tag: str = ""):
        df = self.model.dataframe()
        self.info_label.setText(f"Rows: {len(df)}  Cols: {len(df.columns)}" + (f"  {tag}" if tag else ""))


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

