# JK-BMS Monitor

A lightweight Flask application for monitoring JK-BMS battery systems via Bluetooth Low Energy.

## Features

- **BLE Discovery & Connection** - Scans for JK-BMS devices (OUI `c8:47:80`), connects automatically, and reconnects on failure
- **Live Dashboard** - Real-time SOC, voltage, current, power, temperatures, cell voltages/resistances with auto-refresh
- **Historical Charts** - Chart.js graph of power and capacity data over configurable time ranges (1-30 days)
- **Device Management** - Scan, connect, disconnect, and view detailed info per device
- **Device Detail** - Full cell info (32 cells), all BMS settings, device metadata
- **Alert System** - 27 battery health rules (voltage, current, temperature, SOH, resistance, etc.) with configurable cooldown
- **Authentication** - bcrypt password protection with session-based login (default: `123456`)
- **SQLite Storage** - Persistent storage for device data, historical readings, alerts, and config

## Requirements

- Python 3.10+
- Bluetooth adapter (for BLE communication)

## Installation

```bash
cd bms-monitor
pip install -r requirements.txt
```

## Usage

```bash
python app.py
```

Open `http://localhost:5000` and log in with the default password `123456`.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session secret key | Random hex |

## Project Structure

```
bms-monitor/
├── app.py                  # Flask application + routes
├── config.py               # Configuration constants
├── error_codes.yaml        # Alert rule definitions
├── python/
│   ├── ble/
│   │   ├── protocol.py     # JK-BMS BLE protocol (commands + frame parsing)
│   │   ├── scanner.py      # BLE device discovery
│   │   ├── connector.py    # BLE notification handler
│   │   └── manager.py      # Multi-device connection manager
│   ├── db.py               # SQLite database layer
│   ├── data_store.py       # In-memory live data store
│   ├── alerts.py           # Alert evaluation engine
│   └── auth.py             # Password hashing + auth decorator
├── templates/              # Jinja2 HTML templates
└── static/                 # CSS + JavaScript
```

## JK-BMS BLE Protocol

| Constant | UUID / Value |
|----------|-------------|
| Service UUID | `0000FFE0-0000-1000-8000-00805f9b34fb` |
| Characteristic UUID | `0000FFE1-0000-1000-8000-00805f9b34fb` |
| Device Info Command | `0x97` |
| Cell Info Command | `0x96` |
| Settings Command | `0x95` |

## License

ISC
