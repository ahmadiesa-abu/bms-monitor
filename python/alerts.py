import logging
from datetime import datetime, timedelta, timezone

import yaml

from python import db

log = logging.getLogger(__name__)

with open("error_codes.yaml", "r") as f:
    error_codes = yaml.safe_load(f)

_startup_time = datetime.now(timezone.utc)
SEND_ALLOWED_AFTER = _startup_time + timedelta(minutes=3)


def add_alert(alerts, code):
    alert = error_codes[int(code)]
    alert["id"] = int(code)
    alerts.append(alert)


async def evaluate_alerts(device_address, device_name, cell_info):
    if datetime.now(timezone.utc) < SEND_ALLOWED_AFTER:
        return

    try:
        alerts = []

        if cell_info["state_of_charge"] < 10:
            add_alert(alerts, "1001")
        elif cell_info["state_of_charge"] < 20:
            add_alert(alerts, "1002")
        elif cell_info["state_of_charge"] < 30 and cell_info["charging_status"] == 0:
            add_alert(alerts, "1003")

        if cell_info["voltage_difference"] > 0.1:
            add_alert(alerts, "1004")
        elif cell_info["voltage_difference"] > 0.05:
            add_alert(alerts, "1005")

        if cell_info["average_voltage"] < 3.0:
            add_alert(alerts, "1006")
        elif cell_info["average_voltage"] < 3.2:
            add_alert(alerts, "1007")
        elif cell_info["average_voltage"] > 4.3:
            add_alert(alerts, "1008")
        elif cell_info["average_voltage"] > 4.2:
            add_alert(alerts, "1009")

        max_temp = max(
            cell_info["temperature_sensor_1"],
            cell_info["temperature_sensor_2"],
            cell_info["temperature_sensor_3"],
            cell_info["temperature_sensor_4"],
            cell_info["temperature_sensor_5"],
        )
        if max_temp > 60:
            add_alert(alerts, "1010")
        elif max_temp > 50:
            add_alert(alerts, "1011")

        if cell_info["charge_current"] > 100:
            add_alert(alerts, "1012")
        elif cell_info["charge_current"] > 80:
            add_alert(alerts, "1013")
        elif cell_info["charge_current"] < -100:
            add_alert(alerts, "1014")
        elif cell_info["charge_current"] < -80:
            add_alert(alerts, "1015")

        if cell_info["state_of_health"] < 90:
            add_alert(alerts, "1016")
        elif cell_info["state_of_health"] < 80:
            add_alert(alerts, "1017")

        if cell_info["cell_resistances"] and max(cell_info["cell_resistances"]) > 0.5:
            add_alert(alerts, "1018")
        elif cell_info["cell_resistances"] and max(cell_info["cell_resistances"]) > 0.3:
            add_alert(alerts, "1019")

        if cell_info["battery_voltage"] > 55:
            add_alert(alerts, "1020")
        elif cell_info["battery_voltage"] > 51:
            add_alert(alerts, "1021")
        elif cell_info["battery_voltage"] < 41:
            add_alert(alerts, "1022")
        elif cell_info["battery_voltage"] < 43:
            add_alert(alerts, "1023")

        if cell_info["emergency_time_countdown"] < 5:
            add_alert(alerts, "1024")
        elif cell_info["emergency_time_countdown"] < 10:
            add_alert(alerts, "1025")

        if cell_info["cycle_count"] > 2000:
            add_alert(alerts, "1026")
        elif cell_info["cycle_count"] > 1500:
            add_alert(alerts, "1027")

        config = db.get_config()
        n_hours = config.get("n_hours", 12)
        for alert in alerts:
            db.insert_alert_data(device_address, device_name, alert["id"], datetime.now(), n_hours)
            log.warning("[ALERT] %s - %s: %s", device_name, alert["id"], alert["message"])

        return alerts
    except Exception as e:
        log.error("Alert evaluation error: %s", e)
