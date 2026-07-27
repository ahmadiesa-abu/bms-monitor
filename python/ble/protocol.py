from config import (
    CMD_HEADER, CMD_TYPE_DEVICE_INFO, CMD_TYPE_CELL_INFO, CMD_TYPE_SETTINGS,
    MIN_FRAME_SIZE, MAX_FRAME_SIZE,
)


def calculate_crc(data):
    return sum(data) % 256


def create_command(command_type):
    frame = bytearray(20)
    frame[:4] = CMD_HEADER
    frame[4] = command_type
    frame[19] = calculate_crc(frame[:19])
    return bytes(frame)


def parse_device_info(data, device_address):
    return {
        "frame_type": data[4],
        "frame_counter": data[5],
        "vendor_id": data[6:22].split(b'\x00', 1)[0].decode('utf-8', errors='ignore'),
        "hardware_version": data[22:30].split(b'\x00', 1)[0].decode('utf-8', errors='ignore'),
        "software_version": data[30:38].split(b'\x00', 1)[0].decode('utf-8', errors='ignore'),
        "device_uptime": int.from_bytes(data[38:42], byteorder='little'),
        "power_on_count": int.from_bytes(data[42:46], byteorder='little'),
        "device_name": data[46:62].split(b'\x00', 1)[0].decode('utf-8', errors='ignore'),
        "device_address": device_address,
        "manufacturing_date": data[78:86].split(b'\x00', 1)[0].decode('utf-8', errors='ignore'),
        "serial_number": data[86:97].split(b'\x00', 1)[0].decode('utf-8', errors='ignore'),
        "user_data": data[102:118].split(b'\x00', 1)[0].decode('utf-8', errors='ignore'),
    }


def parse_cell_info(data, device_address):
    cell_voltages = []
    for i in range(32):
        voltage = int.from_bytes(data[6 + i * 2:8 + i * 2], byteorder='little') * 0.001
        cell_voltages.append(voltage)

    cell_resistances = []
    for i in range(32):
        resistance = int.from_bytes(data[80 + i * 2:82 + i * 2], byteorder='little') * 0.001
        cell_resistances.append(resistance)

    filtered_voltages = [v for v in cell_voltages if v > 0]
    filtered_resistances = [r for r in cell_resistances if r > 0]

    power_tube_temp = int.from_bytes(data[144:146], byteorder='little', signed=True) * 0.1
    battery_voltage = int.from_bytes(data[150:154], byteorder='little', signed=True) * 0.001
    battery_power = int.from_bytes(data[154:158], byteorder='little', signed=True) * 0.001
    charge_current = int.from_bytes(data[158:162], byteorder='little', signed=True) * 0.001
    temperature_sensor_1 = int.from_bytes(data[162:164], byteorder='little', signed=True) * 0.1
    temperature_sensor_2 = int.from_bytes(data[164:166], byteorder='little', signed=True) * 0.1

    state_of_charge = data[173]
    remaining_capacity = int.from_bytes(data[174:178], byteorder='little') * 0.001
    nominal_capacity = int.from_bytes(data[178:182], byteorder='little') * 0.001
    cycle_count = int.from_bytes(data[182:186], byteorder='little')
    total_cycle_capacity = int.from_bytes(data[186:189], byteorder='little') * 0.001
    state_of_health = data[190]
    charging_status = data[198]
    discharging_status = data[199]
    precharging_status = data[200]

    temperature_sensor_5 = int.from_bytes(data[254:256], byteorder='little', signed=True) * 0.1
    temperature_sensor_4 = int.from_bytes(data[256:258], byteorder='little', signed=True) * 0.1
    temperature_sensor_3 = int.from_bytes(data[258:260], byteorder='little', signed=True) * 0.1
    emergency_time_countdown = int.from_bytes(data[218:219], byteorder='little')

    average_voltage = sum(filtered_voltages) / len(filtered_voltages) if filtered_voltages else 0
    voltage_diff = (max(filtered_voltages) - min(filtered_voltages)) if len(filtered_voltages) > 1 else 0

    return {
        "device_address": device_address.lower(),
        "charging_status": charging_status,
        "discharging_status": discharging_status,
        "precharging_status": precharging_status,
        "voltage_difference": voltage_diff,
        "average_voltage": average_voltage,
        "cell_voltages": filtered_voltages,
        "cell_resistances": filtered_resistances,
        "power_tube_temperature": power_tube_temp,
        "battery_voltage": battery_voltage,
        "battery_power": battery_power,
        "charge_current": charge_current,
        "temperature_sensor_1": temperature_sensor_1,
        "temperature_sensor_2": temperature_sensor_2,
        "temperature_sensor_3": temperature_sensor_3,
        "temperature_sensor_4": temperature_sensor_4,
        "temperature_sensor_5": temperature_sensor_5,
        "state_of_charge": state_of_charge,
        "remaining_capacity": remaining_capacity,
        "nominal_capacity": nominal_capacity,
        "cycle_count": cycle_count,
        "total_cycle_capacity": total_cycle_capacity,
        "state_of_health": state_of_health,
        "emergency_time_countdown": emergency_time_countdown,
    }


def parse_setting_info(data, device_address, device_name):
    bitmask = int.from_bytes(data[282:284], "little")

    return {
        "name": device_name,
        "address": device_address,
        "cell_count": data[114],
        "nominal_battery_capacity": int.from_bytes(data[130:134], "little") * 0.001,
        "balance_trigger_voltage": int.from_bytes(data[26:30], "little") * 0.001,
        "start_balance_voltage": int.from_bytes(data[138:142], "little") * 0.001,
        "max_balance_current": int.from_bytes(data[78:82], "little") * 0.001,
        "cell_ovp": int.from_bytes(data[18:22], "little") * 0.001,
        "cell_request_charge_voltage": int.from_bytes(data[38:42], "little") * 0.001,
        "soc_100_voltage": int.from_bytes(data[30:34], "little") * 0.001,
        "cell_ovpr": int.from_bytes(data[22:26], "little") * 0.001,
        "cell_uvpr": int.from_bytes(data[14:18], "little") * 0.001,
        "soc_0_voltage": int.from_bytes(data[34:38], "little") * 0.001,
        "cell_uvp": int.from_bytes(data[10:14], "little") * 0.001,
        "power_off_voltage": int.from_bytes(data[46:50], "little") * 0.001,
        "cell_request_float_voltage": int.from_bytes(data[42:46], "little") * 0.001,
        "smart_sleep_voltage": int.from_bytes(data[6:10], "little") * 0.001,
        "max_charge_current": int.from_bytes(data[50:54], "little") * 0.001,
        "charge_ocp_delay": int.from_bytes(data[54:58], "little"),
        "charge_ocp_recovery": int.from_bytes(data[58:62], "little"),
        "max_discharge_current": int.from_bytes(data[62:66], "little") * 0.001,
        "discharge_ocp_delay": int.from_bytes(data[66:70], "little"),
        "discharge_ocp_recovery": int.from_bytes(data[70:74], "little"),
        "charge_otp": int.from_bytes(data[82:86], "little") * 0.1,
        "charge_otp_recovery": int.from_bytes(data[86:90], "little") * 0.1,
        "discharge_otp": int.from_bytes(data[90:94], "little") * 0.1,
        "discharge_otp_recovery": int.from_bytes(data[94:98], "little") * 0.1,
        "charge_utp": int.from_bytes(data[98:102], "little", signed=True) * 0.1,
        "charge_utp_recovery": int.from_bytes(data[102:106], "little", signed=True) * 0.1,
        "mos_otp": int.from_bytes(data[106:110], "little", signed=True) * 0.1,
        "mos_otp_recovery": int.from_bytes(data[110:114], "little", signed=True) * 0.1,
        "short_circuit_protection_delay": int.from_bytes(data[134:138], "little"),
        "short_circuit_protection_recovery": int.from_bytes(data[74:78], "little"),
        "connection_wire_resistances": [
            int.from_bytes(data[i:i + 4], "little") * 0.001
            for i in range(142, 270, 4)
        ],
        "charge_switch": bool(data[118]),
        "discharge_switch": bool(data[122]),
        "balancer_switch": bool(data[126]),
        "heating_enabled": bool(bitmask & 0b0000000000000001),
        "disable_temperature_sensors": bool(bitmask & 0b0000000000000010),
        "gps_heartbeat": bool(bitmask & 0b0000000000000100),
        "port_switch": "RS485" if bitmask & 0b0000000000001000 else "CAN",
        "display_always_on": bool(bitmask & 0b0000000000010000),
        "special_charger": bool(bitmask & 0b0000000000100000),
        "smart_sleep_enabled": bool(bitmask & 0b0000000001000000),
        "disable_pcl_module": bool(bitmask & 0b0000000010000000),
        "timed_stored_data": bool(bitmask & 0b0000000100000000),
        "charging_float_mode": bool(bitmask & 0b0000001000000000),
        "controls_bitmask": bitmask,
    }
