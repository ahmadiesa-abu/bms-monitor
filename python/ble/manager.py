import asyncio
import logging
from datetime import datetime

from bleak import BleakClient

from config import CHARACTERISTIC_UUID, CMD_TYPE_DEVICE_INFO, CMD_TYPE_CELL_INFO, CMD_TYPE_SETTINGS
from python.ble.protocol import create_command
from python.ble.connector import notification_handler, write_setting
from python import db
from python.data_store import data_store

log = logging.getLogger(__name__)

active_connections = {}
_scan_lock = asyncio.Lock()
_pending_writes = {}


def queue_write(device_address, register, value, length):
    _pending_writes[device_address] = (register, value, length)


async def connect_and_run(device, active_connections_dict):
    device_address = device.address.lower()

    while True:
        try:
            device_data = db.get_device_by_address(device_address)
            if not device_data:
                device_data = db.insert_device(
                    address=device_address,
                    name=device.name,
                    connected=False,
                    enabled=True,
                )

            if not device_data.get("enabled", False):
                log.info("[%s] Device disabled, stopping", device.name)
                active_connections_dict.pop(device_address, None)
                db.update_device_status(device_address, connected=False, enabled=False)
                break

            async with BleakClient(device.address) as client:
                log.info("[%s] Connected, discovering services...", device.name)
                for service in client.services:
                    log.info("[%s]  Service: %s", device.name, service.uuid)
                    for char in service.characteristics:
                        props = ",".join(char.properties)
                        log.info("[%s]    Char: %s props=[%s] handle=%s",
                                 device.name, char.uuid, props, char.handle)
                        for desc in char.descriptors:
                            log.info("[%s]      Desc: %s", device.name, desc.uuid)

                notify_queue = asyncio.Queue()

                def handle_notification(sender, data):
                    log.debug("RAW callback: sender=%s len=%d hex=%s", sender, len(data), data.hex())
                    notify_queue.put_nowait(data)

                await client.start_notify(CHARACTERISTIC_UUID, handle_notification)
                db.update_device_status(device_address, connected=True, enabled=True)
                log.info("[%s] Connected and notifications started", device.name)

                async def process_notifications():
                    while True:
                        data = await notify_queue.get()
                        await notification_handler(
                            device, data, device.name, device_address, active_connections_dict
                        )

                notify_task = asyncio.create_task(process_notifications())

                try:
                    while True:
                        device_data = db.get_device_by_address(device_address)
                        if not device_data or not device_data.get("connected", False):
                            log.info("[%s] Device disconnected, stopping polling", device.name)
                            await data_store.clear_buffer(device.name)
                            active_connections_dict.pop(device_address, None)
                            break

                        if "frame_type" not in device_data or device_data["frame_type"] is None:
                            await client.write_gatt_char(CHARACTERISTIC_UUID, create_command(CMD_TYPE_DEVICE_INFO))
                            await asyncio.sleep(2)

                        settings = await data_store.get_setting_info_by_address(device_address)
                        if not settings:
                            await client.write_gatt_char(CHARACTERISTIC_UUID, create_command(CMD_TYPE_SETTINGS))
                            await asyncio.sleep(8)

                        last_update = await data_store.get_last_cell_info_update(device.name)
                        if not last_update or (datetime.now() - last_update).total_seconds() > 30:
                            await client.write_gatt_char(CHARACTERISTIC_UUID, create_command(CMD_TYPE_DEVICE_INFO))
                            await asyncio.sleep(2)
                            await client.write_gatt_char(CHARACTERISTIC_UUID, create_command(CMD_TYPE_CELL_INFO))
                            await asyncio.sleep(2)

                        pending = _pending_writes.pop(device_address, None)
                        if pending:
                            reg, val, length = pending
                            await write_setting(client, reg, val, length, device.name)
                            await asyncio.sleep(3)

                        await asyncio.sleep(8)
                finally:
                    notify_task.cancel()
                    try:
                        await notify_task
                    except asyncio.CancelledError:
                        pass

        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error("[%s] Connection error: %s", device.name, e)

        log.info("[%s] Retrying connection in 8s...", device.name)
        await asyncio.sleep(8)


async def ble_main():
    async with _scan_lock:
        while True:
            try:
                allowed = db.get_all_devices(only_enabled=True)
                allowed_addrs = {d["address"] for d in allowed}
                connected_addrs = {d["address"].lower() for d in allowed if d["connected"]}

                if allowed_addrs and allowed_addrs.issubset(connected_addrs):
                    await asyncio.sleep(60)
                    continue

                from python.ble.scanner import scan_for_devices
                from config import JK_BMS_OUI

                devices_list = await scan_for_devices()
                found_addresses = {d["address"] for d in devices_list}

                for addr in list(active_connections.keys()):
                    task = active_connections[addr]
                    if task.done() or task.cancelled():
                        del active_connections[addr]

                for device_info in devices_list:
                    addr = device_info["address"]
                    if addr in active_connections or addr not in allowed_addrs or addr in connected_addrs:
                        continue

                    log.info("Connecting to %s (%s)", device_info["name"], addr)
                    from python.ble.scanner import find_device_by_address
                    ble_device = await find_device_by_address(addr)
                    if ble_device:
                        task = asyncio.create_task(connect_and_run(ble_device, active_connections))
                        active_connections[addr] = task
                        await asyncio.sleep(3)

                await asyncio.sleep(15)

            except Exception as e:
                log.error("BLE scan error: %s", e)
                await asyncio.sleep(5)


def disconnect_device_sync(device_address):
    active_connections.pop(device_address, None)
    db.update_device_status(device_address, connected=False, enabled=False)
