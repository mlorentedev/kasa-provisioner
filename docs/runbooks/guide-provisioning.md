---
id: "guide-kasa-provisioning"
type: runbook
status: active
tags: [runbook, kasa-provisioner, provisioning]
created: "2026-02-24"
owner: manu
---

# Runbook: Provisioning a TP-Link Smart Plug (Air-Gapped)

## Prerequisites

- Linux host with NetworkManager (`nmcli` available)
- `kasa-provisioner` installed (`uv tool install kasa-provisioner`)
- Target WiFi SSID + WPA2 PSK at hand
- Physical access to the device (plug it in)

## Phase 1: Bootstrap (Factory AP)

### Step 1 — Power on the device

Plug the device in. LED blinks amber/orange. Wait ~5 seconds.

### Step 2 — Connect to device AP

The device creates an open WiFi AP:
- Kasa legacy: `TP-LINK_Smart Plug_XXXX`
- Newer Kasa: `Kasa_XXXX`
- Tapo: `Tapo_XXXX`

Connect manually:
```bash
nmcli dev wifi connect "TP-LINK_Smart Plug_AB12"
```

Verify device is reachable:
```bash
ping -c 1 192.168.0.1
```

### Step 3 — Inject WiFi credentials

```bash
kasa-provisioner bootstrap \
  --host 192.168.0.1 \
  --ssid "MyHomeNetwork" \
  --password "mysecretpassword"
```

Expected output: device disconnects from AP, joins LAN. CLI polls for device on LAN.

### Step 4 — Reconnect host to LAN

```bash
nmcli con up <your-previous-connection-name>
```

## Phase 2: Discover on LAN

```bash
kasa-provisioner discover
```

This broadcasts to UDP 9999 + 20002 and writes `~/.kasa-provisioner/devices.json`.

Sample output:
```
Found 2 device(s):
  192.168.1.50  HS110  legacy  ON   [My Plug]
  192.168.1.51  P110   klap   OFF  [Tapo Plug]
```

## Phase 3: Control

```bash
kasa-provisioner control --host 192.168.1.50 on
kasa-provisioner control --host 192.168.1.50 off
kasa-provisioner control --host 192.168.1.50 toggle
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `192.168.0.1` unreachable | Not connected to AP | Re-run `nmcli dev wifi connect` |
| Device not found after bootstrap | DHCP slow | Re-run `discover` after 15s |
| KLAP auth failure | Device was cloud-paired | Retry with `--username kasa@tp-link.net --password kasa` |
| XOR decode error | Firmware mismatch | Check for Tapo device using different bootstrap flow |
