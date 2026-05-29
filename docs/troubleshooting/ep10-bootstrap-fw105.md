---
id: "ep10-bootstrap-fw105"
type: troubleshooting
status: active
tags: [ep10, bootstrap, firmware, udp, kasa-provisioner]
created: "2026-02-24"
updated: "2026-02-24"
owner: manu
---

# EP10 Bootstrap Fails — AP Mode Requires UDP, Not TCP

## Symptoms

- `kasa-provisioner bootstrap` reports `✓` (command sent)
- AP (`TP-LINK_Smart Plug_XXXX`) **never disappears** after bootstrap
- Device does not appear on home LAN after running discover
- Mobile app provisioning **works** on same device and network

## Root Cause (Confirmed)

**The Kasa mobile app uses UDP for AP-mode provisioning, not TCP.**

UDP XOR frames have **no 4-byte length header**. `LegacyClient.send()` uses TCP with the 4-byte header — the EP10 accepts the TCP connection but **silently ignores the frame** (likely because it only processes the UDP endpoint in AP mode).

### Protocol Comparison

| Aspect | Kasa Mobile App (AP provisioning) | Our LegacyClient |
|--------|----------------------------------|------------------|
| Transport | **UDP port 9999** | TCP port 9999 |
| 4-byte length header | **NO** | YES |
| Discovery | UDP broadcast to `255.255.255.255:9999` | Direct connect |
| `set_stainfo` delivery | UDP unicast to `192.168.0.1:9999` | TCP with header |
| XOR cipher (key=0xAB) | Same | Same |
| JSON payload | Same | Same |

### python-kasa source confirms header stripping for UDP

From `kasa/discover.py`:
```python
encrypted_req = XorEncryption.encrypt(req)   # returns: [4-byte header][XOR payload]
self.transport.sendto(encrypted_req[4:], self.target_1)  # strips header for UDP!
```

## Confirmed Non-Issues

| Check | Result |
|-------|--------|
| Port 9999 open (TCP) | ✓ Yes |
| XOR cipher correct (key=0xAB, autokey) | ✓ Confirmed |
| Command format `{"netif":{"set_stainfo":{...}}}` | ✓ Confirmed |
| Field name `"password"` (not `"key"`) | ✓ Correct |
| `key_type: 3` for WPA2 | ✓ Correct |
| Router WPA2 (not WPA3) | ✓ WPA2 |
| Password correct (mobile app connects) | ✓ Confirmed |

## Fix Plan (T-022)

Modify `LegacyClient` to send `set_stainfo` via UDP (no 4-byte header):

```python
async def set_wifi_udp(self, ssid: str, password: str, key_type: int = 3) -> None:
    """Send set_stainfo via UDP — required for AP-mode bootstrap."""
    payload = json.dumps(
        {"netif": {"set_stainfo": {"ssid": ssid, "password": password, "key_type": key_type}}}
    ).encode()
    encoded = _xor_encode(payload)  # NO length header for UDP

    loop = asyncio.get_event_loop()
    transport, _ = await loop.create_datagram_endpoint(
        asyncio.DatagramProtocol,
        remote_addr=(self.host, self._port),
    )
    transport.sendto(encoded)
    transport.close()
```

Also add fallback namespace `smartlife.iot.common.softaponboarding` for newer devices.

## Current Workaround

Use Kasa mobile app for initial provisioning, then use kasa-provisioner for all LAN control operations (`discover`, `control`, `status`) — these work perfectly.

## Device Info

```
Model:    EP10(US)
HW:       1.0
FW:       1.0.5 Build 221021 Rel.183404
MAC:      3C:52:A1:D1:B0:27
AP SSID:  TP-LINK_Smart Plug_B027
Protocol: IOT.XOR (legacy, port 9999)
```
