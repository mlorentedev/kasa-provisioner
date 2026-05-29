---
id: "ADR-002-wifi-management"
type: adr
status: accepted
date: "2026-02-24"
tags: [architecture, kasa-provisioner, networking]
owner: manu
created: "2026-03-28"
---

# ADR-002: WiFi Interface Management — nmcli vs wpa_supplicant vs Manual

## Context

Bootstrap provisioning requires the host machine to temporarily join the device's factory AP (open, unauthenticated, SSID `TP-LINK_XXXX`), send provisioning commands, then restore the original network connection. This WiFi switching must be programmatic.

## Options Considered

1. **nmcli (NetworkManager CLI)**
   - *Pros:* Standard on all major Linux distros; handles connect/disconnect/restore cleanly; does not require root (if user is in `netdev` group); JSON output; AP scan support
   - *Cons:* Only Linux; requires NetworkManager to be running

2. **wpa_supplicant + iw directly**
   - *Pros:* Lower-level, works without NetworkManager
   - *Cons:* Requires root; complex state management; no clean restore mechanism

3. **pywifi**
   - *Pros:* Python-native; cross-platform (Windows/Linux/macOS); active maintenance
   - *Cons:* Requires native WiFi drivers; less battle-tested than nmcli

4. **User-managed (document only, no automation)**
   - *Pros:* Simplest code; no WiFi dependency in Phase 1
   - *Cons:* Manual friction defeats the "headless" goal

## Decision

**pywifi** for Phase 3 (WiFi automation). Phase 1 MVP assumes the operator connects manually, with CLI instructions provided.

Rationale:
- **Cross-platform requirement confirmed**: tool must run on Windows and Linux (Poetry used for portability)
- `pywifi` abstracts WiFi management across both OSes — `nmcli` is Linux-only
- Phase 1 MVP avoids this complexity by separating concerns: the operator connects to the AP, then runs `kasa-provisioner bootstrap`

## AP SSID Patterns

| Generation | SSID Pattern              |
|------------|---------------------------|
| Legacy Kasa| `TP-LINK_Smart Plug_XXXX` |
| Newer Kasa | `Kasa_XXXX`               |
| Tapo       | `Tapo_XXXX`               |

Where `XXXX` = last 4 hex digits of MAC address.

## Consequences

- **Positive:** Clean separation — Phase 1 is OS-independent; Phase 3 adds nmcli without breaking existing code
- **Negative:** Phase 1 requires manual WiFi switch; not fully hands-free until Phase 3

## References

- `man nmcli` — connect: `nmcli dev wifi connect <SSID>`
- `nmcli con show --active` — restore after provisioning
