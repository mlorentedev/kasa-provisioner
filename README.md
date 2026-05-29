# kasa-provisioner

Offline provisioning and local control of TP-Link Kasa/Tapo smart plugs — zero cloud dependency.

## Features

- **`bootstrap`** — provision a factory-fresh device from its AP to a target WiFi network
- **`discover`** — find TP-Link devices on LAN and save a local device registry
- **`control`** — toggle power (on/off/toggle) by IP
- **`status`** — read current power state and uptime

Supports legacy (XOR/port 9999) and KLAP (v1/v2) devices.

## Install

```bash
poetry install
```

## Usage

```bash
# Provision a factory-fresh device (connect to TP-LINK_* AP first)
kasa-provisioner bootstrap --ssid MyNetwork --password mypassword

# Discover devices on LAN
kasa-provisioner discover

# Control a device
kasa-provisioner control 10.0.0.167 on
kasa-provisioner control 10.0.0.167 off
kasa-provisioner control 10.0.0.167 toggle

# Read current state
kasa-provisioner status 10.0.0.167

# KLAP devices require credentials
kasa-provisioner control 10.0.0.167 on --protocol klap_v2 --username user@example.com --password secret
```

## Tested devices

| Device | HW | FW | Protocol | Status |
|--------|----|----|----------|--------|
| EP10(US) | 1.0 | 1.0.5 | Legacy XOR | ✅ LAN control |

## Development

```bash
poetry run pytest          # run tests
poetry run ruff check .    # lint
poetry run mypy src        # type check
```

## Documentation

Project-bound knowledge lives in [`docs/`](docs/) (docs-as-code): ADRs, runbooks, troubleshooting, and lessons.
