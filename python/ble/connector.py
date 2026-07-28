import logging
from datetime import datetime
from bleak import BleakClient

from config import CHARACTERISTIC_UUID, MIN_FRAME_SIZE, MAX_FRAME_SIZE
from python.ble.protocol import (
    calculate_crc, create_write_command, parse_device_info, parse_cell_info, parse_setting_info,
)
from python.data_store import data_store

log = logging.getLogger(__name__)


async def notification_handler(device, data, device_name, device_address, active_connections):
    if device_address not in active_connections:
        await data_store.clear_buffer(device_name)
        return

    log.debug("[%s] RAW notify: len=%d hex=%s", device_name, len(data), data.hex())
    if data[:4] == b'\x55\xAA\xEB\x90':
        await data_store.clear_buffer(device_name)
    await data_store.append_to_buffer(device_name, data)

    buffer = await data_store.get_buffer_snapshot(device_name)
    if MIN_FRAME_SIZE <= len(buffer) <= MAX_FRAME_SIZE:
        received_crc = buffer[299]
        calculated_crc = calculate_crc(buffer[:299])
        if calculated_crc != received_crc:
            alt_crc = calculate_crc(buffer[:-1])
            alt_received = buffer[-1]
            log.warning(
                "[%s] CRC mismatch at idx 299: calc=%s rcvd=%s (buf_len=%s, alt_last_byte=%s alt_crc=%s, frame_type=0x%02X)",
                device_name, calculated_crc, received_crc, len(buffer), alt_received, alt_crc, buffer[4]
            )
            return

        frame_type = buffer[4]
        if frame_type == 0x03:
            try:
                info = parse_device_info(buffer, device_address)
                info["name"] = info.pop("device_name")
                info.pop("device_address", None)
                info["connected"] = True
                info["enabled"] = True
                from python import db
                db.update_device(device_address, **info)
                log.info("[%s] Device info parsed", device_name)
            except Exception as e:
                log.error("[%s] Failed to parse device info: %s", device_name, e)
        elif frame_type == 0x02:
            try:
                cell_info = parse_cell_info(buffer, device_address)
                await data_store.update_cell_info(device_name, cell_info)
                await data_store.update_last_cell_info_update(device_name)
                from python.alerts import evaluate_alerts
                await evaluate_alerts(device_address, device_name, cell_info)
                log.info("[%s] Cell info parsed", device_name)
            except Exception as e:
                log.error("[%s] Failed to parse cell info: %s", device_name, e)
        elif frame_type == 0x01:
            try:
                setting_info = parse_setting_info(buffer, device_address, device_name)
                await data_store.update_setting_info(device_address, setting_info)
                log.info("[%s] Settings parsed", device_name)
            except Exception as e:
                log.error("[%s] Failed to parse settings: %s", device_name, e)
        else:
            log.warning("[%s] Unknown frame type %s", device_name, frame_type)

        await data_store.clear_buffer(device_name)


async def write_setting(client, register, value, length, device_name):
    command = create_write_command(register, value, length)
    await client.write_gatt_char(CHARACTERISTIC_UUID, command)
    log.info("[%s] Write sent: register=0x%02X value=%s len=%s", device_name, register, value, length)
