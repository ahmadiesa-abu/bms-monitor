import asyncio
from copy import deepcopy
from datetime import datetime


class DataStore:
    def __init__(self):
        self.cell_info = {}
        self.setting_info = {}
        self.last_cell_info_update = {}
        self.response_buffers = {}
        self.lock = asyncio.Lock()

    async def delete_device_data(self, device_name):
        async with self.lock:
            self.cell_info.pop(device_name, None)
            self.last_cell_info_update.pop(device_name, None)
            self.response_buffers.pop(device_name, None)

    async def update_last_cell_info_update(self, device_name):
        async with self.lock:
            self.last_cell_info_update[device_name] = datetime.now()

    async def get_last_cell_info_update(self, device_name):
        async with self.lock:
            return self.last_cell_info_update.get(device_name)

    async def append_to_buffer(self, device_name, data):
        async with self.lock:
            if device_name not in self.response_buffers:
                self.response_buffers[device_name] = bytearray()
            self.response_buffers[device_name].extend(data)

    async def get_buffer(self, device_name):
        async with self.lock:
            return self.response_buffers.get(device_name, bytearray())

    async def get_buffer_snapshot(self, device_name):
        async with self.lock:
            buf = self.response_buffers.get(device_name)
            return bytes(buf) if buf else bytearray()

    async def clear_buffer(self, device_name):
        async with self.lock:
            buf = self.response_buffers.get(device_name)
            if buf:
                buf.clear()

    async def update_cell_info(self, device_name, info):
        async with self.lock:
            self.cell_info[device_name] = info

    async def get_cell_info(self):
        async with self.lock:
            return deepcopy(self.cell_info)

    async def update_setting_info(self, device_address, info):
        async with self.lock:
            self.setting_info[device_address] = info

    async def get_setting_info(self):
        async with self.lock:
            return deepcopy(self.setting_info)

    async def get_setting_info_by_address(self, device_address):
        async with self.lock:
            return deepcopy(self.setting_info.get(device_address))


data_store = DataStore()
