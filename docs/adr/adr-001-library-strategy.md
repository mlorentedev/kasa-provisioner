---
id: "ADR-001-library-strategy"
type: adr
status: accepted
date: "2026-02-24"
tags: [architecture, kasa-provisioner, protocol]
owner: manu
created: "2026-03-28"
---

# ADR-001: Protocol Library Strategy — python-kasa vs Raw Implementation

## Context

We need to communicate with TP-Link smart plugs using two distinct protocols:
- **Legacy (XOR/TCP):** Simple, well-documented, used for bootstrap provisioning AP phase and older devices
- **KLAP:** Two-stage handshake, AES-CBC session encryption, required for devices on firmware 2021+

The question is whether to implement these protocols from scratch or leverage an existing library.

## Options Considered

1. **Full raw implementation**
   - *Pros:* Zero dependencies, complete control, no supply-chain risk
   - *Cons:* Reimplementing ~2000 lines of already-battle-tested crypto/transport code; KLAP v1/v2 differences are subtle (seed ordering, hash function) and error-prone

2. **python-kasa as protocol abstraction layer**
   - *Pros:* Actively maintained (TP-Link devices frequently change firmware); handles both XOR + KLAP v1/v2; includes discovery, credential fallback, all device commands; community-reverse-engineered and validated
   - *Cons:* External dependency; abstracts protocol details (harder to fine-tune)

3. **Hybrid: raw XOR for bootstrap, python-kasa for post-LAN control**
   - *Pros:* Full control over bootstrap AP phase (where python-kasa may assume device is already on LAN); use python-kasa only where it adds value
   - *Cons:* Two paradigms to maintain

## Decision

**Option 3 (Hybrid)** is chosen.

- **Bootstrap phase (AP):** Custom `LegacyClient` implementing XOR codec + TCP framing directly. Rationale: the bootstrap flow requires direct IP targeting of `192.168.0.1`, manual WiFi interface management, and python-kasa's discovery assumes a reachable LAN. A minimal raw client is ~80 lines and is well-documented.
- **Post-provisioning phase (LAN):** Use `python-kasa` via its `DeviceConfig` API for protocol-agnostic control. This handles KLAP v1/v2/legacy transparently.

## Consequences

- **Positive:** Avoid reimplementing KLAP crypto; bootstrap phase remains under full control; python-kasa update cycle keeps us compatible with new firmware.
- **Negative:** python-kasa is an external dependency. Pin to a specific minor version. Monitor for breaking API changes.

## References

- https://github.com/python-kasa/python-kasa
- https://www.softscheck.com/en/blog/tp-link-reverse-engineering/ (Legacy XOR protocol)
- https://python-kasa.readthedocs.io/en/stable/_modules/kasa/transports/klaptransport.html
