/**
 * Renders the "Device 0 / Device 1 / ..." tab strip shared by the
 * Dashboard and Device Detail pages, and keeps the selection in
 * sessionStorage so it survives page loads (but not across browser
 * restarts by default — this is transient UI state, not a preference).
 */
(function (global) {
  const STORAGE_KEY = 'bms_selected_device';

  async function fetchDevices() {
    try {
      const resp = await fetch('/api/device-info');
      if (!resp.ok) return [];
      const data = await resp.json();
      return Array.isArray(data) ? data : [];
    } catch (e) {
      return [];
    }
  }

  function getSelected() {
    return sessionStorage.getItem(STORAGE_KEY);
  }

  function setSelected(address) {
    sessionStorage.setItem(STORAGE_KEY, address);
  }

  /**
   * opts: { containerId, onSelect(address, device), linkToDetail (bool) }
   * Returns the resolved device list and initially-selected address.
   */
  async function initDeviceTabs(opts) {
    const el = document.getElementById(opts.containerId);
    if (!el) return { devices: [], selected: null };

    const devices = await fetchDevices();

    if (devices.length === 0) {
      el.innerHTML = '<div class="device-tab-empty">No devices registered yet. Go to Devices to scan and connect.</div>';
      return { devices, selected: null };
    }

    let selected = opts.forceAddress || getSelected();
    if (!selected || !devices.find((d) => d.address === selected)) {
      const connected = devices.find((d) => d.connected);
      selected = (connected || devices[0]).address;
    }
    setSelected(selected);

    function render() {
      el.innerHTML = devices
        .map((d, i) => {
          const active = d.address === selected ? ' active' : '';
          const ledOn = d.connected ? ' on' : '';
          const label = d.name || `Device ${i}`;
          return `<div class="device-tab${active}" data-address="${d.address}">
            <span class="led${ledOn}"></span>${label}
          </div>`;
        })
        .join('');

      el.querySelectorAll('.device-tab').forEach((tabEl) => {
        tabEl.addEventListener('click', () => {
          const address = tabEl.dataset.address;
          if (address === selected) return;
          selected = address;
          setSelected(address);
          render();
          const device = devices.find((d) => d.address === address);
          if (opts.onSelect) opts.onSelect(address, device);
        });
      });
    }

    render();
    return { devices, selected };
  }

  global.BmsDeviceTabs = { initDeviceTabs, getSelected, setSelected };
})(window);
