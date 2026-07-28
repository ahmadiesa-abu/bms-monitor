import asyncio
import logging
import os
import sys
import threading
from datetime import datetime, timedelta
from uuid import uuid4

from flask import (
    Flask, render_template, request, redirect, url_for, session, jsonify, flash,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SECRET_KEY, TOKEN_LIFETIME_DAYS, JK_BMS_OUI
from python import db
from python.auth import hash_password, verify_password, login_required
from python.data_store import data_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

_loop = None


def get_event_loop():
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    return _loop


def run_async(coro):
    loop = get_event_loop()
    if loop.is_running():
        import concurrent.futures
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=30)
    else:
        return loop.run_until_complete(coro)


def _start_ble_background():
    loop = get_event_loop()
    thread = threading.Thread(target=_run_loop, args=(loop,), daemon=True)
    thread.start()


def _run_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


async def _ble_background_task():
    from python.ble.manager import ble_main
    from python.data_store import data_store as ds

    await asyncio.sleep(2)
    while True:
        try:
            await ble_main()
        except Exception as e:
            log.error("BLE background error: %s", e)
            await asyncio.sleep(5)


async def _aggregation_task():
    from config import AGGREGATED_SAVE_INTERVAL
    while True:
        try:
            for addr, data in dict(db.data_aggregator).items():
                if data["device_name"] and data["count"] > 0:
                    db.save_aggregated_data(data["device_name"], addr, data, interval=AGGREGATED_SAVE_INTERVAL)
        except Exception as e:
            log.error("Aggregation error: %s", e)
        await asyncio.sleep(60)


@app.before_request
def before_request():
    if not hasattr(app, '_bg_started'):
        app._bg_started = True
        db.create_tables()
        db.set_all_devices_disconnected()
        loop = get_event_loop()
        asyncio.run_coroutine_threadsafe(_ble_background_task(), loop)
        asyncio.run_coroutine_threadsafe(_aggregation_task(), loop)


@app.teardown_appcontext
def shutdown_session(exception=None):
    pass


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        password = request.form.get("password", "")
        config = db.get_config()
        if not config or not verify_password(password, config["password"]):
            flash("Invalid password", "error")
            return render_template("login.html")

        token = str(uuid4())
        db.add_token(token)
        session["token"] = token
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    token = session.pop("token", None)
    if token:
        db.remove_token(token)
    return redirect(url_for("login_page"))


@app.route("/")
@login_required
def dashboard():
    devices = db.get_all_devices()
    return render_template("dashboard.html", devices=devices)


@app.route("/devices")
@login_required
def devices_page():
    devices = db.get_all_devices()
    return render_template("devices.html", devices=devices)


@app.route("/device/<address>")
@login_required
def device_detail_page(address):
    device = db.get_device_by_address(address)
    if not device:
        flash("Device not found", "error")
        return redirect(url_for("devices_page"))
    return render_template("device_detail.html", device=device)


@app.route("/alerts")
@login_required
def alerts_page():
    return render_template("alerts.html")


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "change_password":
            old_pwd = request.form.get("old_password", "")
            new_pwd = request.form.get("new_password", "")
            config = db.get_config()
            if not verify_password(old_pwd, config["password"]):
                flash("Current password is incorrect", "error")
            elif not new_pwd:
                flash("New password cannot be empty", "error")
            else:
                db.update_config(password=hash_password(new_pwd))
                flash("Password changed successfully", "success")

        elif action == "update_config":
            try:
                n_hours = int(request.form.get("n_hours", 12))
                db.update_config(n_hours=n_hours)
                flash("Settings updated", "success")
            except ValueError:
                flash("Invalid value for alert cooldown", "error")

        return redirect(url_for("settings_page"))

    config = db.get_config()
    return render_template("settings.html", config=config)


@app.route("/scan-devices")
@login_required
def scan_devices():
    try:
        devices = run_async(_do_scan())
        return jsonify({"devices": devices})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


async def _do_scan():
    from python.ble.scanner import scan_for_devices
    return await scan_for_devices()


@app.route("/api/connect-device", methods=["POST"])
@login_required
def api_connect_device():
    data = request.get_json()
    address = data.get("address", "").strip().lower()
    name = data.get("name", "").strip() or address

    if not address:
        return jsonify({"error": "Device address is required"}), 400

    from python.ble.manager import active_connections
    if address in active_connections:
        return jsonify({"message": f"Device {address} is already connected."})

    try:
        existing = db.get_device_by_address(address)
        if not existing:
            existing = db.insert_device(address=address, name=name, connected=False, enabled=True)

        db.update_device_status(address, connected=True, enabled=True)

        loop = get_event_loop()

        async def _connect():
            from python.ble.scanner import find_device_by_address
            from python.ble.manager import connect_and_run
            ble_device = await find_device_by_address(address)
            if ble_device:
                await connect_and_run(ble_device, active_connections)

        asyncio.run_coroutine_threadsafe(_connect(), loop)
        return jsonify({"message": f"Connection initiated for {address}."})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/disconnect-device", methods=["POST"])
@login_required
def api_disconnect_device():
    data = request.get_json()
    address = data.get("address", "").strip().lower()

    if not address:
        return jsonify({"error": "Device address is required"}), 400

    from python.ble.manager import active_connections, disconnect_device_sync
    from python.data_store import data_store as ds

    task = active_connections.pop(address, None)
    if task:
        task.cancel()

    disconnect_device_sync(address)

    device = db.get_device_by_address(address)
    if device:
        run_async(ds.delete_device_data(device["name"] or address))

    return jsonify({"message": f"Device {address} disconnected."})


@app.route("/api/cell-info")
@login_required
def api_cell_info():
    try:
        info = run_async(data_store.get_cell_info())
        if not info:
            return jsonify({"message": "No cell info available yet."}), 404
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/device-info")
@login_required
def api_device_info():
    devices = db.get_all_devices()
    if not devices:
        return jsonify({"message": "No device info available yet."}), 404
    return jsonify(devices)


@app.route("/api/device-settings")
@login_required
def api_device_settings():
    try:
        info = run_async(data_store.get_setting_info())
        if not info:
            return jsonify({"message": "No settings available yet."}), 404
        return jsonify(list(info.values()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/device-settings/write", methods=["POST"])
@login_required
def api_device_settings_write():
    try:
        data = request.get_json()
        address = data.get("address", "").strip().lower()
        key = data.get("key", "").strip()
        value = data.get("value")

        if not address or not key or value is None:
            return jsonify({"error": "address, key, and value are required"}), 400

        from python.ble.protocol import REGISTER_MAP, SWITCH_MAP
        from python.ble.manager import active_connections, queue_write

        if address not in active_connections:
            return jsonify({"error": "Device is not connected"}), 400

        if key in SWITCH_MAP:
            register = SWITCH_MAP[key]
            raw = 1 if value else 0
            length = 4
        elif key in REGISTER_MAP:
            register, length, factor = REGISTER_MAP[key]
            raw = int(round(value * factor))
        else:
            return jsonify({"error": f"Unknown setting: {key}"}), 400

        queue_write(address, register, raw, length)
        log.info("Queued write: %s @ %s -> %s (raw=%s)", key, address, value, raw)
        return jsonify({"message": f"Write queued for {key}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/aggregated-data")
@login_required
def api_aggregated_data():
    days = request.args.get("days", 1, type=int)
    data = db.fetch_all_data(days=days)
    if not data:
        return jsonify({"message": "No aggregated data available yet."}), 404
    result = []
    for row in data:
        result.append({
            "timestamp": row[0],
            "current": row[1],
            "power": row[2],
            "device_address": row[3],
            "device_name": row[4],
            "remaining_capacity": row[5],
        })
    return jsonify(result)


@app.route("/api/alerts")
@login_required
def api_alerts():
    import yaml
    with open("error_codes.yaml", "r") as f:
        codes = yaml.safe_load(f)

    rows = db.fetch_all_notifications()
    result = []
    for r in rows:
        code = int(r[2]) if isinstance(r[2], str) else r[2]
        entry = {
            "id": r[0],
            "device_address": r[1],
            "error_code": r[2],
            "device_name": r[3],
            "timestamp": r[4],
            "message": codes.get(code, {}).get("message", "Unknown error"),
            "level": codes.get(code, {}).get("level", "unknown"),
        }
        result.append(entry)
    return jsonify(result)


@app.route("/api/alerts/<int:alert_id>", methods=["DELETE"])
@login_required
def api_delete_alert(alert_id):
    db.delete_alert_by_id(alert_id)
    return jsonify({"message": f"Alert {alert_id} deleted."})


@app.route("/api/alerts", methods=["DELETE"])
@login_required
def api_delete_all_alerts():
    db.delete_all_alerts()
    return jsonify({"message": "All alerts deleted."})


if __name__ == "__main__":
    _start_ble_background()
    app.run(host="0.0.0.0", port=5000, debug=False)
