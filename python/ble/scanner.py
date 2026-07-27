from bleak import BleakScanner
from config import JK_BMS_OUI


async def scan_for_devices():
    devices = await BleakScanner.discover()
    results = []
    for device in devices:
        if device.name and device.address.lower().startswith(tuple(JK_BMS_OUI)):
            results.append({"name": device.name, "address": device.address.lower()})
    return results


async def find_device_by_address(address):
    devices = await BleakScanner.discover()
    for device in devices:
        if device.address.lower() == address.lower():
            return device
    return None
