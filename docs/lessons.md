---
id: "kasa-provisioner-lessons"
type: project
status: active
tags: [lessons, kasa-provisioner, debugging]
created: "2026-02-24"
owner: manu
---

# kasa-provisioner: Lessons Learned

---

## L-001: python-kasa 0.9 — `hw_version` attribute removed

**Date:** 2026-02-24
**Symptom:** `AttributeError: Device has no attribute 'hw_version'` in `DiscoveryUseCase`
**Root Cause:** python-kasa 0.9 removed the `hw_version` property from the `Device` base class. The `__getattr__` explicitly raises `AttributeError` instead of returning `None`, so `getattr(device, 'hw_version', None)` is safe but `device.hw_version` is not.
**Fix:** Access hardware/firmware version from the raw sysinfo dict:
```python
sys_info = getattr(device, "sys_info", {}) or {}
hw_version = sys_info.get("hw_ver")
fw_version = sys_info.get("sw_ver")
```
**Generalization:** When using python-kasa, prefer `device.sys_info.get(key)` over named properties for metadata — the API surface changes across minor versions.

---

## L-002: `StrEnum` as `typer.Argument` breaks Click's `make_metavar()`

**Date:** 2026-02-24
**Symptom:** `TypeError: TyperArgument.make_metavar() takes 1 positional argument but 2 were given`
**Root Cause:** Typer ≥ 0.12 + Click ≥ 8.1 cannot correctly handle `StrEnum` (which inherits from both `str` and `Enum`) when used as a `typer.Argument` type. The `StrEnum.__str__` returning the value confuses Click's enum choice validation.
**Fix:** Use `str` in the CLI signature and convert to enum manually:
```python
command: Annotated[str, typer.Argument(help="on | off | toggle")]
# then:
cmd = PowerCommand(command)  # raises ValueError with clear message on invalid input
```
**Generalization:** Never use `StrEnum` directly as a Typer Argument type. Use `str` + explicit conversion. `typer.Option` with `StrEnum` has similar issues with default values.

---

## L-003: Raw TCP LegacyClient times out — use python-kasa Device.connect() for LAN control

**Date:** 2026-02-24
**Symptom:** `ProvisioningError: Read timeout from 10.0.0.167` when using our raw `LegacyClient` for control on a device already discovered by python-kasa.
**Root Cause:** Unknown (possible: device rate-limits sequential connections, or subtle frame timing difference). python-kasa's `XorTransport` handles retries and connection state correctly.
**Fix:** Use `Device.connect(config=DeviceConfig(host=...))` for all post-provisioning LAN control. `LegacyClient` is reserved exclusively for the bootstrap AP phase (192.168.0.1), where python-kasa's discovery logic cannot be used.
**Architecture implication:** ADR-001 (Hybrid) is correct — raw client for AP bootstrap only, python-kasa for everything else.

---

## L-008: Bootstrap AP provisioning requires UDP (no 4-byte header) — NOT TCP

**Date:** 2026-02-24
**Root Cause (confirmed):** The Kasa mobile app uses **UDP port 9999** for AP-mode provisioning. UDP XOR frames have **no 4-byte length header**. Our `LegacyClient` sends TCP frames WITH the 4-byte header — the EP10 receives the TCP connection but silently ignores the command.
**Protocol difference:**

| | TCP (our LegacyClient) | UDP (Kasa app) |
|---|---|---|
| 4-byte length header | YES | **NO** |
| Transport | TCP | **UDP** |
| Discovery | direct | UDP broadcast to 255.255.255.255 |

**Source confirmed in python-kasa `discover.py`:**
```python
encrypted_req = XorEncryption.encrypt(req)   # returns 4-byte header + payload
self.transport.sendto(encrypted_req[4:], ...)  # strips 4-byte header for UDP
```
**Fix:** Add UDP support to `LegacyClient` for AP-mode bootstrap. The `set_stainfo` command must be sent as a UDP datagram to `192.168.0.1:9999` with raw XOR payload (no length prefix).
**Additional fallback:** Some devices use `smartlife.iot.common.softaponboarding` namespace instead of `netif`. Try both.
**Workaround:** Use Kasa mobile app for initial provisioning, then use kasa-provisioner for all LAN control.

---

## L-006: EP10 AP mode closes TCP after receiving `set_stainfo` — no ACK, command format confirmed correct

**Date:** 2026-02-24
**Symptom:** After sending `set_stainfo` via XOR TCP to 192.168.0.1:9999, device closes connection without sending any response bytes. AP stays up — device never joins home WiFi.
**Diagnostics confirmed:**
- Port 9999 is open ✓
- TCP connection established ✓
- Device receives frame and closes cleanly (not RST) ✓
- Command format `{"netif": {"set_stainfo": {"ssid": "...", "password": "...", "key_type": 3}}}` is correct per all sources ✓
- XOR cipher (key=0xAB, autokey) and 4-byte big-endian length header are correct ✓
- AP never disappears after command = device not processing set_stainfo ✗
**Root Cause:** Likely EP10 FW 1.0.5 WiFi state machine bug. TP-Link community forum documents that FW 1.0.5 has known WiFi join issues. FW 1.0.6 (not public) fixes it.
**Workaround options:**
1. Use `kasa --host 192.168.0.1 wifi join "SSID" --password "PASS" --keytype 3` (python-kasa CLI)
2. Request FW 1.0.6 from TP-Link support (provide device MAC: 3C:52:A1:D1:B0:27)
3. Provision via Kasa mobile app, then use kasa-provisioner for LAN control
**Code impact:** `LegacyClient.send()` correctly returns `{}` on empty `IncompleteReadError`. `_assert_success({})` correctly passes (no err_code = assume sent). The code is correct; this is a firmware limitation.

---

## L-007: EP10 FW 1.0.5 — known WiFi provisioning bug, FW 1.0.6 required

**Date:** 2026-02-24
**Source:** TP-Link community forum (community.tp-link.com/us/smart-home/forum/topic/618822)
**Confirmed:** Multiple users report EP10 devices on FW 1.0.5 fail to join new WiFi even after factory reset. Device accepts `set_stainfo` command but WiFi state machine has a race condition/bug that prevents execution of the network switch.
**Resolution:** TP-Link released FW 1.0.6 as a beta/private fix (not on the public download page). Contact TP-Link support with device MAC to obtain it.
**Alternative:** Mobile app provisioning succeeds despite this bug because it uses a slightly different retry sequence (likely sends set_stainfo multiple times).

---

## L-005: Typer 0.12 breaks with Click ≥ 8.2.0 — `make_metavar()` signature change

**Date:** 2026-02-24
**Symptom:** `TypeError: Parameter.make_metavar() missing 1 required positional argument: 'ctx'` when running any `--help` in a Typer 0.12.x app.
**Root Cause:** Click 8.2.0 changed `Option.make_metavar()` to require a `ctx: Context` parameter. Typer 0.12.5's `rich_utils.py` still calls it with no arguments: `metavar_str = param.make_metavar()`.
**Fix:** Pin click below 8.2.0 in pyproject.toml:
```toml
click = ">=8.0.0,<8.2.0"
```
Then run `poetry update click` to downgrade to 8.1.8.
**Generalization:** When using Typer, always check the minimum/maximum compatible Click version. Typer 0.12.x is only compatible with Click 8.0–8.1.x.

---

## L-004: EP10 HW 1.0 FW 1.0.5 — confirmed legacy XOR, no auth required

**Date:** 2026-02-24
**Confirmed:** EP10 at firmware 1.0.5 uses `IOT.XOR` transport (port 9999), no credentials needed.
**Key sysinfo fields:**
- `relay_state`: int (1=ON, 0=OFF) — NOT `device_on` (that's KLAP)
- `mic_type`: `IOT.SMARTPLUGSWITCH`
- `sw_ver`: `1.0.5 Build 221021 Rel.183404`
- `hw_ver`: `1.0`
