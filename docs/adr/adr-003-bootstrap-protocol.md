---
id: "ADR-003-bootstrap-protocol"
type: adr
status: accepted
date: "2026-02-24"
tags: [architecture, kasa-provisioner, protocol, provisioning]
owner: manu
created: "2026-03-28"
---

# ADR-003: Bootstrap Protocol — Legacy XOR for AP Phase

## Context

When a TP-Link device is in factory state (no WiFi configured), it broadcasts an open AP and listens on `192.168.0.1`. The question is which protocol is active during this AP phase and how to inject WiFi credentials.

## Findings from Reverse Engineering

**Regardless of firmware generation**, devices in AP bootstrap mode expose **only the legacy XOR/TCP protocol on port 9999**. Even Tapo devices (which use KLAP post-provisioning) use the legacy protocol during the factory AP phase.

Key command to inject WiFi credentials:
```json
{"netif": {"set_stainfo": {"ssid": "<SSID>", "password": "<PSK>", "key_type": 3}}}
```

Where `key_type`:
- `0` = Open (no security)
- `3` = WPA2-PSK

The XOR (autokey) cipher:
```
key = 0xAB (171)
for each byte b in plaintext:
    ciphertext_byte = b XOR key
    key = b  # autokey: next key = current plaintext byte
```

Prepend 4-byte big-endian length before the XOR-encoded payload.

## Decision

The `LegacyClient` handles **all bootstrap provisioning** regardless of target device generation. Post-provisioning, protocol detection switches to the discovery-based approach (port 9999 vs 20002).

## KLAP Credential Strategy (Post-Bootstrap)

| Device State             | Credentials to Try               |
|--------------------------|----------------------------------|
| Never connected to cloud | Blank: `""` + `""`              |
| Previously cloud-paired  | `kasa@tp-link.net` + `kasa`      |
| User-managed             | Configured username + password   |

Fallback chain: blank → default → user-provided (in that order).

## Failure Modes

1. **Race condition on AP leave:** After `set_stainfo`, device disconnects from AP immediately. Allow 500ms before attempting LAN discovery.
2. **DHCP timing:** Device joining LAN may take 3-10 seconds to get IP. Use polling with backoff.
3. **SSID/password encoding:** Non-ASCII characters in SSID/PSK must be UTF-8 encoded in the JSON payload.

## References

- https://www.softscheck.com/en/blog/tp-link-reverse-engineering/
- python-kasa issue #565: Tapo provisioning
- `kasa/transports/klaptransport.py` — KLAP auth_hash derivation
