"""
Discovery use case: find TP-Link devices on the local network.

Strategy:
  - UDP broadcast to port 9999 (legacy devices)
  - UDP broadcast to port 20002 (KLAP devices)
  - python-kasa Discover handles both transparently
  - Persist results to local JSON device registry
"""

import json
import logging
from pathlib import Path

from kasa import Discover

from kasa_provisioner.domain.exceptions import DiscoveryError
from kasa_provisioner.domain.models import DeviceInfo, ProtocolType

logger = logging.getLogger(__name__)

_DEFAULT_REGISTRY: Path = Path.home() / ".kasa-provisioner" / "devices.json"
_DISCOVERY_TIMEOUT: float = 5.0


class DiscoveryUseCase:
    """Discover TP-Link devices on LAN and persist to registry."""

    def __init__(
        self,
        registry_path: Path = _DEFAULT_REGISTRY,
        username: str = "",
        password: str = "",
    ) -> None:
        self._registry = registry_path
        self._username = username
        self._password = password

    async def run(self) -> list[DeviceInfo]:
        logger.info("Broadcasting discovery on LAN (timeout=%ss)...", _DISCOVERY_TIMEOUT)

        devices = await Discover.discover(
            username=self._username or None,
            password=self._password or None,
            timeout=int(_DISCOVERY_TIMEOUT),
        )

        if not devices:
            raise DiscoveryError("No TP-Link devices found on LAN")

        results: list[DeviceInfo] = []
        for host, device in devices.items():
            await device.update()
            sys_info = getattr(device, "sys_info", {}) or {}
            info = DeviceInfo(
                host=host,
                mac=device.mac,
                alias=device.alias,
                model=device.model,
                protocol=_infer_protocol(device),
                hw_version=sys_info.get("hw_ver"),
                fw_version=sys_info.get("sw_ver"),
            )
            results.append(info)
            logger.info("Found: %s (%s) at %s [%s]", info.alias, info.model, host, info.protocol)

        self._persist(results)
        return results

    def _persist(self, devices: list[DeviceInfo]) -> None:
        self._registry.parent.mkdir(parents=True, exist_ok=True)
        data = [d.model_dump() for d in devices]
        self._registry.write_text(json.dumps(data, indent=2))
        logger.info("Registry saved to %s", self._registry)


def _infer_protocol(device: object) -> ProtocolType:
    """Infer protocol type from python-kasa device protocol class name."""
    protocol_name = type(getattr(device, "protocol", None)).__name__.lower()
    if "klap" in protocol_name:
        return ProtocolType.KLAP_V1
    return ProtocolType.LEGACY
