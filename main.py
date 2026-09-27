import sys
import sqlite3
import shutil
import os
import platform
from pathlib import Path
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QAction
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QDialog,
    QFormLayout,
    QStackedWidget,
    QFrame,
    QAbstractItemView,
    QDateEdit,
    QTextEdit,
    QGroupBox,
    QCheckBox,
    QMenu,
    QInputDialog,
    QProgressBar,
)


# ============================================================
# CROSS-PLATFORM PATHS
# ============================================================

def get_app_dirs():
    """Get platform-appropriate directories for app data, config, cache."""
    system = platform.system().lower()
    home = Path.home()
    
    if system == "windows":
        # Windows: %LOCALAPPDATA%\PATOGH
        base = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        app_data = base / "PATOGH"
    elif system == "darwin":
        # macOS: ~/Library/Application Support/PATOGH
        app_data = home / "Library" / "Application Support" / "PATOGH"
    else:
        # Linux/Unix: ~/.local/share/PATOGH (XDG spec)
        xdg_data = os.environ.get("XDG_DATA_HOME", home / ".local" / "share")
        app_data = Path(xdg_data) / "PATOGH"
    
    app_data.mkdir(parents=True, exist_ok=True)
    
    # Backup directory next to app data
    backup_dir = app_data / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Config directory (could be same as app_data or XDG_CONFIG_HOME)
    if system == "windows":
        config_dir = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming")) / "PATOGH"
    elif system == "darwin":
        config_dir = home / "Library" / "Preferences" / "PATOGH"
    else:
        xdg_config = os.environ.get("XDG_CONFIG_HOME", home / ".config")
        config_dir = Path(xdg_config) / "PATOGH"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    
    return {
        "app_data": app_data,
        "backup_dir": backup_dir,
        "config_dir": config_dir,
    }

_DIRS = get_app_dirs()
DB_PATH = _DIRS["app_data"] / "patogh.db"
BACKUP_DIR = _DIRS["backup_dir"]
CONFIG_DIR = _DIRS["config_dir"]


# ============================================================
# APPLICATION SETTINGS
# ============================================================

APP_NAME = "PATOGH"
APP_VERSION = "1.0.0"
CURRENCY = "AMD"


# ============================================================
# IRC SETTINGS
#
# Connection implementation lives in irc.py.
# These values are intentionally kept here.
# ============================================================

IRC_SETTINGS = {
    "enabled": True,
    "host": "irc.libera.chat",
    "port": 6697,
    "nickname": "PATOGH",
    "username": "patogh",
    "realname": "PATOGH Cafe",
    "channel": "#myCh",
    "password": "",
    "ssl": True,
    "auto_connect": True,
}


def load_irc_settings(db):
    """Load IRC settings from the database, falling back to defaults."""
    settings = dict(IRC_SETTINGS)
    try:
        rows = db.fetchall(
            "SELECT key, value FROM settings WHERE key LIKE 'irc_%'"
        )
        for row in rows:
            key = row["key"]
            if key.startswith("irc_"):
                field = key[4:]
                value = row["value"]
                if field == "port":
                    try:
                        settings[field] = int(value)
                    except (ValueError, TypeError):
                        pass
                elif field in ("enabled", "ssl", "auto_connect"):
                    settings[field] = value in ("1", "true", "True", "yes", "on")
                else:
                    settings[field] = value
    except Exception:
        pass
    return settings


def save_irc_settings(db, settings):
    """Persist IRC settings to the database."""
    for key, value in settings.items():
        db.execute(
            "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
            (f"irc_{key}", str(value)),
        )


# ============================================================
# HELPERS
# ============================================================

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


import random
import string


def today():
    return datetime.now().strftime("%Y-%m-%d")


def transaction_id():
    """Generate unique transaction ID with timestamp + random component."""
    timestamp = datetime.now().strftime("TX-%Y%m%d-%H%M%S-%f")[:-3]
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{timestamp}-{random_suffix}"


def money(value):
    try:
        return f"{float(value):,.0f} {CURRENCY}"
    except Exception:
        return f"0 {CURRENCY}"


def number(value):
    value = float(value)

    if value.is_integer():
        return str(int(value))

    return f"{value:.2f}"


def user_friendly_error(error: Exception) -> str:
    """Convert technical exceptions to user-friendly Persian messages."""
    error_str = str(error).lower()
    
    # SQLite integrity errors
    if "unique constraint failed" in error_str or "integrityerror" in type(error).__name__.lower():
        if "products.code" in error_str or "code" in error_str:
            return "این کد محصول قبلاً استفاده شده است. کد دیگری انتخاب کنید."
        return "اطلاعات تکراری است. لطفاً مقادیر را بررسی کنید."
    
    # Stock/quantity errors
    if "موجودی" in error_str and ("کافی نیست" in error_str or "منفی" in error_str):
        return "موجودی انبار برای این عملیات کافی نیست. ابتدا خرید ثبت کنید یا تعداد را کاهش دهید."
    
    if "stock" in error_str and ("insufficient" in error_str or "negative" in error_str):
        return "موجودی انبار برای این عملیات کافی نیست. ابتدا خرید ثبت کنید یا تعداد را کاهش دهید."
    
    # Connection errors
    if "connection" in error_str or "connect" in error_str:
        if "refused" in error_str or "timeout" in error_str:
            return "اتصال به سرور برقرار نشد. اینترنت را چک کنید و مجدد تلاش کنید."
        return "مشکل در اتصال. لطفاً اینترنت را بررسی کنید."
    
    # Database errors
    if "database" in error_str or "sqlite" in type(error).__name__.lower():
        if "locked" in error_str:
            return "دیتابیس در حال استفاده است. برنامه را مجدد اجرا کنید."
        return "خطای دیتابیس. برنامه را مجدد اجرا کنید."
    
    # File errors
    if "permission" in error_str or "access denied" in error_str:
        return "دسترسی به فایل امکان‌پذیر نیست. برنامه را به عنوان مدیر اجرا کنید یا مجوزها را چک کنید."
    
    if "no space" in error_str or "disk full" in error_str:
        return "فضای دیسک تمام شده. فایل‌های غیرضروری را حذف کنید."
    
    # Generic fallback - show simplified message
    msg = str(error)
    # Remove technical details
    technical_keywords = ["traceback", "file ", "line ", "sql", "cursor", "execute", "commit", "rollback"]
    if any(kw in msg.lower() for kw in technical_keywords):
        return "خطایی رخ داد. لطفاً مجدد تلاش کنید یا پشتیبانی را تماس بگیرید."
    
    return msg


# ============================================================
# DATABASE
# ============================================================

class Database:

    def __init__(self, path=DB_PATH):
        self.path = path

        self.conn = sqlite3.connect(
            str(self.path)
        )

        self.conn.row_factory = sqlite3.Row

        self.conn.execute(
            "PRAGMA foreign_keys = ON"
        )

        self.conn.execute(
            "PRAGMA journal_mode = WAL"
        )

        self.create_tables()
        self.seed()

    # --------------------------------------------------------
    # BASIC
    # --------------------------------------------------------

    def execute(self, sql, params=()):
        cursor = self.conn.cursor()

        cursor.execute(sql, params)

        self.conn.commit()

        return cursor

    def fetchone(self, sql, params=()):
        cursor = self.conn.cursor()

        cursor.execute(sql, params)

        return cursor.fetchone()

    def fetchall(self, sql, params=()):
        cursor = self.conn.cursor()

        cursor.execute(sql, params)

        return cursor.fetchall()

    def close(self):
        self.conn.close()

    # --------------------------------------------------------
    # TABLES
    # --------------------------------------------------------

    def create_tables(self):

        self.conn.executescript("""

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            code TEXT NOT NULL UNIQUE,

            name TEXT NOT NULL,

            category TEXT DEFAULT '',

            unit TEXT DEFAULT 'pcs',

            purchase_price REAL NOT NULL DEFAULT 0,

            sale_price REAL NOT NULL DEFAULT 0,

            stock REAL NOT NULL DEFAULT 0,

            min_stock REAL NOT NULL DEFAULT 0,

            active INTEGER NOT NULL DEFAULT 1,

            created_at TEXT NOT NULL,

            updated_at TEXT NOT NULL
        );


        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            transaction_id TEXT NOT NULL UNIQUE,

            customer_name TEXT DEFAULT '',

            total REAL NOT NULL,

            payment_method TEXT NOT NULL DEFAULT 'CASH',

            created_at TEXT NOT NULL
        );


        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            sale_id INTEGER NOT NULL,

            product_id INTEGER NOT NULL,

            quantity REAL NOT NULL,

            unit_price REAL NOT NULL,

            purchase_price REAL NOT NULL,

            total REAL NOT NULL,

            FOREIGN KEY (sale_id)
                REFERENCES sales(id),

            FOREIGN KEY (product_id)
                REFERENCES products(id)
        );


        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            transaction_id TEXT NOT NULL UNIQUE,

            supplier TEXT DEFAULT '',

            total REAL NOT NULL,

            payment_method TEXT NOT NULL DEFAULT 'CASH',

            note TEXT DEFAULT '',

            created_at TEXT NOT NULL
        );


        CREATE TABLE IF NOT EXISTS purchase_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            purchase_id INTEGER NOT NULL,

            product_id INTEGER NOT NULL,

            quantity REAL NOT NULL,

            unit_cost REAL NOT NULL,

            total REAL NOT NULL,

            FOREIGN KEY (purchase_id)
                REFERENCES purchases(id),

            FOREIGN KEY (product_id)
                REFERENCES products(id)
        );


        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            transaction_id TEXT NOT NULL UNIQUE,

            category TEXT NOT NULL,

            amount REAL NOT NULL,

            description TEXT DEFAULT '',

            payment_method TEXT NOT NULL DEFAULT 'CASH',

            created_at TEXT NOT NULL
        );


        CREATE TABLE IF NOT EXISTS cash_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            transaction_id TEXT NOT NULL UNIQUE,

            type TEXT NOT NULL,

            amount REAL NOT NULL,

            description TEXT DEFAULT '',

            reference_id TEXT DEFAULT '',

            created_at TEXT NOT NULL
        );


        CREATE TABLE IF NOT EXISTS inventory_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            transaction_id TEXT NOT NULL UNIQUE,

            product_id INTEGER NOT NULL,

            type TEXT NOT NULL,

            quantity REAL NOT NULL,

            previous_stock REAL NOT NULL,

            new_stock REAL NOT NULL,

            reason TEXT DEFAULT '',

            created_at TEXT NOT NULL,

            FOREIGN KEY (product_id)
                REFERENCES products(id)
        );


        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT NOT NULL UNIQUE,

            password TEXT NOT NULL,

            role TEXT NOT NULL DEFAULT 'ADMIN',

            active INTEGER NOT NULL DEFAULT 1,

            created_at TEXT NOT NULL
        );


        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,

            value TEXT NOT NULL
        );

        """)

        self.conn.commit()

    # --------------------------------------------------------
    # SEED
    # --------------------------------------------------------

    def seed(self):

        product_count = self.fetchone(
            "SELECT COUNT(*) AS count FROM products"
        )["count"]

        if product_count == 0:

            timestamp = now()

            demo_products = [

                (
                    "1",
                    "قهوه",
                    "نوشیدنی",
                    "cup",
                    1500,
                    4000,
                    0,
                    5
                ),

                (
                    "2",
                    "آب",
                    "نوشیدنی",
                    "bottle",
                    500,
                    1500,
                    0,
                    10
                ),

                (
                    "3",
                    "نوشابه",
                    "نوشیدنی",
                    "bottle",
                    1000,
                    2500,
                    0,
                    10
                ),

                (
                    "4",
                    "آبجو",
                    "نوشیدنی",
                    "bottle",
                    3500,
                    5000,
                    0,
                    5
                ),

                (
                    "5",
                    "شیر",
                    "مواد اولیه",
                    "liter",
                    2500,
                    5000,
                    0,
                    3
                ),

                (
                    "6",
                    "شکر",
                    "مواد اولیه",
                    "kg",
                    1800,
                    3500,
                    0,
                    3
                ),

                (
                    "101",
                    "دانه قهوه",
                    "مواد اولیه",
                    "kg",
                    15000,
                    25000,
                    0,
                    2
                ),
            ]

            for product in demo_products:

                self.conn.execute("""
                    INSERT INTO products (
                        code,
                        name,
                        category,
                        unit,
                        purchase_price,
                        sale_price,
                        stock,
                        min_stock,
                        created_at,
                        updated_at
                    )

                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (*product, timestamp, timestamp))

        user = self.fetchone(
            "SELECT id FROM users WHERE username = ?",
            ("admin",)
        )

        if not user:

            self.conn.execute("""
                INSERT INTO users (
                    username,
                    password,
                    role,
                    created_at
                )

                VALUES (?, ?, ?, ?)
            """, (
                "admin",
                "admin",
                "ADMIN",
                now()
            ))

        self.conn.execute("""
            INSERT OR IGNORE INTO settings(key, value)
            VALUES ('currency', 'AMD')
        """)

        self.conn.commit()

    # --------------------------------------------------------
    # TRANSACTION HELPERS
    # --------------------------------------------------------

    def add_cash(
        self,
        tx_type,
        amount,
        description="",
        reference=""
    ):

        self.conn.execute("""
            INSERT INTO cash_transactions (
                transaction_id,
                type,
                amount,
                description,
                reference_id,
                created_at
            )

            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            transaction_id(),
            tx_type,
            amount,
            description,
            reference,
            now()
        ))

    def inventory_change(
        self,
        product_id,
        quantity,
        tx_type,
        reason="",
        reference=""
    ):

        product = self.fetchone("""
            SELECT stock
            FROM products
            WHERE id = ?
        """, (product_id,))

        if not product:
            raise ValueError("Product not found")

        old_stock = float(product["stock"])

        new_stock = old_stock + quantity

        if new_stock < 0:
            raise ValueError(
                "موجودی برای این عملیات کافی نیست."
            )

        self.conn.execute("""
            UPDATE products
            SET stock = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            new_stock,
            now(),
            product_id
        ))

        self.conn.execute("""
            INSERT INTO inventory_transactions (
                transaction_id,
                product_id,
                type,
                quantity,
                previous_stock,
                new_stock,
                reason,
                created_at
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            reference or transaction_id(),
            product_id,
            tx_type,
            quantity,
            old_stock,
            new_stock,
            reason,
            now()
        ))

    # --------------------------------------------------------
    # CASH BALANCE
    # --------------------------------------------------------

    def cash_balance(self):

        row = self.fetchone("""
            SELECT COALESCE(
                SUM(
                    CASE

                        WHEN type IN ('SALE', 'CASH_IN')
                        THEN amount

                        WHEN type IN (
                            'PURCHASE',
                            'EXPENSE',
                            'CASH_OUT',
                            'REFUND'
                        )
                        THEN -amount

                        ELSE 0

                    END
                ),
                0
            ) AS balance

            FROM cash_transactions
        """)

        return float(row["balance"] or 0)


# ============================================================
# PRODUCT DIALOG
# ============================================================

class ProductDialog(QDialog):

    def __init__(
        self,
        db,
        product=None,
        parent=None
    ):

        super().__init__(parent)

        self.db = db
        self.product = product

        self.setWindowTitle(
            "افزودن محصول"
            if product is None
            else "ویرایش محصول"
        )

        self.setMinimumWidth(450)

        layout = QFormLayout(self)

        self.code = QLineEdit()
        self.name = QLineEdit()
        self.category = QLineEdit()
        self.unit = QLineEdit()

        self.purchase_price = QDoubleSpinBox()
        self.purchase_price.setMaximum(999999999)
        self.purchase_price.setDecimals(0)

        self.sale_price = QDoubleSpinBox()
        self.sale_price.setMaximum(999999999)
        self.sale_price.setDecimals(0)

        self.stock = QDoubleSpinBox()
        self.stock.setMaximum(999999999)
        self.stock.setDecimals(2)

        self.min_stock = QDoubleSpinBox()
        self.min_stock.setMaximum(999999999)
        self.min_stock.setDecimals(2)

        layout.addRow("کد محصول:", self.code)
        layout.addRow("نام:", self.name)
        layout.addRow("دسته‌بندی:", self.category)
        layout.addRow("واحد شمارش:", self.unit)
        layout.addRow(
            "قیمت خرید کافه:",
            self.purchase_price
        )
        layout.addRow(
            "قیمت فروش به مشتری:",
            self.sale_price
        )
        layout.addRow(
            "موجودی انبار:",
            self.stock
        )
        layout.addRow(
            "حداقل موجودی (هشدار):",
            self.min_stock
        )

        buttons = QHBoxLayout()

        cancel = QPushButton("انصراف")

        save = QPushButton("ذخیره")
        save.setObjectName("Primary")

        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.save)

        buttons.addWidget(cancel)
        buttons.addWidget(save)

        layout.addRow(buttons)

        if product:

            self.code.setText(
                product["code"]
            )

            self.name.setText(
                product["name"]
            )

            self.category.setText(
                product["category"]
            )

            self.unit.setText(
                product["unit"]
            )

            self.purchase_price.setValue(
                product["purchase_price"]
            )

            self.sale_price.setValue(
                product["sale_price"]
            )

            self.stock.setValue(
                product["stock"]
            )

            self.min_stock.setValue(
                product["min_stock"]
            )

    def save(self):

        code = self.code.text().strip()
        name = self.name.text().strip()

        if not code:
            QMessageBox.warning(
                self,
                "خطا",
                "کد محصول را وارد کنید."
            )
            return

        if not name:
            QMessageBox.warning(
                self,
                "خطا",
                "نام محصول را وارد کنید."
            )
            return

        timestamp = now()

        try:

            if self.product:

                self.db.execute("""
                    UPDATE products

                    SET
                        code = ?,
                        name = ?,
                        category = ?,
                        unit = ?,
                        purchase_price = ?,
                        sale_price = ?,
                        stock = ?,
                        min_stock = ?,
                        updated_at = ?

                    WHERE id = ?
                """, (
                    code,
                    name,
                    self.category.text().strip(),
                    self.unit.text().strip() or "pcs",
                    self.purchase_price.value(),
                    self.sale_price.value(),
                    self.stock.value(),
                    self.min_stock.value(),
                    timestamp,
                    self.product["id"]
                ))

            else:

                self.db.execute("""
                    INSERT INTO products (
                        code,
                        name,
                        category,
                        unit,
                        purchase_price,
                        sale_price,
                        stock,
                        min_stock,
                        created_at,
                        updated_at
                    )

                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    code,
                    name,
                    self.category.text().strip(),
                    self.unit.text().strip() or "pcs",
                    self.purchase_price.value(),
                    self.sale_price.value(),
                    self.stock.value(),
                    self.min_stock.value(),
                    timestamp,
                    timestamp
                ))

            self.accept()

        except sqlite3.IntegrityError as e:

            QMessageBox.warning(
                self,
                "خطا",
                user_friendly_error(e)
            )
# SIMPLE IRC CONNECTION
# ============================================================

def connect_irc(settings, parent_widget=None):
    """Connect to IRC and return IRCManager or None on failure."""
    from irc import IRCManager
    from PyQt6.QtWidgets import QProgressDialog, QApplication
    from PyQt6.QtCore import Qt, QTimer, QEventLoop

    if parent_widget:
        progress = QProgressDialog("در حال اتصال به سرور IRC...", "انصراف", 0, 0, parent_widget)
        progress.setWindowTitle("اتصال IRC")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()
    else:
        progress = None

    mgr = IRCManager(settings)
    connected = [False]
    error_msg = [None]
    loop = QEventLoop()

    def on_connected():
        connected[0] = True
        loop.quit()

    def on_error(err):
        error_msg[0] = str(err)
        loop.quit()

    mgr.connect(on_connected=on_connected, on_error=on_error)

    # Wait with timeout
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(30000)  # 30 second timeout

    loop.exec()

    if progress:
        progress.close()

    if connected[0]:
        return mgr
    else:
        if error_msg[0]:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(parent_widget, "خطای اتصال IRC", user_friendly_error(Exception(error_msg[0])))
        return None


# ============================================================
# SIMPLE IRC CONNECTION
# ============================================================

def connect_irc(settings, parent_widget=None):
    """Connect to IRC and return IRCManager or None on failure."""
    from irc import IRCManager
    from PyQt6.QtWidgets import QProgressDialog, QApplication
    from PyQt6.QtCore import Qt, QTimer, QEventLoop

    if parent_widget:
        progress = QProgressDialog("در حال اتصال به سرور IRC...", "انصراف", 0, 0, parent_widget)
        progress.setWindowTitle("اتصال IRC")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()
    else:
        progress = None

    mgr = IRCManager(settings)
    connected = [False]
    error_msg = [None]
    loop = QEventLoop()

    def on_connected():
        connected[0] = True
        loop.quit()

    def on_error(err):
        error_msg[0] = str(err)
        loop.quit()

    mgr.connect(on_connected=on_connected, on_error=on_error)

    # Wait with timeout
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(30000)  # 30 second timeout

    loop.exec()

    if progress:
        progress.close()

    if connected[0]:
        return mgr
    else:
        if error_msg[0]:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(parent_widget, "خطای اتصال IRC", user_friendly_error(Exception(error_msg[0])))
        return None


# ============================================================
# DASHBOARD
# ============================================================

# ============================================================
# DASHBOARD
# ============================================================

class DashboardPage(QWidget):

    def __init__(self, db):

        super().__init__()

        self.db = db

        root = QVBoxLayout(self)

        title = QLabel("داشبورد")
        title.setObjectName("PageTitle")

        root.addWidget(title)

        cards = QGridLayout()

        self.sales_card = self.create_card(
            "فروش امروز"
        )

        self.purchase_card = self.create_card(
            "خرید امروز"
        )

        self.expense_card = self.create_card(
            "هزینه امروز"
        )

        self.cash_card = self.create_card(
            "صندوق"
        )

        cards.addWidget(
            self.sales_card,
            0,
            0
        )

        cards.addWidget(
            self.purchase_card,
            0,
            1
        )

        cards.addWidget(
            self.expense_card,
            0,
            2
        )

        cards.addWidget(
            self.cash_card,
            0,
            3
        )

        root.addLayout(cards)

        low_title = QLabel(
            "موجودی پایین"
        )

        low_title.setStyleSheet(
            "font-size:17px;font-weight:700;"
            "margin-top:15px;"
        )

        root.addWidget(low_title)

        self.low_table = QTableWidget()

        self.low_table.setColumnCount(4)

        self.low_table.setHorizontalHeaderLabels([
            "کد",
            "محصول",
            "موجودی",
            "حداقل"
        ])

        self.low_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self.low_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        root.addWidget(
            self.low_table
        )

        refresh = QPushButton(
            "به‌روزرسانی"
        )

        refresh.clicked.connect(
            self.refresh
        )

        root.addWidget(refresh)

        self.refresh()

    def create_card(self, title):

        frame = QFrame()

        frame.setObjectName(
            "Card"
        )

        layout = QVBoxLayout(frame)

        label = QLabel(title)

        label.setObjectName(
            "CardTitle"
        )

        value = QLabel(
            money(0)
        )

        value.setObjectName(
            "CardValue"
        )

        layout.addWidget(label)
        layout.addWidget(value)

        frame.value_label = value

        return frame

    def refresh(self):

        start = (
            datetime.now()
            .strftime("%Y-%m-%d")
            + " 00:00:00"
        )

        sales = self.db.fetchone("""
            SELECT COALESCE(
                SUM(total), 0
            ) AS value

            FROM sales

            WHERE created_at >= ?
        """, (start,))["value"]

        purchases = self.db.fetchone("""
            SELECT COALESCE(
                SUM(total), 0
            ) AS value

            FROM purchases

            WHERE created_at >= ?
        """, (start,))["value"]

        expenses = self.db.fetchone("""
            SELECT COALESCE(
                SUM(amount), 0
            ) AS value

            FROM expenses

            WHERE created_at >= ?
        """, (start,))["value"]

        cash = self.db.cash_balance()

        self.sales_card.value_label.setText(
            money(sales)
        )

        self.purchase_card.value_label.setText(
            money(purchases)
        )

        self.expense_card.value_label.setText(
            money(expenses)
        )

        self.cash_card.value_label.setText(
            money(cash)
        )

        rows = self.db.fetchall("""
            SELECT
                code,
                name,
                stock,
                min_stock

            FROM products

            WHERE active = 1

            AND stock <= min_stock

            ORDER BY stock ASC
        """)

        self.low_table.setRowCount(
            len(rows)
        )

        for r, row in enumerate(rows):

            values = [
                row["code"],
                row["name"],
                number(row["stock"]),
                number(row["min_stock"])
            ]

            for c, value in enumerate(values):

                self.low_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(
                        str(value)
                    )
                )


# ============================================================
# PRODUCTS PAGE
# ============================================================

class ProductsPage(QWidget):

    def __init__(self, db):

        super().__init__()

        self.db = db

        root = QVBoxLayout(self)

        title = QLabel(
            "محصولات"
        )

        title.setObjectName(
            "PageTitle"
        )

        root.addWidget(title)

        toolbar = QHBoxLayout()

        self.search = QLineEdit()

        self.search.setPlaceholderText(
            "جستجو با کد، نام یا دسته..."
        )

        add = QPushButton(
            "＋ افزودن محصول"
        )

        add.setObjectName(
            "Primary"
        )

        refresh = QPushButton(
            "به‌روزرسانی"
        )

        toolbar.addWidget(
            self.search
        )

        toolbar.addWidget(
            refresh
        )

        toolbar.addWidget(
            add
        )

        root.addLayout(
            toolbar
        )

        self.table = QTableWidget()

        self.table.setColumnCount(9)

        self.table.setHorizontalHeaderLabels([
            "شناسه",
            "کد محصول",
            "نام",
            "دسته‌بندی",
            "واحد",
            "قیمت خرید کافه",
            "قیمت فروش به مشتری",
            "موجودی انبار",
            "حداقل موجودی"
        ])

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.table.doubleClicked.connect(
            self.edit_selected
        )

        root.addWidget(
            self.table
        )

        self.search.textChanged.connect(
            self.refresh
        )

        refresh.clicked.connect(
            self.refresh
        )

        add.clicked.connect(
            self.add_product
        )

        self.refresh()

    def refresh(self):

        search = self.search.text().strip()

        rows = self.db.fetchall("""
            SELECT *

            FROM products

            WHERE active = 1

            AND (
                code LIKE ?
                OR name LIKE ?
                OR category LIKE ?
            )

            ORDER BY id DESC
        """, (
            f"%{search}%",
            f"%{search}%",
            f"%{search}%"
        ))

        self.table.setRowCount(
            len(rows)
        )

        for r, row in enumerate(rows):

            values = [
                row["id"],
                row["code"],
                row["name"],
                row["category"],
                row["unit"],
                money(row["purchase_price"]),
                money(row["sale_price"]),
                number(row["stock"]),
                number(row["min_stock"])
            ]

            for c, value in enumerate(values):

                self.table.setItem(
                    r,
                    c,
                    QTableWidgetItem(
                        str(value)
                    )
                )

    def add_product(self):

        dialog = ProductDialog(
            self.db,
            parent=self
        )

        if dialog.exec():

            self.refresh()

    def edit_selected(self):

        row = self.table.currentRow()

        if row < 0:
            return

        product_id = int(
            self.table.item(
                row,
                0
            ).text()
        )

        product = self.db.fetchone("""
            SELECT *
            FROM products
            WHERE id = ?
        """, (product_id,))

        if product:

            dialog = ProductDialog(
                self.db,
                product,
                self
            )

            if dialog.exec():

                self.refresh()


# ============================================================
# SALES PAGE
# ============================================================

class SalesPage(QWidget):

    def __init__(self, db):

        super().__init__()

        self.db = db
        self.cart = []
        self.irc = None

        root = QVBoxLayout(self)

        title = QLabel("فروش")

        title.setObjectName(
            "PageTitle"
        )

        root.addWidget(title)

        form = QHBoxLayout()

        self.product_input = QLineEdit()

        self.product_input.setPlaceholderText(
            "کد یا نام محصول"
        )

        self.quantity = QDoubleSpinBox()

        self.quantity.setMinimum(0.01)
        self.quantity.setMaximum(999999)
        self.quantity.setValue(1)
        self.quantity.setDecimals(2)

        self.payment = QComboBox()

        self.payment.addItems([
            "CASH",
            "CARD",
            "OTHER"
        ])

        self.customer_name = QLineEdit()
        self.customer_name.setPlaceholderText("نام خریدار (اختیاری)")

        add = QPushButton(
            "افزودن"
        )

        add.setObjectName(
            "Primary"
        )

        form.addWidget(
            self.product_input
        )

        form.addWidget(
            self.quantity
        )

        form.addWidget(
            self.payment
        )

        form.addWidget(
            self.customer_name
        )

        form.addWidget(
            add
        )

        root.addLayout(form)

        self.table = QTableWidget()

        self.table.setColumnCount(6)

        self.table.setHorizontalHeaderLabels([
            "کد محصول",
            "نام محصول",
            "تعداد",
            "قیمت واحد",
            "مبلغ",
            "موجودی انبار"
        ])

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        root.addWidget(
            self.table
        )

        bottom = QHBoxLayout()

        self.total_label = QLabel(
            "جمع: 0 AMD"
        )

        self.total_label.setObjectName(
            "CardValue"
        )

        remove = QPushButton(
            "حذف از سبد"
        )

        checkout = QPushButton(
            "ثبت فروش"
        )

        checkout.setObjectName(
            "Primary"
        )

        bottom.addWidget(
            self.total_label
        )

        bottom.addStretch()

        bottom.addWidget(
            remove
        )

        bottom.addWidget(
            checkout
        )

        root.addLayout(
            bottom
        )

        add.clicked.connect(
            self.add_to_cart
        )

        remove.clicked.connect(
            self.remove_selected
        )

        checkout.clicked.connect(
            self.checkout
        )

        self.product_input.returnPressed.connect(
            self.add_to_cart
        )

    # --------------------------------------------------------

    def find_product(self, text):

        return self.db.fetchone("""
            SELECT *

            FROM products

            WHERE active = 1

            AND (
                code = ?
                OR name LIKE ?
            )

            LIMIT 1
        """, (
            text,
            f"%{text}%"
        ))

    # --------------------------------------------------------

    def add_to_cart(self):

        text = self.product_input.text().strip()

        if not text:

            QMessageBox.warning(
                self,
                "خطا",
                "کد یا نام محصول را وارد کنید."
            )

            return

        product = self.find_product(
            text
        )

        if not product:

            QMessageBox.warning(
                self,
                "خطا",
                "محصول پیدا نشد."
            )

            return

        quantity = self.quantity.value()

        existing = None

        for item in self.cart:

            if item["id"] == product["id"]:

                existing = item
                break

        current_quantity = (
            existing["quantity"]
            if existing
            else 0
        )

        if current_quantity + quantity > product["stock"]:

            QMessageBox.warning(
                self,
                "موجودی ناکافی",
                f"موجودی {product['name']} "
                f"فقط {number(product['stock'])} است."
            )

            return

        if existing:

            existing["quantity"] += quantity

        else:

            self.cart.append({
                "id": product["id"],
                "code": product["code"],
                "name": product["name"],
                "quantity": quantity,
                "sale_price": product["sale_price"],
                "purchase_price": product["purchase_price"],
                "stock": product["stock"]
            })

        self.product_input.clear()
        self.quantity.setValue(1)

        self.refresh_cart()

    # --------------------------------------------------------

    def refresh_cart(self):

        self.table.setRowCount(
            len(self.cart)
        )

        total = 0

        for r, item in enumerate(self.cart):

            line_total = (
                item["quantity"]
                * item["sale_price"]
            )

            total += line_total

            values = [
                item["code"],
                item["name"],
                number(item["quantity"]),
                money(item["sale_price"]),
                money(line_total),
                number(item["stock"])
            ]

            for c, value in enumerate(values):

                self.table.setItem(
                    r,
                    c,
                    QTableWidgetItem(
                        str(value)
                    )
                )

        self.total_label.setText(
            f"جمع: {money(total)}"
        )

    # --------------------------------------------------------

    def remove_selected(self):

        row = self.table.currentRow()

        if row < 0:
            return

        del self.cart[row]

        self.refresh_cart()

    # --------------------------------------------------------

    def checkout(self):

        if not self.cart:

            QMessageBox.warning(
                self,
                "سبد خالی",
                "سبد فروش خالی است."
            )

            return

        total = sum(
            item["quantity"]
            * item["sale_price"]
            for item in self.cart
        )

        payment = self.payment.currentText()

        answer = QMessageBox.question(
            self,
            "تأیید فروش",
            f"مبلغ فروش:\n"
            f"{money(total)}\n\n"
            f"فروش ثبت شود؟"
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        tx = transaction_id()

        customer_name = self.customer_name.text().strip()

        try:

            self.db.conn.execute(
                "BEGIN"
            )

            cursor = self.db.conn.cursor()

            cursor.execute("""
                INSERT INTO sales (
                    transaction_id,
                    customer_name,
                    total,
                    payment_method,
                    created_at
                )

                VALUES (?, ?, ?, ?, ?)
            """, (
                tx,
                customer_name,
                total,
                payment,
                now()
            ))

            sale_id = cursor.lastrowid

            for item in self.cart:

                current = cursor.execute("""
                    SELECT stock
                    FROM products
                    WHERE id = ?
                """, (
                    item["id"],
                )).fetchone()

                if not current:

                    raise ValueError(
                        "محصول پیدا نشد."
                    )

                stock = float(
                    current["stock"]
                )

                quantity = float(
                    item["quantity"]
                )

                if quantity > stock:

                    raise ValueError(
                        f"موجودی {item['name']} کافی نیست."
                    )

                line_total = (
                    quantity
                    * item["sale_price"]
                )

                cursor.execute("""
                    INSERT INTO sale_items (
                        sale_id,
                        product_id,
                        quantity,
                        unit_price,
                        purchase_price,
                        total
                    )

                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    sale_id,
                    item["id"],
                    quantity,
                    item["sale_price"],
                    item["purchase_price"],
                    line_total
                ))

                new_stock = stock - quantity

                cursor.execute("""
                    UPDATE products

                    SET stock = ?,
                        updated_at = ?

                    WHERE id = ?
                """, (
                    new_stock,
                    now(),
                    item["id"]
                ))

                cursor.execute("""
                    INSERT INTO inventory_transactions (
                        transaction_id,
                        product_id,
                        type,
                        quantity,
                        previous_stock,
                        new_stock,
                        reason,
                        created_at
                    )

                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tx,
                    item["id"],
                    "SALE",
                    -quantity,
                    stock,
                    new_stock,
                    "Sale",
                    now()
                ))

            if payment == "CASH":

                cursor.execute("""
                    INSERT INTO cash_transactions (
                        transaction_id,
                        type,
                        amount,
                        description,
                        reference_id,
                        created_at
                    )

                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    tx,
                    "SALE",
                    total,
                    "Sale",
                    tx,
                    now()
                ))

            self.db.conn.commit()

            items_to_notify = list(self.cart)

            QMessageBox.information(
                self,
                "فروش ثبت شد",
                f"فروش با موفقیت ثبت شد.\n\n"
                f"شناسه:\n{tx}\n\n"
                f"مبلغ:\n{money(total)}"
            )

            self.cart.clear()
            self.refresh_cart()

            if self.irc:
                names = "، ".join(
                    f"{item['name']}×{number(item['quantity'])}"
                    for item in items_to_notify
                ) or "سبد فروش"
                customer_part = f" | {customer_name}" if customer_name else ""
                msg = f"[فروش] {names} = {money(total)} | {payment}{customer_part} | {tx}"
                self.irc.send_message(msg)

        except Exception as error:

            self.db.conn.rollback()

            QMessageBox.critical(
                self,
                "خطا",
                user_friendly_error(error)
            )


# ============================================================
# PURCHASE PAGE
# ============================================================

class PurchasesPage(QWidget):

    def __init__(self, db):

        super().__init__()

        self.db = db
        self.irc = None

        root = QVBoxLayout(self)

        title = QLabel(
            "خرید"
        )

        title.setObjectName(
            "PageTitle"
        )

        root.addWidget(title)

        form = QGridLayout()

        self.product = QLineEdit()
        self.product.setPlaceholderText(
            "کد محصول"
        )

        self.quantity = QDoubleSpinBox()
        self.quantity.setMinimum(0.01)
        self.quantity.setMaximum(999999)
        self.quantity.setDecimals(2)

        self.unit_cost = QDoubleSpinBox()
        self.unit_cost.setMaximum(999999999)
        self.unit_cost.setDecimals(0)

        self.supplier = QLineEdit()
        self.supplier.setPlaceholderText(
            "تأمین‌کننده"
        )

        self.payment = QComboBox()
        self.payment.addItems([
            "CASH",
            "CARD",
            "OTHER"
        ])

        self.note = QLineEdit()

        form.addWidget(
            QLabel("محصول"),
            0, 0
        )

        form.addWidget(
            self.product,
            0, 1
        )

        form.addWidget(
            QLabel("تعداد"),
            0, 2
        )

        form.addWidget(
            self.quantity,
            0, 3
        )

        form.addWidget(
            QLabel("قیمت واحد"),
            1, 0
        )

        form.addWidget(
            self.unit_cost,
            1, 1
        )

        form.addWidget(
            QLabel("تأمین‌کننده"),
            1, 2
        )

        form.addWidget(
            self.supplier,
            1, 3
        )

        form.addWidget(
            QLabel("پرداخت"),
            2, 0
        )

        form.addWidget(
            self.payment,
            2, 1
        )

        form.addWidget(
            QLabel("توضیح"),
            2, 2
        )

        form.addWidget(
            self.note,
            2, 3
        )

        root.addLayout(form)

        save = QPushButton(
            "ثبت خرید"
        )

        save.setObjectName(
            "Primary"
        )

        save.clicked.connect(
            self.save_purchase
        )

        root.addWidget(save)

        self.table = QTableWidget()

        self.table.setColumnCount(6)

        self.table.setHorizontalHeaderLabels([
            "شناسه",
            "تأمین‌کننده",
            "مبلغ",
            "پرداخت",
            "توضیح",
            "تاریخ"
        ])

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        root.addWidget(
            self.table
        )

        self.refresh()

    def save_purchase(self):

        code = self.product.text().strip()

        if not code:

            QMessageBox.warning(
                self,
                "خطا",
                "کد محصول را وارد کنید."
            )

            return

        product = self.db.fetchone("""
            SELECT *
            FROM products
            WHERE code = ?
              AND active = 1
        """, (code,))

        if not product:

            QMessageBox.warning(
                self,
                "خطا",
                "محصول پیدا نشد."
            )

            return

        quantity = self.quantity.value()
        unit_cost = self.unit_cost.value()

        if quantity <= 0:

            QMessageBox.warning(
                self,
                "خطا",
                "تعداد نامعتبر است."
            )

            return

        if unit_cost < 0:

            QMessageBox.warning(
                self,
                "خطا",
                "قیمت نامعتبر است."
            )

            return

        total = quantity * unit_cost

        tx = transaction_id()

        try:

            self.db.conn.execute(
                "BEGIN"
            )

            cursor = self.db.conn.cursor()

            cursor.execute("""
                INSERT INTO purchases (
                    transaction_id,
                    supplier,
                    total,
                    payment_method,
                    note,
                    created_at
                )

                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                tx,
                self.supplier.text().strip(),
                total,
                self.payment.currentText(),
                self.note.text().strip(),
                now()
            ))

            purchase_id = cursor.lastrowid

            old_stock = float(
                product["stock"]
            )

            new_stock = (
                old_stock
                + quantity
            )

            cursor.execute("""
                INSERT INTO purchase_items (
                    purchase_id,
                    product_id,
                    quantity,
                    unit_cost,
                    total
                )

                VALUES (?, ?, ?, ?, ?)
            """, (
                purchase_id,
                product["id"],
                quantity,
                unit_cost,
                total
            ))

            cursor.execute("""
                UPDATE products

                SET stock = ?,
                    purchase_price = ?,
                    updated_at = ?

                WHERE id = ?
            """, (
                new_stock,
                unit_cost,
                now(),
                product["id"]
            ))

            cursor.execute("""
                INSERT INTO inventory_transactions (
                    transaction_id,
                    product_id,
                    type,
                    quantity,
                    previous_stock,
                    new_stock,
                    reason,
                    created_at
                )

                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tx,
                product["id"],
                "PURCHASE",
                quantity,
                old_stock,
                new_stock,
                "Purchase",
                now()
            ))

            if self.payment.currentText() == "CASH":

                cursor.execute("""
                    INSERT INTO cash_transactions (
                        transaction_id,
                        type,
                        amount,
                        description,
                        reference_id,
                        created_at
                    )

                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    tx,
                    "PURCHASE",
                    total,
                    "Purchase",
                    tx,
                    now()
                ))

            self.db.conn.commit()

            if self.irc:
                supplier = self.supplier.text().strip()
                pay = self.payment.currentText()
                msg = f"[خرید] {product['name']} × {number(quantity)} = {money(total)} | {supplier} | {pay} | {tx}"
                self.irc.send_message(msg)

            QMessageBox.information(
                self,
                "خرید ثبت شد",
                f"خرید ثبت شد.\n\n"
                f"{money(total)}\n"
                f"{tx}"
            )

            self.product.clear()
            self.quantity.setValue(1)
            self.unit_cost.setValue(0)
            self.supplier.clear()
            self.note.clear()

            self.refresh()

        except Exception as error:

            self.db.conn.rollback()

            QMessageBox.critical(
                self,
                "خطا",
                user_friendly_error(error)
            )

    def refresh(self):

        rows = self.db.fetchall("""
            SELECT
                transaction_id,
                supplier,
                total,
                payment_method,
                note,
                created_at

            FROM purchases

            ORDER BY id DESC

            LIMIT 100
        """)

        self.table.setRowCount(
            len(rows)
        )

        for r, row in enumerate(rows):

            values = [
                row["transaction_id"],
                row["supplier"],
                money(row["total"]),
                row["payment_method"],
                row["note"],
                row["created_at"]
            ]

            for c, value in enumerate(values):

                self.table.setItem(
                    r,
                    c,
                    QTableWidgetItem(
                        str(value)
                    )
                )


# ============================================================
# EXPENSES
# ============================================================

class ExpensesPage(QWidget):

    def __init__(self, db):

        super().__init__()

        self.db = db
        self.irc = None

        root = QVBoxLayout(self)

        title = QLabel(
            "هزینه‌ها"
        )

        title.setObjectName(
            "PageTitle"
        )

        root.addWidget(title)

        form = QGridLayout()

        self.category = QLineEdit()
        self.category.setPlaceholderText(
            "مثلاً برق، اجاره، اینترنت..."
        )

        self.amount = QDoubleSpinBox()
        self.amount.setMaximum(999999999)
        self.amount.setDecimals(0)

        self.description = QLineEdit()

        self.payment = QComboBox()

        self.payment.addItems([
            "CASH",
            "CARD",
            "OTHER"
        ])

        form.addWidget(
            QLabel("دسته"),
            0, 0
        )

        form.addWidget(
            self.category,
            0, 1
        )

        form.addWidget(
            QLabel("مبلغ"),
            0, 2
        )

        form.addWidget(
            self.amount,
            0, 3
        )

        form.addWidget(
            QLabel("پرداخت"),
            1, 0
        )

        form.addWidget(
            self.payment,
            1, 1
        )

        form.addWidget(
            QLabel("توضیح"),
            1, 2
        )

        form.addWidget(
            self.description,
            1, 3
        )

        root.addLayout(form)

        save = QPushButton(
            "ثبت هزینه"
        )

        save.setObjectName(
            "Primary"
        )

        save.clicked.connect(
            self.save_expense
        )

        root.addWidget(save)

        self.table = QTableWidget()

        self.table.setColumnCount(6)

        self.table.setHorizontalHeaderLabels([
            "شناسه",
            "دسته",
            "مبلغ",
            "پرداخت",
            "توضیح",
            "تاریخ"
        ])

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        root.addWidget(
            self.table
        )

        self.refresh()

    def save_expense(self):

        category = self.category.text().strip()
        amount = self.amount.value()

        if not category:

            QMessageBox.warning(
                self,
                "خطا",
                "دسته هزینه را وارد کنید."
            )

            return

        if amount <= 0:

            QMessageBox.warning(
                self,
                "خطا",
                "مبلغ باید بیشتر از صفر باشد."
            )

            return

        tx = transaction_id()

        try:

            self.db.conn.execute(
                "BEGIN"
            )

            cursor = self.db.conn.cursor()

            payment = self.payment.currentText()

            cursor.execute("""
                INSERT INTO expenses (
                    transaction_id,
                    category,
                    amount,
                    description,
                    payment_method,
                    created_at
                )

                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                tx,
                category,
                amount,
                self.description.text().strip(),
                payment,
                now()
            ))

            if payment == "CASH":

                cursor.execute("""
                    INSERT INTO cash_transactions (
                        transaction_id,
                        type,
                        amount,
                        description,
                        reference_id,
                        created_at
                    )

                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    tx,
                    "EXPENSE",
                    amount,
                    category,
                    tx,
                    now()
                ))

            self.db.conn.commit()

            if self.irc:
                cat = category
                pay = self.payment.currentText()
                msg = f"[هزینه] {cat}: {money(amount)} | {pay} | {tx}"
                self.irc.send_message(msg)

            QMessageBox.information(
                self,
                "ثبت شد",
                f"هزینه ثبت شد.\n{money(amount)}"
            )

            self.category.clear()
            self.amount.setValue(0)
            self.description.clear()

            self.refresh()

        except Exception as error:

            self.db.conn.rollback()

            QMessageBox.critical(
                self,
                "خطا",
                user_friendly_error(error)
            )

    def refresh(self):

        rows = self.db.fetchall("""
            SELECT
                transaction_id,
                category,
                amount,
                payment_method,
                description,
                created_at

            FROM expenses

            ORDER BY id DESC

            LIMIT 100
        """)

        self.table.setRowCount(
            len(rows)
        )

        for r, row in enumerate(rows):

            values = [
                row["transaction_id"],
                row["category"],
                money(row["amount"]),
                row["payment_method"],
                row["description"],
                row["created_at"]
            ]

            for c, value in enumerate(values):

                self.table.setItem(
                    r,
                    c,
                    QTableWidgetItem(
                        str(value)
                    )
                )


# ============================================================
# INVENTORY
# ============================================================

class InventoryPage(QWidget):

    def __init__(self, db):

        super().__init__()

        self.db = db

        root = QVBoxLayout(self)

        title = QLabel(
            "انبار"
        )

        title.setObjectName(
            "PageTitle"
        )

        root.addWidget(title)

        self.table = QTableWidget()

        self.table.setColumnCount(8)

        self.table.setHorizontalHeaderLabels([
            "کد محصول",
            "نام محصول",
            "واحد",
            "موجودی انبار",
            "حداقل موجودی",
            "قیمت خرید",
            "قیمت فروش",
            "وضعیت"
        ])

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        root.addWidget(
            self.table
        )

        refresh = QPushButton(
            "به‌روزرسانی"
        )

        refresh.clicked.connect(
            self.refresh
        )

        root.addWidget(refresh)

        self.refresh()

    def refresh(self):

        rows = self.db.fetchall("""
            SELECT *

            FROM products

            WHERE active = 1

            ORDER BY name
        """)

        self.table.setRowCount(
            len(rows)
        )

        for r, row in enumerate(rows):

            stock = float(
                row["stock"]
            )

            minimum = float(
                row["min_stock"]
            )

            if stock <= 0:

                status = "تمام شده"

            elif stock <= minimum:

                status = "کم"

            else:

                status = "مناسب"

            values = [
                row["code"],
                row["name"],
                row["unit"],
                number(stock),
                number(minimum),
                money(row["purchase_price"]),
                money(row["sale_price"]),
                status
            ]

            for c, value in enumerate(values):

                self.table.setItem(
                    r,
                    c,
                    QTableWidgetItem(
                        str(value)
                    )
                )


# ============================================================
# CASH
# ============================================================

class CashPage(QWidget):

    def __init__(self, db):

        super().__init__()

        self.db = db
        self.irc = None

        root = QVBoxLayout(self)

        title = QLabel(
            "صندوق"
        )

        title.setObjectName(
            "PageTitle"
        )

        root.addWidget(title)

        self.balance = QLabel(
            money(0)
        )

        self.balance.setObjectName(
            "CardValue"
        )

        root.addWidget(
            self.balance
        )

        buttons = QHBoxLayout()

        cash_in = QPushButton(
            "＋ ورود وجه"
        )

        cash_out = QPushButton(
            "－ خروج وجه"
        )

        cash_in.setObjectName(
            "Primary"
        )

        buttons.addWidget(
            cash_in
        )

        buttons.addWidget(
            cash_out
        )

        root.addLayout(
            buttons
        )

        self.table = QTableWidget()

        self.table.setColumnCount(5)

        self.table.setHorizontalHeaderLabels([
            "شناسه",
            "نوع",
            "مبلغ",
            "توضیح",
            "تاریخ"
        ])

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        root.addWidget(
            self.table
        )

        cash_in.clicked.connect(
            lambda: self.cash_adjustment(
                "CASH_IN"
            )
        )

        cash_out.clicked.connect(
            lambda: self.cash_adjustment(
                "CASH_OUT"
            )
        )

        self.refresh()

    def cash_adjustment(self, kind):

        amount, ok = QInputDialog.getDouble(
            self,
            "مبلغ",
            "مبلغ:",
            0,
            0,
            999999999,
            0
        )

        if not ok or amount <= 0:
            return

        description, ok = QInputDialog.getText(
            self,
            "توضیح",
            "توضیح:"
        )

        if not ok:
            return

        tx = transaction_id()

        try:

            self.db.execute("""
                INSERT INTO cash_transactions (
                    transaction_id,
                    type,
                    amount,
                    description,
                    created_at
                )

                VALUES (?, ?, ?, ?, ?)
            """, (
                tx,
                kind,
                amount,
                description,
                now()
            ))

            if self.irc:
                label = "ورود پول" if kind == "CASH_IN" else "خروج پول"
                msg = f"[{label}] {money(amount)}"
                if description:
                    msg += f" | {description}"
                msg += f" | {tx}"
                self.irc.send_message(msg)

            self.refresh()

        except Exception as error:

            QMessageBox.critical(
                self,
                "خطا",
                user_friendly_error(error)
            )

    def refresh(self):

        self.balance.setText(
            money(
                self.db.cash_balance()
            )
        )

        rows = self.db.fetchall("""
            SELECT
                transaction_id,
                type,
                amount,
                description,
                created_at

            FROM cash_transactions

            ORDER BY id DESC

            LIMIT 200
        """)

        self.table.setRowCount(
            len(rows)
        )

        for r, row in enumerate(rows):

            values = [
                row["transaction_id"],
                row["type"],
                money(row["amount"]),
                row["description"],
                row["created_at"]
            ]

            for c, value in enumerate(values):

                self.table.setItem(
                    r,
                    c,
                    QTableWidgetItem(
                        str(value)
                    )
                )


# ============================================================
# REPORTS
# ============================================================

class ReportsPage(QWidget):

    def __init__(self, db):

        super().__init__()

        self.db = db

        root = QVBoxLayout(self)

        title = QLabel(
            "گزارش‌ها"
        )

        title.setObjectName(
            "PageTitle"
        )

        root.addWidget(title)

        dates = QHBoxLayout()

        self.from_date = QDateEdit()

        self.to_date = QDateEdit()

        self.from_date.setCalendarPopup(True)
        self.to_date.setCalendarPopup(True)

        self.from_date.setDate(
            self.from_date.minimumDate().currentDate()
        )

        self.to_date.setDate(
            self.to_date.minimumDate().currentDate()
        )

        dates.addWidget(
            QLabel("از:")
        )

        dates.addWidget(
            self.from_date
        )

        dates.addWidget(
            QLabel("تا:")
        )

        dates.addWidget(
            self.to_date
        )

        run = QPushButton(
            "نمایش گزارش"
        )

        run.setObjectName(
            "Primary"
        )

        dates.addWidget(run)

        root.addLayout(dates)

        self.result = QTextEdit()

        self.result.setReadOnly(True)

        root.addWidget(
            self.result
        )

        run.clicked.connect(
            self.generate
        )

        self.generate()

    def generate(self):

        start = self.from_date.date().toString(
            "yyyy-MM-dd"
        ) + " 00:00:00"

        end = self.to_date.date().toString(
            "yyyy-MM-dd"
        ) + " 23:59:59"

        sales = self.db.fetchone("""
            SELECT COALESCE(SUM(total), 0) AS value
            FROM sales
            WHERE created_at BETWEEN ? AND ?
        """, (
            start,
            end
        ))["value"]

        purchases = self.db.fetchone("""
            SELECT COALESCE(SUM(total), 0) AS value
            FROM purchases
            WHERE created_at BETWEEN ? AND ?
        """, (
            start,
            end
        ))["value"]

        expenses = self.db.fetchone("""
            SELECT COALESCE(SUM(amount), 0) AS value
            FROM expenses
            WHERE created_at BETWEEN ? AND ?
        """, (
            start,
            end
        ))["value"]

        refund = self.db.fetchone("""
            SELECT COALESCE(
                SUM(amount), 0
            ) AS value

            FROM cash_transactions

            WHERE type = 'REFUND'

            AND created_at BETWEEN ? AND ?
        """, (
            start,
            end
        ))["value"]

        approximate_profit = (
            float(sales)
            - float(purchases)
            - float(expenses)
        )

        top_products = self.db.fetchall("""
            SELECT
                p.name,
                SUM(si.quantity) AS quantity

            FROM sale_items si

            JOIN sales s
                ON s.id = si.sale_id

            JOIN products p
                ON p.id = si.product_id

            WHERE s.created_at BETWEEN ? AND ?

            GROUP BY p.id

            ORDER BY quantity DESC

            LIMIT 10
        """, (
            start,
            end
        ))

        text = []

        text.append(
            f"گزارش از {start} تا {end}"
        )

        text.append("")
        text.append(
            f"فروش: {money(sales)}"
        )

        text.append(
            f"خرید: {money(purchases)}"
        )

        text.append(
            f"هزینه: {money(expenses)}"
        )

        text.append(
            f"Refund: {money(refund)}"
        )

        text.append(
            f"سود تقریبی: "
            f"{money(approximate_profit)}"
        )

        text.append("")
        text.append(
            "پرفروش‌ترین محصولات:"
        )

        for item in top_products:

            text.append(
                f"• {item['name']} — "
                f"{number(item['quantity'])}"
            )

        self.result.setPlainText(
            "\n".join(text)
        )


# ============================================================
# DATABASE SEARCH / READ
# ============================================================

class DatabaseSearchPage(QWidget):

    def __init__(self, db):

        super().__init__()

        self.db = db

        root = QVBoxLayout(self)

        title = QLabel(
            "جستجوی دیتابیس"
        )

        title.setObjectName(
            "PageTitle"
        )

        root.addWidget(title)

        # Search form
        search_group = QGroupBox("جستجو")
        search_layout = QVBoxLayout(search_group)

        # Search type selector
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("نوع جستجو:"))
        
        self.search_type = QComboBox()
        self.search_type.addItems([
            "نام خریدار (مشتری)",
            "نام/کد محصول",
            "شناسه تراکنش",
            "بازه تاریخ"
        ])
        self.search_type.currentTextChanged.connect(self.on_search_type_changed)
        type_layout.addWidget(self.search_type)
        
        type_layout.addStretch()
        search_layout.addLayout(type_layout)

        # Search input (changes based on type)
        self.search_input_stack = QStackedWidget()

        # Page 0: Customer name search
        self.customer_input = QLineEdit()
        self.customer_input.setPlaceholderText("نام مشتری را وارد کنید...")
        self.customer_input.returnPressed.connect(self.search)
        self.search_input_stack.addWidget(self.customer_input)

        # Page 1: Product search
        self.product_input = QLineEdit()
        self.product_input.setPlaceholderText("نام یا کد محصول را وارد کنید...")
        self.product_input.returnPressed.connect(self.search)
        self.search_input_stack.addWidget(self.product_input)

        # Page 2: Transaction ID search
        self.tx_input = QLineEdit()
        self.tx_input.setPlaceholderText("شناسه تراکنش را وارد کنید...")
        self.tx_input.returnPressed.connect(self.search)
        self.search_input_stack.addWidget(self.tx_input)

        # Page 3: Date range search
        date_widget = QWidget()
        date_layout = QHBoxLayout(date_widget)
        date_layout.setContentsMargins(0, 0, 0, 0)
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(self.from_date.minimumDate().currentDate().addMonths(-1))
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(self.to_date.minimumDate().currentDate())
        date_layout.addWidget(QLabel("از:"))
        date_layout.addWidget(self.from_date)
        date_layout.addWidget(QLabel("تا:"))
        date_layout.addWidget(self.to_date)
        date_layout.addStretch()
        self.search_input_stack.addWidget(date_widget)

        search_layout.addWidget(self.search_input_stack)

        # Search button
        search_btn = QPushButton("جستجو")
        search_btn.setObjectName("Primary")
        search_btn.clicked.connect(self.search)
        search_layout.addWidget(search_btn)

        root.addWidget(search_group)

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "شناسه تراکنش",
            "نوع",
            "مشتری",
            "محصول",
            "تعداد",
            "مبلغ",
            "تاریخ"
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        root.addWidget(self.table)

        # Summary label
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("font-weight: bold; padding: 10px;")
        root.addWidget(self.summary_label)

    def on_search_type_changed(self, text):
        """Switch input widget based on search type."""
        type_map = {
            "نام خریدار (مشتری)": 0,
            "نام/کد محصول": 1,
            "شناسه تراکنش": 2,
            "بازه تاریخ": 3,
        }
        self.search_input_stack.setCurrentIndex(type_map.get(text, 0))

    def search(self):
        """Execute search based on selected type."""
        search_type = self.search_type.currentText()
        self.table.setRowCount(0)
        self.summary_label.setText("")

        try:
            if search_type == "نام خریدار (مشتری)":
                self.search_by_customer()
            elif search_type == "نام/کد محصول":
                self.search_by_product()
            elif search_type == "شناسه تراکنش":
                self.search_by_transaction()
            elif search_type == "بازه تاریخ":
                self.search_by_date_range()
        except Exception as e:
            QMessageBox.critical(self, "خطا", user_friendly_error(e))

    def search_by_customer(self):
        """Search sales by customer name."""
        customer = self.customer_input.text().strip()
        if not customer:
            QMessageBox.warning(self, "خطا", "نام مشتری را وارد کنید.")
            return

        rows = self.db.fetchall("""
            SELECT 
                s.transaction_id,
                'فروش' as type,
                s.customer_name,
                p.name as product_name,
                si.quantity,
                si.total,
                s.created_at
            FROM sales s
            JOIN sale_items si ON s.id = si.sale_id
            JOIN products p ON si.product_id = p.id
            WHERE s.customer_name LIKE ?
            ORDER BY s.created_at DESC
        """, (f"%{customer}%",))

        self.populate_table(rows, f"خریدهای مشتری: {customer}")

    def search_by_product(self):
        """Search sales by product name or code."""
        query = self.product_input.text().strip()
        if not query:
            QMessageBox.warning(self, "خطا", "نام یا کد محصول را وارد کنید.")
            return

        rows = self.db.fetchall("""
            SELECT 
                s.transaction_id,
                'فروش' as type,
                s.customer_name,
                p.name as product_name,
                si.quantity,
                si.total,
                s.created_at
            FROM sales s
            JOIN sale_items si ON s.id = si.sale_id
            JOIN products p ON si.product_id = p.id
            WHERE p.name LIKE ? OR p.code LIKE ?
            ORDER BY s.created_at DESC
        """, (f"%{query}%", f"%{query}%"))

        self.populate_table(rows, f"فروش‌های محصول: {query}")

    def search_by_transaction(self):
        """Search by transaction ID."""
        tx_id = self.tx_input.text().strip()
        if not tx_id:
            QMessageBox.warning(self, "خطا", "شناسه تراکنش را وارد کنید.")
            return

        rows = self.db.fetchall("""
            SELECT 
                s.transaction_id,
                'فروش' as type,
                s.customer_name,
                p.name as product_name,
                si.quantity,
                si.total,
                s.created_at
            FROM sales s
            JOIN sale_items si ON s.id = si.sale_id
            JOIN products p ON si.product_id = p.id
            WHERE s.transaction_id = ?
            ORDER BY s.created_at DESC
        """, (tx_id,))

        self.populate_table(rows, f"تراکنش: {tx_id}")

    def search_by_date_range(self):
        """Search by date range."""
        start = self.from_date.date().toString("yyyy-MM-dd") + " 00:00:00"
        end = self.to_date.date().toString("yyyy-MM-dd") + " 23:59:59"

        rows = self.db.fetchall("""
            SELECT 
                s.transaction_id,
                'فروش' as type,
                s.customer_name,
                p.name as product_name,
                si.quantity,
                si.total,
                s.created_at
            FROM sales s
            JOIN sale_items si ON s.id = si.sale_id
            JOIN products p ON si.product_id = p.id
            WHERE s.created_at BETWEEN ? AND ?
            ORDER BY s.created_at DESC
        """, (start, end))

        self.populate_table(rows, f"فروش از {start[:10]} تا {end[:10]}")

    def populate_table(self, rows, summary):
        """Populate results table and show summary."""
        self.table.setRowCount(len(rows))

        total_amount = 0
        total_quantity = 0
        customers = set()
        products = set()

        for r, row in enumerate(rows):
            values = [
                row["transaction_id"],
                row["type"],
                row["customer_name"] or "—",
                row["product_name"],
                number(row["quantity"]),
                money(row["total"]),
                row["created_at"]
            ]

            for c, value in enumerate(values):
                self.table.setItem(
                    r,
                    c,
                    QTableWidgetItem(str(value))
                )

            total_amount += float(row["total"])
            total_quantity += float(row["quantity"])
            if row["customer_name"]:
                customers.add(row["customer_name"])
            products.add(row["product_name"])

        self.summary_label.setText(
            f"مجموع: {money(total_amount)} | تعداد کل: {number(total_quantity)} | "
            f"مشتریان منحصر به فرد: {len(customers)} | محصولات: {len(products)}"
        )


# ============================================================
# TRANSACTIONS
# ============================================================

class TransactionsPage(QWidget):

    def __init__(self, db):

        super().__init__()

        self.db = db

        root = QVBoxLayout(self)

        title = QLabel(
            "تراکنش‌ها"
        )

        title.setObjectName(
            "PageTitle"
        )

        root.addWidget(title)

        self.table = QTableWidget()

        self.table.setColumnCount(5)

        self.table.setHorizontalHeaderLabels([
            "شناسه",
            "نوع",
            "مبلغ/تعداد",
            "توضیح",
            "تاریخ"
        ])

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        root.addWidget(
            self.table
        )

        refresh = QPushButton(
            "به‌روزرسانی"
        )

        refresh.clicked.connect(
            self.refresh
        )

        root.addWidget(refresh)

        self.refresh()

    def refresh(self):

        rows = []

        sales = self.db.fetchall("""
            SELECT
                transaction_id,
                total,
                created_at

            FROM sales

            ORDER BY id DESC

            LIMIT 100
        """)

        for row in sales:

            rows.append((
                row["transaction_id"],
                "SALE",
                row["total"],
                "",
                row["created_at"]
            ))

        purchases = self.db.fetchall("""
            SELECT
                transaction_id,
                total,
                created_at

            FROM purchases

            ORDER BY id DESC

            LIMIT 100
        """)

        for row in purchases:

            rows.append((
                row["transaction_id"],
                "PURCHASE",
                row["total"],
                "",
                row["created_at"]
            ))

        expenses = self.db.fetchall("""
            SELECT
                transaction_id,
                amount,
                description,
                created_at

            FROM expenses

            ORDER BY id DESC

            LIMIT 100
        """)

        for row in expenses:

            rows.append((
                row["transaction_id"],
                "EXPENSE",
                row["amount"],
                row["description"],
                row["created_at"]
            ))

        rows.sort(
            key=lambda x: x[4],
            reverse=True
        )

        self.table.setRowCount(
            len(rows)
        )

        for r, row in enumerate(rows):

            values = [
                row[0],
                row[1],
                money(row[2]),
                row[3],
                row[4]
            ]

            for c, value in enumerate(values):

                self.table.setItem(
                    r,
                    c,
                    QTableWidgetItem(
                        str(value)
                    )
                )


# ============================================================
# BACKUP
# ============================================================

class BackupPage(QWidget):

    def __init__(self, db):

        super().__init__()

        self.db = db

        root = QVBoxLayout(self)

        title = QLabel(
            "پشتیبان‌گیری"
        )

        title.setObjectName(
            "PageTitle"
        )

        root.addWidget(title)

        info = QLabel(
            f"دیتابیس فعلی:\n{DB_PATH}"
        )

        info.setWordWrap(True)

        root.addWidget(info)

        backup = QPushButton(
            "ایجاد Backup"
        )

        backup.setObjectName(
            "Primary"
        )

        backup.clicked.connect(
            self.create_backup
        )

        root.addWidget(
            backup
        )

        self.list = QTableWidget()

        self.list.setColumnCount(2)

        self.list.setHorizontalHeaderLabels([
            "فایل",
            "زمان"
        ])

        self.list.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        root.addWidget(
            self.list
        )

        self.refresh()

    def create_backup(self):

        BACKUP_DIR.mkdir(
            exist_ok=True
        )

        filename = (
            "patogh-"
            + datetime.now().strftime(
                "%Y%m%d-%H%M%S"
            )
            + ".db"
        )

        target = (
            BACKUP_DIR
            / filename
        )

        try:

            self.db.conn.commit()

            shutil.copy2(
                DB_PATH,
                target
            )

            QMessageBox.information(
                self,
                "Backup",
                f"Backup ساخته شد:\n{target}"
            )

            self.refresh()

        except Exception as error:

            QMessageBox.critical(
                self,
                "خطا",
                user_friendly_error(error)
            )

    def refresh(self):

        BACKUP_DIR.mkdir(
            exist_ok=True
        )

        files = sorted(
            BACKUP_DIR.glob("*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        self.list.setRowCount(
            len(files)
        )

        for r, path in enumerate(files):

            timestamp = datetime.fromtimestamp(
                path.stat().st_mtime
            ).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            self.list.setItem(
                r,
                0,
                QTableWidgetItem(
                    path.name
                )
            )

            self.list.setItem(
                r,
                1,
                QTableWidgetItem(
                    timestamp
                )
            )


# ============================================================
# HELP
# ============================================================

class HelpPage(QWidget):

    def __init__(self):

        super().__init__()

        root = QVBoxLayout(self)

        title = QLabel(
            "راهنمای PATOGH"
        )

        title.setObjectName(
            "PageTitle"
        )

        root.addWidget(title)

        help_text = QTextEdit()

        help_text.setReadOnly(True)

        help_text.setHtml("""
        <h2>PATOGH - راهنمای کامل</h2>

        <p style="font-size: 16px; color: #3B2419;">
        خوش آمدید! PATOGH یک نرم‌افزار ساده و قدرتمند برای مدیریت کافه و پاتوق است.
        این راهنما برای کسانی نوشته شده که تجربه کمپیوتری یا حسابداری کمی دارند.
        هر بخش به زبان ساده توضیح داده شده است.
        </p>

        <hr>

        <h3>۱. این برنامه چه کاری انجام می‌دهد؟</h3>
        <p>
        PATOGH به شما کمک می‌کند تا:
        </p>
        <ul>
            <li>محصولات کافه را ثبت و مدیریت کنید</li>
            <li>خریدهای جدید را ثبت کنید (موجودی انبار افزایش می‌یابد)</li>
            <li>فروش را سریع و آسان انجام دهید</li>
            <li>هزینه‌های کافه را پیگیری کنید</li>
            <li>صندوق (پول نقد) را کنترل کنید</li>
            <li>موجودی انبار را ببینید و کالاهای کم‌موجود را شناسایی کنید</li>
            <li>گزارش‌های روزانه، هفتگی و ماهانه بگیرید</li>
            <li>اطلاعات را به صورت خودکار به کانال IRC بفرستید (برای مالک کافه)</li>
        </ul>

        <hr>

        <h3>۲. مفاهیم اصلی - به زبان ساده</h3>

        <h4>محصول (Product)</h4>
        <p>
        هر کالایی که در کافه می‌فروشید: قهوه، چای، نوشابه، غذا، و غیره.
        هر محصول مشخصات زیر را دارد:
        </p>
        <ul>
            <li><b>کد محصول:</b> یک کد منحصر به فرد (مثل: COF-001, DRK-002) که برای پیدا کردن سریع استفاده می‌شود.</li>
            <li><b>نام:</b> نام نمایشی محصول (مثل: «قهوه ترک», «نوشابه کولا»)</li>
            <li><b>دسته‌بندی:</b> گروه‌بندی برای مرتب‌سازی (مثل: «نوشیدنی داغ», «نوشیدنی سرد», «غذا»)</li>
            <li><b>واحد شمارش:</b> واحد فروش (مثل: «فنجان», «بطری», «ظرف», «کیلوگرم»)</li>
            <li><b>قیمت خرید کافه:</b> مبلغی که کافه برای تهیه این محصول می‌پردازد (قیمت پایه/بها). این قیمت به مشتری نمایش داده نمی‌شود.</li>
            <li><b>قیمت فروش به مشتری:</b> مبلغی که از مشتری گرفته می‌شود. این قیمت باید از قیمت خرید بیشتر باشد تا سود به دست آید.</li>
            <li><b>موجودی انبار:</b> تعداد فعلی این محصول در انبار. وقتی فروش می‌کنید کم می‌شود، وقتی خرید می‌کنید زیاد می‌شود.</li>
            <li><b>حداقل موجودی (هشدار):</b> اگر موجودی از این عدد کمتر شود، در داشبورد و انبار قرمز/هشدار نشان داده می‌شود تا بدانید باید خرید کنید.</li>
        </ul>

        <h4>خرید (Purchase)</h4>
        <p>
        وقتی کافه کالایی می‌خرد (از تأمین‌کننده)، این یک «خرید» است.
        اثر خرید: موجودی انبار آن محصول <b>افزایش</b> می‌یابد و صندوق (اگر نقدی باشد) <b>کاهش</b> می‌یابد.
        </p>
        <p>
        اطلاعات ثبت شده: کد محصول، تعداد، قیمت واحد خرید، تأمین‌کننده، روش پرداخت، توضیح.
        </p>

        <h4>فروش (Sale)</h4>
        <p>
        وقتی مشتری کالایی می‌خرد، این یک «فروش» است.
        اثر فروش: موجودی انبار آن محصول <b>کاهش</b> می‌یابد و صندوق (اگر نقدی باشد) <b>افزایش</b> می‌یابد.
        </p>
        <p>
        فرآیند: کد/نام محصول را تایپ کنید → تعداد را وارد کنید → به سبد اضافه کنید → در نهایت «ثبت فروش» را بزنید.
        </p>

        <h4>هزینه (Expense)</h4>
        <p>
        هزینه‌های جاری کافه مثل: اجاره، برق، آب، اینترنت، حقوق کارکنان، تعمیرات.
        اثر هزینه: صندوق (اگر نقدی باشد) <b>کاهش</b> می‌یابد. موجودی انبار تغییر نمی‌کند.
        </p>

        <h4>صندوق (Cash)</h4>
        <p>
        نشان‌دهنده موجودی پول نقد کافه است.
        <ul>
            <li>فروش نقدی → صندوق بالا می‌رود</li>
            <li>خرید نقدی → صندوق پایین می‌آید</li>
            <li>هزینه نقدی → صندوق پایین می‌آید</li>
            <li>می‌توانید دستی «ورود وجه» و «خروج وجه» ثبت کنید</li>
        </ul>
        </p>

        <h4>انبار / موجودی (Inventory)</h4>
        <p>
        لیست تمام محصولات با موجودی فعلی آن‌ها.
        وضعیت‌ها:
        <ul>
            <li><b>مناسب:</b> موجودی از حداقل بیشتر است</li>
            <li><b>کم:</b> موجودی نزدیک به حداقل است (زمان خرید رسیده)</li>
            <li><b>تمام شده:</b> موجودی صفر یا کمتر از صفر است</li>
        </ul>
        </p>

        <hr>

        <h3>۳. شروع کار - قدم به قدم</h3>
        <ol>
            <li><b>محصولات را وارد کنید:</b> به بخش «محصولات» بروید، «افزودن محصول» را بزنید، اطلاعات را پر کنید.</li>
            <li><b>موجودی اولیه را تعیین کنید:</b> برای هر محصول، تعداد فعلی در انبار را در فیلد «موجودی انبار» بنویسید.</li>
            <li><b>حداقل موجودی را ست کنید:</b> عددی که اگر موجودی کمتر شود، هشدار بدهد (مثلاً ۵ عدد).</li>
            <li><b>قیمت‌ها را تعیین کنید:</b> «قیمت خرید کافه» و «قیمت فروش به مشتری» را وارد کنید.</li>
            <li><b>خرید اول را ثبت کنید:</b> اگر کالا دارید، از بخش «خرید» موجودی را افزایش دهید.</li>
            <li><b>فروش را آغاز کنید:</b> به بخش «فروش» بروید، کد محصول را تایپ کنید، تعداد بزنید، «ثبت فروش».</li>
            <li><b>هر روز صندوق را چک کنید:</b> بخش «صندوق» موجودی نقدی را نشان می‌دهد.</li>
            <li><b>هفتگی یک بار گزارش بگیرید:</b> بخش «گزارش‌ها» سود و ضرر را نشان می‌دهد.</li>
            <li><b>هر روز بکاپ بگیرید:</b> بخش «پشتیبان‌گیری» فایل ذخیره می‌کند.</li>
        </ol>

        <hr>

        <h3>۴. بخش‌های برنامه</h3>

        <h4>داشبورد (صفحه اصلی)</h4>
        <p>
        خلاصه وضعیت امروز: جمع فروش، جمع خرید، جمع هزینه، موجودی صندوق، و لیست کالاهای کم‌موجود.
        </p>

        <h4>فروش</h4>
        <p>
        سریع‌ترین بخش. کد یا نام محصول را تایپ کنید، Enter بزنید، تعداد را تایید کنید، به سبد اضافه می‌شود.
        در نهایت «ثبت فروش» را بزنید. روش پرداخت (نقد/کارت/سایر) را انتخاب کنید.
        </p>

        <h4>محصولات</h4>
        <p>
        لیست تمام محصولات. می‌توانید جستجو کنید، ویرایش کنید، یا جدید اضافه کنید.
        ستون‌ها: کد، نام، دسته، واحد، قیمت خرید، قیمت فروش، موجودی، حداقل.
        </p>

        <h4>خرید</h4>
        <p>
        کد محصول را وارد کنید، تعداد و قیمت خرید را بنویسید، تأمین‌کننده و روش پرداخت را انتخاب کنید، «ثبت خرید».
        موجودی انبار بلافاصله افزایش می‌یابد.
        </p>

        <h4>انبار</h4>
        <p>
        نمای کامل موجودی همه محصولات. وضعیت (مناسب/کم/تمام شده) رنگی نمایش داده می‌شود.
        برای دیدن کالاهای کم، به داشبورد یا همین صفحه مراجعه کنید.
        </p>

        <h4>صندوق</h4>
        <p>
        موجودی نقد فعلی. دکمه‌های «ورود وجه» و «خروج وجه» برای ثبت دستی پول.
        جدول تراکنش‌های نقدی در پایین صفحه.
        </p>

        <h4>هزینه‌ها</h4>
        <p>
        دسته هزینه (مثل: اجاره، برق)، مبلغ، توضیح، روش پرداخت. «ثبت هزینه».
        </p>

        <h4>گزارش‌ها</h4>
        <p>
        بازه تاریخ را انتخاب کنید، «نمایش گزارش» بزنید.
        شامل: جمع فروش، جمع خرید، جمع هزینه، سود تقریبی، ۱۰ پرفروش‌ترین کالا.
        <b>سود تقریبی = فروش - خرید - هزینه</b>
        </p>

        <h4>تراکنش‌ها</h4>
        <p>
        تاریخچه کامل همه فروش‌ها، خریدها، و هزینه‌ها در یک لیست ادغام شده.
        </p>

        <h4>پشتیبان‌گیری (Backup)</h4>
        <p>
        <b>بسیار مهم:</b> هر روز (یا بعد از کارهای مهم) «ایجاد Backup» بزنید.
        فایل‌های بکاپ در پوشه <b>backups</b> در کنار دیتابیس ذخیره می‌شوند.
        اگر سیستم خراب شد، فایل بکاپ را کپی کنید و به جای patogh.db قرار دهید.
        </p>

        <hr>

        <h3>۵. IRC - پیام‌رسانی برای مالک</h3>
        <p>
        برنامه به سرور IRC (Libera.Chat) وصل می‌شود و هر تراکنش (فروش، خرید، هزینه، ورود/خروج وجه) را به کانال <b>#myCh</b> می‌فرستد.
        مالک کافه با باز کردن کانال در برنامه‌های IRC (مثل HexChat، mIRC، WeeChat) می‌تواند لحظه‌به‌لحظه تراکنش‌ها را ببیند.
        <br>
        تنظیمات در دیتابیس ذخیره می‌شوند و با اول بار اجرا ستاپ می‌شوند.
        </p>

        <hr>

        <h3>۶. رفع اشکال رایج</h3>
        <ul>
            <li><b>«موجودی کافی نیست» در فروش:</b> یعنی تعداد در انبار کمتر از درخواست است. اول خرید ثبت کنید یا موجودی را چک کنید.</li>
            <li><b>«کد محصول قبلاً استفاده شده»:</b> کد تکراری است. کد دیگر بزنید.</li>
            <li><b>اتصال IRC برقرار نمی‌شود:</b> اینترنت را چک کنید، فایروال/آنتی‌ویروس را موقت غیرفعال کنید. برنامه در شروع اجرا تلاش می‌کند وصل شود.</li>
            <li><b>گزارش خالی است:</b> بازه تاریخ را چک کنید (از/تا).</li>
            <li><b>موجودی منفی شد:</b> فروش بیش از موجودی ثبت شده. خرید آن کالا را ثبت کنید.</li>
            <li><b>برنامه باز نمی‌شود:</b> فایل دیتابیس (patogh.db) را چک کنید، شاید قفل شده باشد. برنامه را مجدد اجرا کنید.</li>
        </ul>

        <hr>

        <h3>۷. نکات مهم و نکته‌های طلایی</h3>
        <ul>
            <li><b>هر روز بکاپ بگیرید.</b> این مهم‌ترین کار است. فایل .db در پوشه backups کپی می‌شود.</li>
            <li><b>قیمت خرید ≠ قیمت فروش.</b> قیمت خرید = هزینه کافه. قیمت فروش = درآمد از مشتری. فروش باید گران‌تر باشد.</li>
            <li><b>حداقل موجودی ست کنید.</b> وگرنه ناگهان کالا تمام می‌شود و متوجه نمی‌شوید.</li>
            <li><b>خرید قبل از فروش.</b> اگر کالایی ندارید و بفروشید، موجودی منفی می‌شود و محاسبه سود غلط می‌شود.</li>
            <li><b>پرداخت «سایر» برای چک/حواله/آنلاین.</b> در صورت لزوم در توضیح بنویسید.</li>
            <li><b>IRC فقط اطلاع‌رسانی است.</b> اگر وصل نشد، برنامه کار می‌کند، فقط پیام‌ها ارسال نمی‌شوند.</li>
            <li><b>فایل دیتابیس = تمام اطلاعات.</b> آن را مثل طلا نگه دارید.</li>
        </ul>

        <hr>

        <h3>۸. سوالات متداول</h3>
        <p><b>س: چطور یک محصول جدید بسازم؟</b><br>
        ج: به بخش «محصولات» → «افزودن محصول» → تمام فیلدها را پر کنید → ذخیره.</p>
        <p><b>س: چطور موجودی را افزایش دهم؟</b><br>
        ج: به بخش «خرید» → کد محصول، تعداد، قیمت خرید → ثبت خرید.</p>
        <p><b>س: چطور بفهمم سود کردم یا ضرر؟</b><br>
        ج: بخش «گزارش‌ها» → بازه تاریخ → «نمایش گزارش» → «سود تقریبی» را ببینید. سبز = سود، قرمز = ضرر.</p>
        <p><b>س: مشتری برمی‌گرداند (استثنا/برگشت).</b><br>
        ج: فعلاً از بخش «صندوق» → «خروج وجه» با توضیح «برگشت کالا» مبلغ را کسر کنید و در انبار دستی موجودی را افزایش دهید. (نسخه‌های آینده برگشت خودکار خواهد داشت).</p>
        <p><b>س: برنامه کجا اطلاعات را ذخیره می‌کند؟</b><br>
        ج: در فایل <b>patogh.db</b> در پوشه داده‌های برنامه (روی ویندوز در AppData، روی لینوکس در ~/.local/share/PATOGH).</p>

        <hr>

        <h3>۹. توسعه‌دهنده</h3>
        <p style="text-align: center; color: #6F4E37; font-weight: bold;">
        PATOGH v1.0.0 — برای کافه‌های ساده و شیک
        <br>
        در صورت سوال، راهنما را دوباره بخوانید یا از بخش‌های مختلف برنامه استفاده کنید.
        <br><br>
        <b>توسعه‌دهنده:</b> مانی کامران (maniKamran)<br>
        <b>ایمیل:</b> m4nikamran@gmail.com<br>
        <b>گیتهاب:</b> <a href="https://github.com/adolfmacro" style="color: #6F4E37;">https://github.com/adolfmacro</a><br>
        <b>تمام حقوق محفوظ است.</b>
        </p>
        """)

        root.addWidget(
            help_text
        )

        # IRC Settings Button
        irc_btn = QPushButton("⚙ تنظیمات IRC")
        irc_btn.setObjectName("Primary")
        irc_btn.setMinimumHeight(40)
        irc_btn.clicked.connect(self.open_irc_settings)
        root.addWidget(irc_btn)

    def open_irc_settings(self):
        """Open IRC Settings page."""
        window = self.window()
        if hasattr(window, 'show_page'):
            window.show_page("تنظیمات IRC")


# ============================================================
# IRC SETTINGS PAGE
# ============================================================

class IRCSettingsPage(QWidget):

    def __init__(self, db, irc_manager=None, parent_window=None):

        super().__init__()

        self.db = db
        self.irc = irc_manager
        self.parent_window = parent_window

        root = QVBoxLayout(self)

        title = QLabel(
            "تنظیمات IRC"
        )

        title.setObjectName(
            "PageTitle"
        )

        root.addWidget(title)

        # Load current settings
        self.settings = load_irc_settings(self.db)

        form = QFormLayout()

        self.enabled = QCheckBox("فعال‌سازی IRC")
        self.enabled.setChecked(self.settings.get("enabled", True))
        form.addRow(self.enabled)

        self.host = QLineEdit()
        self.host.setText(self.settings.get("host", "irc.libera.chat"))
        form.addRow("سرور:", self.host)

        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(self.settings.get("port", 6697))
        form.addRow("پورت:", self.port)

        self.nickname = QLineEdit()
        self.nickname.setText(self.settings.get("nickname", "PATOGH"))
        form.addRow("نام کاربری (Nickname):", self.nickname)

        self.username = QLineEdit()
        self.username.setText(self.settings.get("username", "patogh"))
        form.addRow("نام کاربری (Username):", self.username)

        self.realname = QLineEdit()
        self.realname.setText(self.settings.get("realname", "PATOGH Cafe"))
        form.addRow("نام واقعی:", self.realname)

        self.channel = QLineEdit()
        self.channel.setText(self.settings.get("channel", "#myCh"))
        form.addRow("کانال:", self.channel)

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setText(self.settings.get("password", ""))
        form.addRow("رمز عبور (اختیاری):", self.password)

        self.ssl = QCheckBox("استفاده از SSL/TLS")
        self.ssl.setChecked(self.settings.get("ssl", True))
        form.addRow(self.ssl)

        self.auto_connect = QCheckBox("اتصال خودکار در آغاز برنامه")
        self.auto_connect.setChecked(self.settings.get("auto_connect", True))
        form.addRow(self.auto_connect)

        root.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()

        save_btn = QPushButton("ذخیره و اتصال")
        save_btn.setObjectName("Primary")
        save_btn.clicked.connect(self.save_and_connect)

        test_btn = QPushButton("تست اتصال")
        test_btn.clicked.connect(self.test_connection)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(test_btn)
        btn_layout.addStretch()

        root.addLayout(btn_layout)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusWarning")
        root.addWidget(self.status_label)

        root.addStretch()

    def save_and_connect(self):
        """Save settings and reconnect IRC."""
        new_settings = {
            "enabled": self.enabled.isChecked(),
            "host": self.host.text().strip(),
            "port": self.port.value(),
            "nickname": self.nickname.text().strip(),
            "username": self.username.text().strip(),
            "realname": self.realname.text().strip(),
            "channel": self.channel.text().strip(),
            "password": self.password.text(),
            "ssl": self.ssl.isChecked(),
            "auto_connect": self.auto_connect.isChecked(),
        }

        # Validate
        if not new_settings["host"]:
            QMessageBox.warning(self, "خطا", "آدرس سرور را وارد کنید.")
            return
        if not new_settings["nickname"]:
            QMessageBox.warning(self, "خطا", "نام کاربری (Nickname) را وارد کنید.")
            return
        if not new_settings["channel"]:
            QMessageBox.warning(self, "خطا", "نام کانال را وارد کنید.")
            return

        # Save to database
        save_irc_settings(self.db, new_settings)
        self.settings = new_settings

        # Update parent window settings
        if self.parent_window:
            self.parent_window.irc_settings = new_settings

        # Reconnect IRC
        if self.irc:
            self.irc.disconnect()

        self.status_label.setText("در حال اتصال...")
        self.status_label.setObjectName("StatusWarning")

        # Use QTimer to allow UI to update
        QTimer.singleShot(100, lambda: self._do_connect(new_settings))

    def _do_connect(self, settings):
        """Connect in background."""
        from irc import IRCManager
        from PyQt6.QtWidgets import QProgressDialog, QApplication
        from PyQt6.QtCore import Qt, QTimer, QEventLoop

        progress = QProgressDialog("در حال اتصال به سرور IRC...", "انصراف", 0, 0, self)
        progress.setWindowTitle("اتصال IRC")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        mgr = IRCManager(settings)
        connected = [False]
        error_msg = [None]
        loop = QEventLoop()

        def on_connected():
            connected[0] = True
            loop.quit()

        def on_error(err):
            error_msg[0] = str(err)
            loop.quit()

        mgr.connect(on_connected=on_connected, on_error=on_error)

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(30000)

        loop.exec()

        progress.close()

        if connected[0]:
            self.irc = mgr
            if self.parent_window:
                self.parent_window.irc = mgr
            self.status_label.setText("✓ متصل شد")
            self.status_label.setObjectName("StatusOK")
            QMessageBox.information(self, "موفقیت", "تنظیمات ذخیره و اتصال برقرار شد.")
        else:
            if error_msg[0]:
                self.status_label.setText(f"✗ خطا: {user_friendly_error(Exception(error_msg[0]))}")
                self.status_label.setObjectName("StatusError")
            else:
                self.status_label.setText("✗ خطای ناشناخته")
                self.status_label.setObjectName("StatusError")

    def test_connection(self):
        """Test IRC connection without saving."""
        test_settings = {
            "enabled": True,
            "host": self.host.text().strip(),
            "port": self.port.value(),
            "nickname": self.nickname.text().strip(),
            "username": self.username.text().strip(),
            "realname": self.realname.text().strip(),
            "channel": self.channel.text().strip(),
            "password": self.password.text(),
            "ssl": self.ssl.isChecked(),
            "auto_connect": False,
        }

        if not test_settings["host"] or not test_settings["nickname"] or not test_settings["channel"]:
            QMessageBox.warning(self, "خطا", "سرور، نام کاربری و کانال را وارد کنید.")
            return

        self.status_label.setText("در حال تست اتصال...")
        self.status_label.setObjectName("StatusWarning")

        QTimer.singleShot(100, lambda: self._do_test(test_settings))

    def _do_test(self, settings):
        """Test connection."""
        from irc import IRCManager
        from PyQt6.QtWidgets import QProgressDialog, QApplication
        from PyQt6.QtCore import Qt, QTimer, QEventLoop

        progress = QProgressDialog("در حال تست اتصال...", "انصراف", 0, 0, self)
        progress.setWindowTitle("تست اتصال IRC")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        mgr = IRCManager(settings)
        connected = [False]
        error_msg = [None]
        loop = QEventLoop()

        def on_connected():
            connected[0] = True
            loop.quit()

        def on_error(err):
            error_msg[0] = str(err)
            loop.quit()

        mgr.connect(on_connected=on_connected, on_error=on_error)

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(15000)

        loop.exec()

        progress.close()
        mgr.disconnect()

        if connected[0]:
            self.status_label.setText("✓ تست اتصال موفق")
            self.status_label.setObjectName("StatusOK")
            QMessageBox.information(self, "موفقیت", "اتصال به سرور IRC با موفقیت برقرار شد.")
        else:
            if error_msg[0]:
                self.status_label.setText(f"✗ خطا: {user_friendly_error(Exception(error_msg[0]))}")
                self.status_label.setObjectName("StatusError")
            else:
                self.status_label.setText("✗ خطای ناشناخته")
                self.status_label.setObjectName("StatusError")


# ============================================================
# MAIN WINDOW
# ============================================================

class MainWindow(QMainWindow):

    def __init__(self, db, irc_manager=None):

        super().__init__()

        self.db = db

        self.setWindowTitle(
            f"{APP_NAME} {APP_VERSION}"
        )

        self.resize(
            1280,
            780
        )

        self.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft
        )

        self.irc_settings = load_irc_settings(self.db)
        self.irc = irc_manager

        central = QWidget()

        layout = QHBoxLayout(
            central
        )

        layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        layout.setSpacing(0)

        self._create_menu()

        self.sidebar = self.create_sidebar()

        self.stack = QStackedWidget()

        layout.addWidget(
            self.sidebar
        )

        layout.addWidget(
            self.stack,
            1
        )

        self.setCentralWidget(
            central
        )

        self.pages = {}

        self.add_page(
            "داشبورد",
            DashboardPage(self.db)
        )

        self.add_page(
            "فروش",
            SalesPage(self.db)
        )

        self.add_page(
            "محصولات",
            ProductsPage(self.db)
        )

        self.add_page(
            "خرید",
            PurchasesPage(self.db)
        )

        self.add_page(
            "انبار",
            InventoryPage(self.db)
        )

        self.add_page(
            "صندوق",
            CashPage(self.db)
        )

        self.add_page(
            "هزینه‌ها",
            ExpensesPage(self.db)
        )

        self.add_page(
            "گزارش‌ها",
            ReportsPage(self.db)
        )

        self.add_page(
            "جستجوی دیتابیس",
            DatabaseSearchPage(self.db)
        )

        self.add_page(
            "تراکنش‌ها",
            TransactionsPage(self.db)
        )

        self.add_page(
            "پشتیبان‌گیری",
            BackupPage(self.db)
        )

        self.add_page(
            "تنظیمات IRC",
            IRCSettingsPage(self.db, self.irc, self)
        )

        self.add_page(
            "راهنما",
            HelpPage()
        )

        self.show_page(
            "داشبورد"
        )

        # Wire IRC to pages
        for name in ("فروش", "خرید", "هزینه‌ها", "صندوق", "تنظیمات IRC"):
            page = self.pages.get(name)
            if page:
                page.irc = self.irc


    # --------------------------------------------------------
    # MENU
    # --------------------------------------------------------

    def _create_menu(self):
        pass

    def closeEvent(self, event):

        if self.irc:
            self.irc.disconnect()
        self.db.close()

        event.accept()

    def create_sidebar(self):

        sidebar = QFrame()

        sidebar.setObjectName(
            "Sidebar"
        )

        sidebar.setFixedWidth(
            220
        )

        layout = QVBoxLayout(
            sidebar
        )

        logo = QLabel(
            "PATOGH"
        )

        logo.setObjectName(
            "Logo"
        )

        subtitle = QLabel(
            "Café Management"
        )

        subtitle.setObjectName(
            "Subtitle"
        )

        layout.addWidget(
            logo
        )

        layout.addWidget(
            subtitle
        )

        buttons = [
            "داشبورد",
            "فروش",
            "محصولات",
            "خرید",
            "انبار",
            "صندوق",
            "هزینه‌ها",
            "گزارش‌ها",
            "جستجوی دیتابیس",
            "تراکنش‌ها",
            "پشتیبان‌گیری",
            "تنظیمات IRC",
            "راهنما",
        ]

        for name in buttons:

            button = QPushButton(
                name
            )

            button.setMinimumHeight(
                42
            )

            button.clicked.connect(
                lambda checked=False,
                page=name:
                self.show_page(page)
            )

            layout.addWidget(
                button
            )

        layout.addStretch()

        # DEV label
        dev_label = QLabel(
            "DEV: maniKamran"
        )
        dev_label.setStyleSheet(
            "color:#888;padding:10px;font-size:11px;"
        )
        dev_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(dev_label)

        version = QLabel(
            f"v{APP_VERSION}"
        )

        version.setStyleSheet(
            "color:#66717D;padding:10px;"
        )

        layout.addWidget(
            version
        )

        return sidebar

    def add_page(self, name, widget):

        self.pages[name] = widget

        self.stack.addWidget(
            widget
        )

    def show_page(self, name):

        widget = self.pages.get(
            name
        )

        if widget is None:
            return

        self.stack.setCurrentWidget(
            widget
        )

        if hasattr(
            widget,
            "refresh"
        ):
            try:
                widget.refresh()
            except Exception:
                pass

    def closeEvent(self, event):

        self.db.close()

        event.accept()


# ============================================================
# APPLICATION
# ============================================================

def get_app_fonts():
    """Get platform-appropriate font families with fallbacks."""
    system = platform.system().lower()
    if system == "windows":
        # Windows built-in fonts
        return ["Segoe UI", "Tahoma", "Arial", "Sans Serif"]
    elif system == "darwin":
        # macOS built-in fonts
        return ["SF Pro Display", "Helvetica Neue", "Helvetica", "Arial", "Sans Serif"]
    else:
        # Linux - try Noto, then DejaVu, then system default
        return ["Noto Sans", "Noto Sans Arabic", "DejaVu Sans", "Ubuntu", "Cantarell", "Sans Serif"]


def get_stylesheet():
    """Generate stylesheet with platform-appropriate fonts."""
    fonts = get_app_fonts()
    font_family = ", ".join(f'"{f}"' for f in fonts)
    
    css = """
/* ============================================================
   PATOGH - COFFEE / CREAM UI
   ============================================================ */

* {
    font-family: FONT_FAMILY_PLACEHOLDER;
    font-size: 15px;
}

/* ============================================================
   MAIN APPLICATION
   ============================================================ */

QWidget {
    background-color: #F5EBDD;
    color: #2B1B14;
}

QMainWindow {
    background-color: #F5EBDD;
}

/* ============================================================
   LABELS
   ============================================================ */

QLabel {
    color: #2B1B14;
    background: transparent;
}

QLabel#PageTitle {
    font-size: 27px;
    font-weight: 800;
    color: #3B2419;
    padding: 6px 2px 14px 2px;
}

QLabel#CardTitle {
    font-size: 15px;
    font-weight: 600;
    color: #795548;
}

QLabel#CardValue {
    font-size: 25px;
    font-weight: 800;
    color: #4E342E;
}

QLabel#Logo {
    font-size: 27px;
    font-weight: 900;
    color: #F8E9D2;
    padding: 8px;
}

QLabel#Subtitle {
    font-size: 14px;
    color: #CDB9A5;
    padding-bottom: 18px;
}

/* ============================================================
   SIDEBAR
   ============================================================ */

QFrame#Sidebar {
    background-color: #2B1B14;
    border-right: 1px solid #4A3025;
}

QFrame#Sidebar QPushButton {
    background-color: transparent;
    color: #F5EBDD;
    border: none;
    padding: 12px 16px;
    text-align: left;
    font-size: 15px;
}

QFrame#Sidebar QPushButton:hover {
    background-color: #3D281F;
}

QFrame#Sidebar QPushButton:checked {
    background-color: #4E342E;
    border-left: 3px solid #D4A574;
}

/* ============================================================
   TABLES
   ============================================================ */

QTableWidget {
    background-color: #FFFFFF;
    alternate-background-color: #FDF8F3;
    border: 1px solid #E8D5C4;
    border-radius: 4px;
    gridline-color: #E8D5C4;
    selection-background-color: #D4A574;
    selection-color: #2B1B14;
}

QHeaderView::section {
    background-color: #F5EBDD;
    color: #3B2419;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #E8D5C4;
    font-weight: 600;
}

QTableCornerButton::section {
    background-color: #F5EBDD;
    border: none;
    border-bottom: 1px solid #E8D5C4;
    border-right: 1px solid #E8D5C4;
}

/* ============================================================
   INPUTS
   ============================================================ */

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit {
    background-color: #FFFFFF;
    border: 1px solid #D4C4B8;
    border-radius: 4px;
    padding: 6px 10px;
    color: #2B1B14;
    selection-background-color: #D4A574;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QTextEdit:focus {
    border: 1px solid #D4A574;
    background-color: #FFFDF8;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    border: 1px solid #D4C4B8;
    selection-background-color: #D4A574;
    selection-color: #2B1B14;
}

/* ============================================================
   BUTTONS
   ============================================================ */

QPushButton {
    background-color: #E8D5C4;
    color: #2B1B14;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #D4A574;
}

QPushButton:pressed {
    background-color: #C98D5C;
}

QPushButton:disabled {
    background-color: #E8D5C4;
    color: #A89B91;
}

/* Primary Button - Green */
QPushButton[primary="true"] {
    background-color: #4CAF50;
    color: white;
}

QPushButton[primary="true"]:hover {
    background-color: #43A047;
}

QPushButton[primary="true"]:pressed {
    background-color: #388E3C;
}

/* Danger Button - Red */
QPushButton[danger="true"] {
    background-color: #E53935;
    color: white;
}

QPushButton[danger="true"]:hover {
    background-color: #D32F2F;
}

QPushButton[danger="true"]:pressed {
    background-color: #C62828;
}

/* ============================================================
   SCROLLBARS
   ============================================================ */

QScrollBar:vertical {
    background-color: #F5EBDD;
    width: 10px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #D4A574;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #C98D5C;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #F5EBDD;
    height: 10px;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #D4A574;
    border-radius: 5px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #C98D5C;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ============================================================
   MESSAGE BOX / DIALOGS
   ============================================================ */

QMessageBox {
    background-color: #F5EBDD;
}

QMessageBox QLabel {
    color: #2B1B14;
    font-size: 15px;
}

QMessageBox QPushButton {
    min-width: 80px;
    padding: 8px 16px;
}

/* ============================================================
   PROGRESS BAR
   ============================================================ */

QProgressBar {
    background-color: #E8D5C4;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: #2B1B14;
}

QProgressBar::chunk {
    background-color: #4CAF50;
    border-radius: 4px;
}

/* ============================================================
   TOOLTIPS
   ============================================================ */

QToolTip {
    background-color: #2B1B14;
    color: #F5EBDD;
    border: 1px solid #4A3025;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 13px;
}

/* ============================================================
   TAB WIDGET
   ============================================================ */

QTabWidget::pane {
    border: 1px solid #E8D5C4;
    background-color: #FFFFFF;
    border-radius: 4px;
}

QTabBar::tab {
    background-color: #F5EBDD;
    color: #3B2419;
    padding: 8px 16px;
    border: 1px solid #E8D5C4;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #FFFFFF;
    border-bottom: 1px solid #FFFFFF;
    color: #2B1B14;
}

QTabBar::tab:hover:!selected {
    background-color: #EDE3D9;
}

/* ============================================================
   GROUP BOX
   ============================================================ */

QGroupBox {
    border: 1px solid #E8D5C4;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 12px;
    color: #3B2419;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #3B2419;
}

/* ============================================================
   CHECKBOX / RADIO
   ============================================================ */

QCheckBox, QRadioButton {
    color: #2B1B14;
    spacing: 8px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #D4A574;
    border-radius: 4px;
    background-color: #FFFFFF;
}

QCheckBox::indicator:checked {
    background-color: #4CAF50;
    border-color: #4CAF50;
    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDQuNUw0LjUgOEwxMSAxIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
}

QRadioButton::indicator {
    border-radius: 9px;
}

QRadioButton::indicator:checked {
    background-color: #4CAF50;
    border-color: #4CAF50;
}

/* ============================================================
   STATUS
   ============================================================ */

QLabel#StatusOK {
    color: #4CAF50;
    font-weight: 600;
}

QLabel#StatusError {
    color: #E53935;
    font-weight: 600;
}

QLabel#StatusWarning {
    color: #FB8C00;
    font-weight: 600;
}

/* ============================================================
   INVENTORY STATUS COLORS
   ============================================================ */

QTableWidgetItem[status="ok"] {
    background-color: #E8F5E9;
}

QTableWidgetItem[status="low"] {
    background-color: #FFF8E1;
}

QTableWidgetItem[status="out"] {
    background-color: #FBE9E7;
}
"""
    return css.replace("FONT_FAMILY_PLACEHOLDER", font_family)


def main():
    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        APP_NAME
    )

    app.setApplicationVersion(
        APP_VERSION
    )

    app.setStyleSheet(
        get_stylesheet()
    )

    font = QFont(
        get_app_fonts()[0],
        10
    )

    app.setFont(
        font
    )

    db = Database()

    irc_settings = load_irc_settings(db)
    irc_manager = connect_irc(irc_settings)
    if not irc_manager:
        return

    window = MainWindow(
        db,
        irc_manager
    )

    window.showMaximized()

    sys.exit(
        app.exec()
    )


    # ============================================================
    # ENTRY POINT
    # ============================================================

if __name__ == "__main__":
    main()