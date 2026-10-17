import sqlite3
from datetime import datetime
from pathlib import Path
try:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP
except ImportError:  # mcp 2.x: FastMCP wurde in MCPServer umbenannt
    from mcp.server.mcpserver import MCPServer as FastMCP

# Dateien liegen immer neben diesem Skript (unabhängig vom Arbeitsverzeichnis)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "inventory.db")
LOG_PATH = str(BASE_DIR / "audit_log.txt")

# Server initialisieren
server_mcp = FastMCP("MCI-Freelance-IT-System")


# ==========================================
# SETUP: Lokale Datenbank für die Korrektur
# ==========================================
def setup_database():
    """Erstellt eine lokale SQLite Datenbank für die Hausaufgabe."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT,
            category TEXT,
            stock INTEGER,
            price REAL
        )
    ''')
    # Basis-Datenbestand
    cursor.execute('INSERT OR IGNORE INTO products VALUES (1, "WiFi 6 Access Point (Unifi)", "Hardware", 5, 150.00)')
    cursor.execute('INSERT OR IGNORE INTO products VALUES (2, "NAS 4TB HDD", "Hardware", 2, 95.00)')
    cursor.execute('INSERT OR IGNORE INTO products VALUES (3, "IT Support Hour", "Service", 100, 85.00)')
    cursor.execute('INSERT OR IGNORE INTO products VALUES (4, "Wedding Video Package", "Service", 10, 1250.00)')
    conn.commit()
    conn.close()


setup_database()


# ==========================================
# TOOL 1: SQL Database Lookup (Product Inventory)
# ==========================================
@server_mcp.tool()
def query_inventory(product_name: str) -> str:
    """Queries the SQLite product inventory database for stock and pricing."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT name, stock, price FROM products WHERE name LIKE ?', ('%' + product_name + '%',))
    result = cursor.fetchone()
    conn.close()

    if result:
        return f"Product found: {result[0]} | Stock: {result[1]} | Price: €{result[2]}"
    return f"Product '{product_name}' not found in inventory."


# ==========================================
# TOOL 2: Formula Engine (Tiered Discounts)
# ==========================================
@server_mcp.tool()
def calculate_tiered_discount(unit_price: float, volume: int) -> str:
    """Computes complex tiered discounts based on order volume."""
    total_base_price = unit_price * volume
    discount_percent = 0.0

    if volume >= 50:
        discount_percent = 0.20
    elif volume >= 20:
        discount_percent = 0.15
    elif volume >= 5:
        discount_percent = 0.05

    discount_amount = total_base_price * discount_percent
    final_price = total_base_price - discount_amount

    return (f"Volume: {volume}, Base Price: €{total_base_price:.2f}, "
            f"Discount: {discount_percent * 100:.0f}%, Final Price: €{final_price:.2f}")


# ==========================================
# TOOL 3: Log Audit Tool
# ==========================================
@server_mcp.tool()
def log_audit_event(event_description: str) -> str:
    """Appends security and audit events to a local file resource."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] AUDIT: {event_description}\n"

    with open(LOG_PATH, "a", encoding="utf-8") as log_file:
        log_file.write(log_entry)

    return "Event successfully audited and written to log."


if __name__ == "__main__":
    server_mcp.run()