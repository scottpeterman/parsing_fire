#!/usr/bin/env python3
"""
TTP Template Tester - PyQt6 Edition
Debug tool for testing TTP template matching, manual parsing, and template management

Features:
- Database-driven template testing with auto-scoring
- Manual TTP template testing (no database required)
- Full CRUD interface for ttp_templates.db
- Light/Dark/Cyber theme support

Author: Scott Peterman (TTP port)
License: MIT
"""

import sys
import json
import sqlite3
import hashlib
import traceback
import warnings
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QSplitter, QTableWidget,
    QTableWidgetItem, QTabWidget, QGroupBox, QSpinBox, QCheckBox,
    QFileDialog, QMessageBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHeaderView, QAbstractItemView, QMenu, QInputDialog,
    QStatusBar, QToolBar, QFrame, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QAction, QIcon, QColor, QPalette, QShortcut, QKeySequence


def get_package_db_path() -> Path:
    """Database is in same directory as this module."""
    return Path(__file__).parent / "ttp_templates.db"


def find_database(db_path: Optional[str] = None) -> Optional[Path]:
    """Find database - explicit path first, then package location."""

    def is_valid_db(path: Path) -> bool:
        return path.exists() and path.is_file() and path.stat().st_size > 0

    if db_path:
        p = Path(db_path)
        return p if is_valid_db(p) else None

    package_db = get_package_db_path()
    return package_db if is_valid_db(package_db) else None


# Try to import the TTP engine
TTP_ENGINE_AVAILABLE = False
try:
    from ttp_fire import TTPAutoEngine

    TTP_ENGINE_AVAILABLE = True
except ImportError:
    try:
        from .ttp_fire import TTPAutoEngine

        TTP_ENGINE_AVAILABLE = True
    except ImportError:
        pass

# TTP library
TTP_AVAILABLE = False
try:
    from ttp import ttp

    TTP_AVAILABLE = True
except ImportError:
    pass

# =============================================================================
# THEMES
# =============================================================================

THEMES = {
    'light': {
        'name': 'Light',
        'window_bg': '#ffffff',
        'text_color': '#000000',
        'input_bg': '#ffffff',
        'input_border': '#cccccc',
        'button_bg': '#e0e0e0',
        'button_hover': '#d0d0d0',
        'table_bg': '#ffffff',
        'table_alt': '#f5f5f5',
        'highlight': '#0078d4',
        'success': '#28a745',
        'error': '#dc3545',
        'warning': '#ffc107'
    },
    'dark': {
        'name': 'Dark',
        'window_bg': '#2b2b2b',
        'text_color': '#e0e0e0',
        'input_bg': '#3c3c3c',
        'input_border': '#555555',
        'button_bg': '#404040',
        'button_hover': '#505050',
        'table_bg': '#2b2b2b',
        'table_alt': '#353535',
        'highlight': '#0078d4',
        'success': '#28a745',
        'error': '#dc3545',
        'warning': '#ffc107'
    },
    'cyber': {
        'name': 'Cyber',
        'window_bg': '#0a0a0a',
        'text_color': '#00ff00',
        'input_bg': '#1a1a1a',
        'input_border': '#00ff00',
        'button_bg': '#1a1a1a',
        'button_hover': '#2a2a2a',
        'table_bg': '#0a0a0a',
        'table_alt': '#151515',
        'highlight': '#00ff00',
        'success': '#00ff00',
        'error': '#ff0000',
        'warning': '#ffff00'
    }
}


def apply_theme(widget: QWidget, theme_name: str = 'dark'):
    """Apply a theme to a widget and its children."""
    theme = THEMES.get(theme_name, THEMES['dark'])

    stylesheet = f"""
        QMainWindow, QWidget {{
            background-color: {theme['window_bg']};
            color: {theme['text_color']};
        }}
        QTextEdit, QLineEdit, QSpinBox {{
            background-color: {theme['input_bg']};
            color: {theme['text_color']};
            border: 1px solid {theme['input_border']};
            border-radius: 3px;
            padding: 4px;
        }}
        QPushButton {{
            background-color: {theme['button_bg']};
            color: {theme['text_color']};
            border: 1px solid {theme['input_border']};
            border-radius: 3px;
            padding: 6px 12px;
            min-width: 80px;
        }}
        QPushButton:hover {{
            background-color: {theme['button_hover']};
        }}
        QPushButton:pressed {{
            background-color: {theme['highlight']};
        }}
        QTableWidget {{
            background-color: {theme['table_bg']};
            color: {theme['text_color']};
            gridline-color: {theme['input_border']};
            border: 1px solid {theme['input_border']};
        }}
        QTableWidget::item:alternate {{
            background-color: {theme['table_alt']};
        }}
        QTableWidget::item:selected {{
            background-color: {theme['highlight']};
        }}
        QHeaderView::section {{
            background-color: {theme['button_bg']};
            color: {theme['text_color']};
            border: 1px solid {theme['input_border']};
            padding: 4px;
        }}
        QTabWidget::pane {{
            border: 1px solid {theme['input_border']};
        }}
        QTabBar::tab {{
            background-color: {theme['button_bg']};
            color: {theme['text_color']};
            border: 1px solid {theme['input_border']};
            padding: 8px 16px;
        }}
        QTabBar::tab:selected {{
            background-color: {theme['highlight']};
        }}
        QGroupBox {{
            border: 1px solid {theme['input_border']};
            border-radius: 3px;
            margin-top: 10px;
            padding-top: 10px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
            color: {theme['text_color']};
        }}
        QComboBox {{
            background-color: {theme['input_bg']};
            color: {theme['text_color']};
            border: 1px solid {theme['input_border']};
            border-radius: 3px;
            padding: 4px;
        }}
        QComboBox::drop-down {{
            border: none;
        }}
        QStatusBar {{
            background-color: {theme['button_bg']};
            color: {theme['text_color']};
        }}
        QLabel {{
            color: {theme['text_color']};
        }}
        QProgressBar {{
            border: 1px solid {theme['input_border']};
            border-radius: 3px;
            text-align: center;
        }}
        QProgressBar::chunk {{
            background-color: {theme['highlight']};
        }}
    """
    widget.setStyleSheet(stylesheet)


# =============================================================================
# TTP PARSING UTILITIES
# =============================================================================

def parse_with_ttp(template_content: str, cli_content: str) -> tuple:
    """
    Parse CLI output with TTP template.
    Returns (success, results_list, error_message)
    """
    if not TTP_AVAILABLE:
        return False, [], "TTP library not installed"

    try:
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=SyntaxWarning)
            parser = ttp(data=cli_content, template=template_content)
            parser.parse()
            results = parser.result()

        # Flatten results
        parsed_dicts = []

        def extract_records(obj):
            if isinstance(obj, dict):
                has_data = any(not isinstance(v, (list, dict)) for v in obj.values())
                if has_data:
                    record = {k: v for k, v in obj.items() if not isinstance(v, (list, dict))}
                    if record:
                        parsed_dicts.append(record)
                for v in obj.values():
                    extract_records(v)
            elif isinstance(obj, list):
                for item in obj:
                    extract_records(item)

        if results and len(results) > 0:
            extract_records(results[0])

        return True, parsed_dicts, ""
    except Exception as e:
        return False, [], str(e)


# =============================================================================
# WORKER THREADS
# =============================================================================

class AutoTestWorker(QThread):
    """Worker thread for auto-testing templates"""
    progress = pyqtSignal(int, int, str)  # current, total, status
    result = pyqtSignal(str, list, float, list)  # best_template, parsed, score, all_scores
    error = pyqtSignal(str)

    def __init__(self, engine, cli_output: str, filter_string: str):
        super().__init__()
        self.engine = engine
        self.cli_output = cli_output
        self.filter_string = filter_string

    def run(self):
        try:
            best, parsed, score, all_scores = self.engine.find_best_template(
                self.cli_output,
                self.filter_string if self.filter_string else None
            )
            self.result.emit(best or "", parsed or [], score, all_scores)
        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# MAIN WINDOW
# =============================================================================

class TTPTester(QMainWindow):
    """Main TTP Template Tester Window"""

    def __init__(self, db_path: str = None):
        super().__init__()

        self.db_path = db_path or str(get_package_db_path())
        self.current_theme = 'dark'
        self.engine = None

        self.init_ui()
        self.apply_current_theme()

        # Initialize engine if available
        if TTP_ENGINE_AVAILABLE and Path(self.db_path).exists():
            try:
                self.engine = TTPAutoEngine(self.db_path)
                self.statusBar().showMessage(f"Loaded database: {self.db_path}")
            except Exception as e:
                self.statusBar().showMessage(f"Error loading database: {e}")

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("TTP Template Tester")
        self.setGeometry(100, 100, 1400, 900)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Toolbar
        self.create_toolbar()

        # Main tabs
        self.main_tabs = QTabWidget()
        layout.addWidget(self.main_tabs)

        # Create tabs
        self.create_auto_test_tab()
        self.create_manual_test_tab()
        self.create_manager_tab()

        # Status bar
        self.setStatusBar(QStatusBar())

    def create_toolbar(self):
        """Create the toolbar"""
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        # Database path
        toolbar.addWidget(QLabel("Database: "))
        self.db_path_input = QLineEdit(self.db_path)
        self.db_path_input.setMinimumWidth(300)
        toolbar.addWidget(self.db_path_input)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_database)
        toolbar.addWidget(browse_btn)

        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.reload_database)
        toolbar.addWidget(reload_btn)

        toolbar.addSeparator()

        # Theme selector
        toolbar.addWidget(QLabel("Theme: "))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(['dark', 'light', 'cyber'])
        self.theme_combo.setCurrentText(self.current_theme)
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        toolbar.addWidget(self.theme_combo)

    def create_auto_test_tab(self):
        """Create the Auto Test tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Top section - CLI Input and Controls
        top_group = QGroupBox("CLI Output to Test")
        top_layout = QVBoxLayout(top_group)

        # Filter row
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self.auto_filter_input = QLineEdit()
        self.auto_filter_input.setPlaceholderText("e.g., cisco_ios, show_version, arista")
        filter_layout.addWidget(self.auto_filter_input)

        self.auto_test_btn = QPushButton("Find Best Template")
        self.auto_test_btn.clicked.connect(self.run_auto_test)
        filter_layout.addWidget(self.auto_test_btn)

        top_layout.addLayout(filter_layout)

        # CLI input
        self.auto_cli_input = QTextEdit()
        self.auto_cli_input.setPlaceholderText("Paste CLI output here...")
        self.auto_cli_input.setFont(QFont("Consolas", 10))
        top_layout.addWidget(self.auto_cli_input)

        layout.addWidget(top_group)

        # Bottom section - Results
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Scores table
        scores_group = QGroupBox("Template Scores")
        scores_layout = QVBoxLayout(scores_group)

        self.auto_scores_table = QTableWidget()
        self.auto_scores_table.setColumnCount(3)
        self.auto_scores_table.setHorizontalHeaderLabels(["Template", "Score", "Records"])
        self.auto_scores_table.horizontalHeader().setStretchLastSection(True)
        self.auto_scores_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.auto_scores_table.itemDoubleClicked.connect(self.load_template_to_manual)
        scores_layout.addWidget(self.auto_scores_table)

        bottom_splitter.addWidget(scores_group)

        # Parsed results
        results_group = QGroupBox("Parsed Data (Best Match)")
        results_layout = QVBoxLayout(results_group)

        self.auto_results_table = QTableWidget()
        self.auto_results_table.setAlternatingRowColors(True)
        results_layout.addWidget(self.auto_results_table)

        bottom_splitter.addWidget(results_group)

        layout.addWidget(bottom_splitter)

        self.main_tabs.addTab(tab, "Auto Test")

    def create_manual_test_tab(self):
        """Create the Manual Test tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Top - Template and CLI Input
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)

        # Template input
        template_group = QGroupBox("TTP Template")
        template_layout = QVBoxLayout(template_group)

        self.manual_template_text = QTextEdit()
        self.manual_template_text.setFont(QFont("Consolas", 10))
        self.manual_template_text.setPlaceholderText('''<group name="interfaces">
{{INTERFACE}} is {{STATUS}}, line protocol is {{PROTOCOL}}
</group>''')
        template_layout.addWidget(self.manual_template_text)

        top_layout.addWidget(template_group)

        # CLI input
        cli_group = QGroupBox("CLI Output")
        cli_layout = QVBoxLayout(cli_group)

        self.manual_cli_text = QTextEdit()
        self.manual_cli_text.setFont(QFont("Consolas", 10))
        self.manual_cli_text.setPlaceholderText("Paste CLI output here...")
        cli_layout.addWidget(self.manual_cli_text)

        top_layout.addWidget(cli_group)

        splitter.addWidget(top_widget)

        # Bottom - Results
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)

        # Parse button
        btn_layout = QHBoxLayout()
        self.manual_parse_btn = QPushButton("Parse with TTP")
        self.manual_parse_btn.clicked.connect(self.run_manual_parse)
        btn_layout.addWidget(self.manual_parse_btn)

        self.manual_clear_btn = QPushButton("Clear All")
        self.manual_clear_btn.clicked.connect(self.clear_manual)
        btn_layout.addWidget(self.manual_clear_btn)

        btn_layout.addStretch()
        bottom_layout.addLayout(btn_layout)

        # Results
        results_group = QGroupBox("Parsed Results")
        results_layout = QVBoxLayout(results_group)

        self.manual_results_table = QTableWidget()
        self.manual_results_table.setAlternatingRowColors(True)
        results_layout.addWidget(self.manual_results_table)

        # Raw JSON output
        self.manual_json_output = QTextEdit()
        self.manual_json_output.setFont(QFont("Consolas", 9))
        self.manual_json_output.setReadOnly(True)
        self.manual_json_output.setMaximumHeight(150)
        results_layout.addWidget(self.manual_json_output)

        bottom_layout.addWidget(results_group)

        splitter.addWidget(bottom_widget)

        layout.addWidget(splitter)

        self.main_tabs.addTab(tab, "Manual Test")

    def create_manager_tab(self):
        """Create the Template Manager tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.mgr_search_input = QLineEdit()
        self.mgr_search_input.setPlaceholderText("Filter templates...")
        self.mgr_search_input.textChanged.connect(self.filter_templates)
        search_layout.addWidget(self.mgr_search_input)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_all_templates)
        search_layout.addWidget(refresh_btn)

        layout.addLayout(search_layout)

        # Templates table
        self.mgr_table = QTableWidget()
        self.mgr_table.setColumnCount(6)
        self.mgr_table.setHorizontalHeaderLabels([
            "ID", "Command", "TTP Rows", "Match Ratio", "Source", "Created"
        ])
        self.mgr_table.horizontalHeader().setStretchLastSection(True)
        self.mgr_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.mgr_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.mgr_table.customContextMenuRequested.connect(self.show_template_context_menu)
        self.mgr_table.itemDoubleClicked.connect(self.edit_template)
        layout.addWidget(self.mgr_table)

        # Action buttons
        btn_layout = QHBoxLayout()

        add_btn = QPushButton("Add Template")
        add_btn.clicked.connect(self.add_template)
        btn_layout.addWidget(add_btn)

        edit_btn = QPushButton("Edit Selected")
        edit_btn.clicked.connect(self.edit_selected_template)
        btn_layout.addWidget(edit_btn)

        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self.delete_selected_template)
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()

        export_btn = QPushButton("Export All")
        export_btn.clicked.connect(self.export_all_templates)
        btn_layout.addWidget(export_btn)

        import_btn = QPushButton("Import from Directory")
        import_btn.clicked.connect(self.import_from_directory)
        btn_layout.addWidget(import_btn)

        layout.addLayout(btn_layout)

        self.main_tabs.addTab(tab, "Template Manager")

    # =========================================================================
    # THEME AND DATABASE
    # =========================================================================

    def apply_current_theme(self):
        """Apply the current theme"""
        apply_theme(self, self.current_theme)

    def change_theme(self, theme_name: str):
        """Change the application theme"""
        self.current_theme = theme_name
        self.apply_current_theme()

    def browse_database(self):
        """Browse for a database file"""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select TTP Database", "", "SQLite Database (*.db);;All Files (*)"
        )
        if path:
            self.db_path_input.setText(path)
            self.reload_database()

    def reload_database(self):
        """Reload the database"""
        self.db_path = self.db_path_input.text()

        if TTP_ENGINE_AVAILABLE and Path(self.db_path).exists():
            try:
                self.engine = TTPAutoEngine(self.db_path)
                self.statusBar().showMessage(f"Loaded database: {self.db_path}")
                self.load_all_templates()
            except Exception as e:
                self.statusBar().showMessage(f"Error: {e}")
                QMessageBox.critical(self, "Error", f"Failed to load database: {e}")
        else:
            self.statusBar().showMessage("Database not found or TTP engine not available")

    def get_db_connection(self) -> Optional[sqlite3.Connection]:
        """Get a database connection"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            QMessageBox.critical(self, "Database Error", str(e))
            return None

    # =========================================================================
    # AUTO TEST
    # =========================================================================

    def run_auto_test(self):
        """Run auto-matching test"""
        if not self.engine:
            QMessageBox.warning(self, "Warning", "No database loaded or TTP engine not available")
            return

        cli_output = self.auto_cli_input.toPlainText()
        if not cli_output.strip():
            QMessageBox.warning(self, "Warning", "Please enter CLI output to test")
            return

        filter_str = self.auto_filter_input.text().strip()

        self.auto_test_btn.setEnabled(False)
        self.auto_test_btn.setText("Testing...")
        self.statusBar().showMessage("Running auto-test...")

        # Run in thread
        self.auto_worker = AutoTestWorker(self.engine, cli_output, filter_str)
        self.auto_worker.result.connect(self.on_auto_test_complete)
        self.auto_worker.error.connect(self.on_auto_test_error)
        self.auto_worker.start()

    def on_auto_test_complete(self, best_template: str, parsed: list, score: float, all_scores: list):
        """Handle auto-test completion"""
        self.auto_test_btn.setEnabled(True)
        self.auto_test_btn.setText("Find Best Template")

        # Update scores table
        self.auto_scores_table.setRowCount(len(all_scores))
        for i, (template, score, records) in enumerate(all_scores):
            self.auto_scores_table.setItem(i, 0, QTableWidgetItem(template))
            self.auto_scores_table.setItem(i, 1, QTableWidgetItem(f"{score:.2f}"))
            self.auto_scores_table.setItem(i, 2, QTableWidgetItem(str(records)))

            # Highlight best match
            if template == best_template:
                for j in range(3):
                    item = self.auto_scores_table.item(i, j)
                    item.setBackground(QColor("#28a745"))

        self.auto_scores_table.resizeColumnsToContents()

        # Update results table
        self.populate_results_table(self.auto_results_table, parsed)

        if best_template:
            self.statusBar().showMessage(f"Best match: {best_template} (score: {score:.2f})")
        else:
            self.statusBar().showMessage("No matching template found")

    def on_auto_test_error(self, error: str):
        """Handle auto-test error"""
        self.auto_test_btn.setEnabled(True)
        self.auto_test_btn.setText("Find Best Template")
        self.statusBar().showMessage(f"Error: {error}")
        QMessageBox.critical(self, "Error", error)

    def load_template_to_manual(self, item):
        """Load selected template to manual test tab"""
        row = item.row()
        template_name = self.auto_scores_table.item(row, 0).text()

        if self.engine:
            template_content = self.engine.get_template(template_name)
            if template_content:
                self.manual_template_text.setPlainText(template_content)
                self.manual_cli_text.setPlainText(self.auto_cli_input.toPlainText())
                self.main_tabs.setCurrentIndex(1)
                self.statusBar().showMessage(f"Loaded template: {template_name}")

    # =========================================================================
    # MANUAL TEST
    # =========================================================================

    def run_manual_parse(self):
        """Run manual TTP parsing"""
        template = self.manual_template_text.toPlainText()
        cli_output = self.manual_cli_text.toPlainText()

        if not template.strip():
            QMessageBox.warning(self, "Warning", "Please enter a TTP template")
            return

        if not cli_output.strip():
            QMessageBox.warning(self, "Warning", "Please enter CLI output")
            return

        success, results, error = parse_with_ttp(template, cli_output)

        if success:
            self.populate_results_table(self.manual_results_table, results)

            # Show raw JSON
            try:
                from ttp import ttp as ttp_lib
                with warnings.catch_warnings():
                    warnings.filterwarnings('ignore', category=SyntaxWarning)
                    parser = ttp_lib(data=cli_output, template=template)
                    parser.parse()
                    raw_results = parser.result()
                self.manual_json_output.setPlainText(json.dumps(raw_results, indent=2))
            except Exception as e:
                self.manual_json_output.setPlainText(f"Error getting raw results: {e}")

            self.statusBar().showMessage(f"Parsed {len(results)} records")
        else:
            QMessageBox.critical(self, "Parse Error", error)
            self.statusBar().showMessage(f"Parse failed: {error}")

    def clear_manual(self):
        """Clear manual test fields"""
        self.manual_template_text.clear()
        self.manual_cli_text.clear()
        self.manual_results_table.setRowCount(0)
        self.manual_results_table.setColumnCount(0)
        self.manual_json_output.clear()

    def populate_results_table(self, table: QTableWidget, results: list):
        """Populate a results table with parsed data"""
        if not results:
            table.setRowCount(0)
            table.setColumnCount(0)
            return

        # Get all unique keys
        all_keys = set()
        for record in results:
            all_keys.update(record.keys())
        keys = sorted(all_keys)

        table.setColumnCount(len(keys))
        table.setHorizontalHeaderLabels(keys)
        table.setRowCount(len(results))

        for i, record in enumerate(results):
            for j, key in enumerate(keys):
                value = record.get(key, "")
                table.setItem(i, j, QTableWidgetItem(str(value) if value else ""))

        table.resizeColumnsToContents()

    # =========================================================================
    # TEMPLATE MANAGER
    # =========================================================================

    def load_all_templates(self):
        """Load all templates from database"""
        conn = self.get_db_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, cli_command, ttp_rows, match_ratio, source, created_at 
                FROM templates ORDER BY cli_command
            """)
            templates = cursor.fetchall()
            conn.close()

            self.mgr_table.setRowCount(len(templates))
            for i, t in enumerate(templates):
                self.mgr_table.setItem(i, 0, QTableWidgetItem(str(t['id'])))
                self.mgr_table.setItem(i, 1, QTableWidgetItem(t['cli_command']))
                self.mgr_table.setItem(i, 2, QTableWidgetItem(str(t['ttp_rows'] or '')))
                self.mgr_table.setItem(i, 3, QTableWidgetItem(f"{t['match_ratio']:.2f}" if t['match_ratio'] else ''))
                self.mgr_table.setItem(i, 4, QTableWidgetItem(t['source'] or ''))
                self.mgr_table.setItem(i, 5, QTableWidgetItem(t['created_at'] or ''))

            self.mgr_table.resizeColumnsToContents()
            self.statusBar().showMessage(f"Loaded {len(templates)} templates")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load templates: {e}")

    def filter_templates(self, text: str):
        """Filter templates table by search text"""
        for i in range(self.mgr_table.rowCount()):
            command_item = self.mgr_table.item(i, 1)
            if command_item:
                match = text.lower() in command_item.text().lower()
                self.mgr_table.setRowHidden(i, not match)

    def show_template_context_menu(self, pos):
        """Show context menu for template table"""
        menu = QMenu(self)

        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(self.edit_selected_template)

        test_action = menu.addAction("Test in Manual Tab")
        test_action.triggered.connect(self.test_selected_in_manual)

        menu.addSeparator()

        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_selected_template)

        menu.exec(self.mgr_table.mapToGlobal(pos))

    def add_template(self):
        """Add a new template"""
        dialog = TemplateEditDialog(self, "Add Template")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()

            conn = self.get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO templates (cli_command, ttp_content, source, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (data['command'], data['template'], 'manual', datetime.now().isoformat()))
                    conn.commit()
                    conn.close()

                    self.statusBar().showMessage(f"Added template: {data['command']}")
                    self.load_all_templates()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to add template: {e}")

    def edit_template(self, item=None):
        """Edit a template"""
        self.edit_selected_template()

    def edit_selected_template(self):
        """Edit the selected template"""
        selected = self.mgr_table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        template_id = self.mgr_table.item(row, 0).text()

        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
            template = dict(cursor.fetchone())
            conn.close()

            dialog = TemplateEditDialog(self, "Edit Template", template)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                data = dialog.get_data()

                conn = self.get_db_connection()
                if conn:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE templates SET cli_command = ?, ttp_content = ?
                            WHERE id = ?
                        """, (data['command'], data['template'], template_id))
                        conn.commit()
                        conn.close()

                        self.statusBar().showMessage(f"Updated template: {data['command']}")
                        self.load_all_templates()
                    except Exception as e:
                        QMessageBox.critical(self, "Error", f"Failed to update template: {e}")

    def delete_selected_template(self):
        """Delete the selected template"""
        selected = self.mgr_table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        template_id = self.mgr_table.item(row, 0).text()
        command = self.mgr_table.item(row, 1).text()

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete template '{command}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            conn = self.get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM templates WHERE id = ?", (template_id,))
                    conn.commit()
                    conn.close()

                    self.statusBar().showMessage(f"Deleted template: {command}")
                    self.load_all_templates()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to delete: {e}")

    def test_selected_in_manual(self):
        """Load selected template into manual test tab"""
        selected = self.mgr_table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        template_id = self.mgr_table.item(row, 0).text()

        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ttp_content, cli_content FROM templates WHERE id = ?", (template_id,))
            result = cursor.fetchone()
            conn.close()

            if result:
                self.manual_template_text.setPlainText(result['ttp_content'] or '')
                self.manual_cli_text.setPlainText(result['cli_content'] or '')
                self.main_tabs.setCurrentIndex(1)
                self.statusBar().showMessage("Template loaded into Manual Test tab")

    def export_all_templates(self):
        """Export all templates to a directory"""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if not dir_path:
            return

        conn = self.get_db_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT cli_command, ttp_content FROM templates")
            templates = cursor.fetchall()
            conn.close()

            export_dir = Path(dir_path)
            exported = 0

            for t in templates:
                if t['ttp_content']:
                    file_path = export_dir / f"{t['cli_command']}.ttp"
                    with open(file_path, 'w') as f:
                        f.write(t['ttp_content'])
                    exported += 1

            self.statusBar().showMessage(f"Exported {exported} templates")
            QMessageBox.information(self, "Export Complete", f"Exported {exported} templates to {dir_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed: {e}")

    def import_from_directory(self):
        """Import TTP templates from a directory"""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Templates Directory")
        if not dir_path:
            return

        templates_dir = Path(dir_path)
        ttp_files = list(templates_dir.glob("*.ttp"))

        if not ttp_files:
            QMessageBox.warning(self, "Warning", "No .ttp files found")
            return

        conn = self.get_db_connection()
        if not conn:
            return

        imported = 0
        skipped = 0

        try:
            cursor = conn.cursor()

            for file_path in ttp_files:
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()

                    cli_command = file_path.stem

                    cursor.execute("SELECT id FROM templates WHERE cli_command = ?", (cli_command,))
                    if cursor.fetchone():
                        skipped += 1
                        continue

                    cursor.execute("""
                        INSERT INTO templates (cli_command, ttp_content, source, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (cli_command, content, 'imported', datetime.now().isoformat()))
                    imported += 1
                except Exception as e:
                    print(f"Error importing {file_path}: {e}")

            conn.commit()
            conn.close()

            self.statusBar().showMessage(f"Imported {imported}, skipped {skipped}")
            QMessageBox.information(self, "Import Complete", f"Imported: {imported}\nSkipped: {skipped}")
            self.load_all_templates()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Import failed: {e}")


# =============================================================================
# TEMPLATE EDIT DIALOG
# =============================================================================

class TemplateEditDialog(QDialog):
    """Dialog for adding/editing templates"""

    def __init__(self, parent, title: str, template: dict = None):
        super().__init__(parent)
        self.template = template or {}
        self.setWindowTitle(title)
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)

        # Command name
        form_layout = QFormLayout()
        self.command_input = QLineEdit(self.template.get('cli_command', ''))
        form_layout.addRow("Command:", self.command_input)
        layout.addLayout(form_layout)

        # Template content
        layout.addWidget(QLabel("TTP Template:"))
        self.template_text = QTextEdit()
        self.template_text.setFont(QFont("Consolas", 10))
        self.template_text.setPlainText(self.template.get('ttp_content', ''))
        layout.addWidget(self.template_text)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> dict:
        return {
            'command': self.command_input.text(),
            'template': self.template_text.toPlainText()
        }


# =============================================================================
# MAIN
# =============================================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Check for database path argument
    db_path = sys.argv[1] if len(sys.argv) > 1 else None

    window = TTPTester(db_path)
    window.show()

    # Load templates on startup
    if Path(window.db_path).exists():
        window.load_all_templates()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()