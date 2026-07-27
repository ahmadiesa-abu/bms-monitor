import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timedelta

from config import DB_NAME, DEFAULT_PASSWORD
from python.auth import hash_password

data_aggregator = defaultdict(lambda: {
    "device_name": None,
    "device_address": None,
    "current_sum": 0,
    "remaining_capacity": 0,
    "power_sum": 0,
    "count": 0,
    "last_insert_time": None,
})

CONFIG_CACHE = None
CONFIG_CACHE_TIMESTAMP = 0
CONFIG_CACHE_EXPIRY = 60

DEVICE_CACHE = {}
DEVICE_CACHE_EXPIRY = 60

ALERT_CACHE = {}
ALERT_CACHE_EXPIRY = 60

AGGREGATED_CACHE = {}
AGGREGATED_CACHE_EXPIRY = 240


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    return conn


def create_tables():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS bms_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                current REAL NOT NULL,
                remaining_capacity REAL NOT NULL,
                power REAL NOT NULL,
                device_address TEXT NOT NULL,
                device_name TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON bms_data (timestamp)")

        c.execute("""
            CREATE TABLE IF NOT EXISTS error_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_address TEXT NOT NULL,
                error_code TEXT NOT NULL,
                device_name TEXT NOT NULL,
                occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                password TEXT DEFAULT '',
                n_hours INTEGER DEFAULT 12
            )
        """)
        c.execute("SELECT COUNT(*) FROM configs")
        if c.fetchone()[0] == 0:
            c.execute(
                "INSERT INTO configs (password, n_hours) VALUES (?, ?)",
                (hash_password(DEFAULT_PASSWORD), 12),
            )

        c.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL UNIQUE,
                name TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                connected BOOLEAN DEFAULT FALSE,
                enabled BOOLEAN DEFAULT TRUE,
                frame_type INTEGER,
                frame_counter INTEGER,
                vendor_id TEXT,
                hardware_version TEXT,
                software_version TEXT,
                device_uptime INTEGER,
                power_on_count INTEGER,
                manufacturing_date TEXT,
                serial_number TEXT,
                user_data TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS active_tokens (
                token TEXT PRIMARY KEY,
                created_at TEXT
            )
        """)
        conn.commit()


def set_all_devices_disconnected():
    with get_connection() as conn:
        conn.execute("UPDATE devices SET connected = ?", (False,))
        conn.commit()


def get_all_devices(only_enabled=False):
    now = time.time()
    if DEVICE_CACHE and all(
        (now - v["timestamp"]) < DEVICE_CACHE_EXPIRY for v in DEVICE_CACHE.values()
    ):
        return [v["data"] for v in DEVICE_CACHE.values()]

    with get_connection() as conn:
        c = conn.cursor()
        q = """
            SELECT id, address, name, added_at, connected, enabled, frame_type, frame_counter,
                   vendor_id, hardware_version, software_version, device_uptime, power_on_count,
                   manufacturing_date, serial_number, user_data
            FROM devices
        """
        params = ()
        if only_enabled:
            q += " WHERE enabled = ?"
            params = (True,)
        c.execute(q, params)
        rows = c.fetchall()

    DEVICE_CACHE.clear()
    for r in rows:
        d = {
            "id": r[0], "address": r[1], "name": r[2], "added_at": r[3],
            "connected": bool(r[4]), "enabled": bool(r[5]), "frame_type": r[6],
            "frame_counter": r[7], "vendor_id": r[8], "hardware_version": r[9],
            "software_version": r[10], "device_uptime": r[11], "power_on_count": r[12],
            "manufacturing_date": r[13], "serial_number": r[14], "user_data": r[15],
        }
        DEVICE_CACHE[r[1]] = {"data": d, "timestamp": time.time()}

    return [v["data"] for v in DEVICE_CACHE.values()]


def get_device_by_address(address, force_refresh=False):
    now = time.time()
    if not force_refresh and address in DEVICE_CACHE and (now - DEVICE_CACHE[address]["timestamp"]) < DEVICE_CACHE_EXPIRY:
        return DEVICE_CACHE[address]["data"]

    with get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, address, name, added_at, connected, enabled, frame_type, frame_counter,
                   vendor_id, hardware_version, software_version, device_uptime, power_on_count,
                   manufacturing_date, serial_number, user_data
            FROM devices WHERE address = ?
        """, (address.lower(),))
        r = c.fetchone()
        if not r:
            return None

    d = {
        "id": r[0], "address": r[1], "name": r[2], "added_at": r[3],
        "connected": bool(r[4]), "enabled": bool(r[5]), "frame_type": r[6],
        "frame_counter": r[7], "vendor_id": r[8], "hardware_version": r[9],
        "software_version": r[10], "device_uptime": r[11], "power_on_count": r[12],
        "manufacturing_date": r[13], "serial_number": r[14], "user_data": r[15],
    }
    DEVICE_CACHE[address] = {"data": d, "timestamp": time.time()}
    return d


def update_device(address, **kwargs):
    if not kwargs:
        return
    with get_connection() as conn:
        fields = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [address]
        conn.execute(f"UPDATE devices SET {fields} WHERE address = ?", values)
        conn.commit()
    DEVICE_CACHE.pop(address, None)


def update_device_status(address, connected, enabled):
    with get_connection() as conn:
        conn.execute(
            "UPDATE devices SET connected = ?, enabled = ? WHERE address = ?",
            (connected, enabled, address),
        )
        conn.commit()
    DEVICE_CACHE.pop(address, None)


def insert_device(address, name=None, frame_type=None, frame_counter=None, vendor_id=None,
                  hardware_version=None, software_version=None, device_uptime=None,
                  power_on_count=None, manufacturing_date=None, serial_number=None,
                  user_data=None, connected=False, enabled=True):
    existing = get_device_by_address(address)
    if existing:
        return existing

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO devices (address, name, added_at, connected, enabled, frame_type,
                frame_counter, vendor_id, hardware_version, software_version, device_uptime,
                power_on_count, manufacturing_date, serial_number, user_data)
            VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (address, name, connected, enabled, frame_type, frame_counter, vendor_id,
              hardware_version, software_version, device_uptime, power_on_count,
              manufacturing_date, serial_number, user_data))
        conn.commit()
    return get_device_by_address(address)


def insert_data(timestamp, current, power, remaining_capacity, device_address, device_name):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO bms_data (timestamp, current, power, remaining_capacity, device_address, device_name)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (timestamp, current, power, remaining_capacity, device_address, device_name))
        conn.commit()


def insert_alert_data(device_address, device_name, error_code, occurred_at, n_hours=12):
    time_limit = (datetime.now() - timedelta(hours=n_hours)).strftime('%Y-%m-%d %H:%M:%S')

    key = f"{device_address}:{error_code}"
    if key in ALERT_CACHE and ALERT_CACHE[key] > time_limit:
        return

    with get_connection() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id FROM error_notifications WHERE device_address = ? AND error_code = ? AND occurred_at > ?",
            (device_address, str(error_code), time_limit),
        )
        if c.fetchone():
            ALERT_CACHE[key] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            return

        c.execute(
            "INSERT INTO error_notifications (device_address, error_code, occurred_at, device_name) VALUES (?, ?, ?, ?)",
            (device_address, str(error_code), occurred_at, device_name),
        )
        conn.commit()
    ALERT_CACHE[key] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def fetch_all_notifications():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM error_notifications ORDER BY occurred_at DESC")
        return c.fetchall()


def delete_alert_by_id(alert_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM error_notifications WHERE id = ?", (alert_id,))
        conn.commit()


def delete_all_alerts():
    with get_connection() as conn:
        conn.execute("DELETE FROM error_notifications")
        conn.commit()


def fetch_all_data(days=1):
    now = datetime.now()
    cache_key = days
    if cache_key in AGGREGATED_CACHE:
        cached, cache_time = AGGREGATED_CACHE[cache_key]
        if (now - cache_time).total_seconds() < AGGREGATED_CACHE_EXPIRY:
            return cached

    if days == 1:
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        cutoff = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)

    with get_connection() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT timestamp, current, power, device_address, device_name, remaining_capacity FROM bms_data WHERE timestamp >= ?",
            (cutoff.strftime('%Y-%m-%d %H:%M:%S'),),
        )
        result = c.fetchall()

    AGGREGATED_CACHE[cache_key] = (result, now)
    return result


def update_aggregated_data(device_name, device_address, current, power, remaining_capacity):
    d = data_aggregator[device_address]
    if d["device_name"] is None:
        d["device_name"] = device_name
    if d["device_address"] is None:
        d["device_address"] = device_address
    d["current_sum"] += current
    d["power_sum"] += power
    d["remaining_capacity"] += remaining_capacity
    d["count"] += 1
    if d["last_insert_time"] is None:
        d["last_insert_time"] = datetime.now()


def save_aggregated_data(device_name, device_address, device_data, interval=60):
    now = datetime.now()
    last = device_data["last_insert_time"]
    if last and (now - last).total_seconds() < interval:
        return
    if device_data["count"] <= 0:
        return

    current_avg = device_data["current_sum"] / device_data["count"]
    power_avg = device_data["power_sum"] / device_data["count"]
    rc_avg = device_data["remaining_capacity"] / device_data["count"]

    insert_data(
        timestamp=now.strftime('%Y-%m-%d %H:%M:%S'),
        current=current_avg,
        power=power_avg,
        remaining_capacity=rc_avg,
        device_address=device_address,
        device_name=device_name,
    )
    device_data.update({
        "current_sum": 0, "power_sum": 0, "remaining_capacity": 0,
        "count": 0, "last_insert_time": now,
    })


def get_config():
    global CONFIG_CACHE, CONFIG_CACHE_TIMESTAMP
    if CONFIG_CACHE and (time.time() - CONFIG_CACHE_TIMESTAMP) < CONFIG_CACHE_EXPIRY:
        return CONFIG_CACHE

    with get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT password, n_hours FROM configs LIMIT 1")
        row = c.fetchone()
        if row:
            CONFIG_CACHE = {"password": row[0], "n_hours": row[1]}
            CONFIG_CACHE_TIMESTAMP = time.time()
            return CONFIG_CACHE
    return None


def update_config(password=None, n_hours=None):
    global CONFIG_CACHE, CONFIG_CACHE_TIMESTAMP
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT password, n_hours FROM configs LIMIT 1")
        existing = c.fetchone()
        if not existing:
            return None

        new_pwd = password if password is not None else existing[0]
        new_n = n_hours if n_hours is not None else existing[1]
        c.execute("UPDATE configs SET password = ?, n_hours = ?", (new_pwd, new_n))
        conn.commit()
    CONFIG_CACHE = None
    CONFIG_CACHE_TIMESTAMP = 0
    return get_config()


def add_token(token):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO active_tokens (token, created_at) VALUES (?, ?)",
            (token, datetime.now().isoformat()),
        )
        conn.commit()


def remove_token(token):
    with get_connection() as conn:
        conn.execute("DELETE FROM active_tokens WHERE token = ?", (token,))
        conn.commit()


def is_token_valid(token, lifetime_days=30):
    lifetime_seconds = lifetime_days * 86400
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT created_at FROM active_tokens WHERE token = ?", (token,))
        row = c.fetchone()
        if not row:
            return False
        created = datetime.fromisoformat(row[0])
        if datetime.now() < created + timedelta(seconds=lifetime_seconds):
            return True
        conn.execute("DELETE FROM active_tokens WHERE token = ?", (token,))
        conn.commit()
        return False
