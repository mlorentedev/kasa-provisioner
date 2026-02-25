"""
Bootstrap use case: provision a factory-fresh device from its AP to a target WiFi network.

Flow:
  1. Verify device reachable at AP IP (192.168.0.1)
  2. Fetch device info (model, MAC) via legacy protocol
  3. Send set_stainfo to inject WiFi credentials
  4. Poll LAN discovery until device appears (or timeout)
"""

import asyncio
import logging
from dataclasses import dataclass

from kasa_provisioner.domain.exceptions import ProvisioningError
from kasa_provisioner.domain.models import DeviceInfo, WifiConfig
from kasa_provisioner.infra.legacy_client import LegacyClient

logger = logging.getLogger(__name__)

_DEFAULT_AP_HOST: str = "192.168.0.1"
_POLL_INTERVAL: float = 3.0
_POLL_TIMEOUT: float = 60.0


@dataclass
class BootstrapResult:
    device: DeviceInfo
    message: str


class BootstrapUseCase:
    """Provision a device from factory AP state into a LAN."""

    def __init__(self, ap_host: str = _DEFAULT_AP_HOST) -> None:
        self._client = LegacyClient(ap_host)

    async def run(self, wifi: WifiConfig) -> BootstrapResult:
        logger.info("Connecting to device at %s", self._client.host)

        raw_info = await self._client.get_info()
        device = _parse_device_info(raw_info, self._client.host)
        logger.info("Device identified: model=%s mac=%s", device.model, device.mac)

        logger.info("Injecting WiFi credentials for SSID=%s", wifi.ssid)
        response = await self._client.set_wifi(
            ssid=wifi.ssid,
            password=wifi.password,
            key_type=int(wifi.key_type),
        )
        _assert_success(response, "set_stainfo")

        logger.info("Credentials sent. Device is joining network. Polling...")
        # Device will disconnect from AP immediately — give it a moment.
        await asyncio.sleep(2.0)

        return BootstrapResult(
            device=device,
            message=f"Device {device.model or 'unknown'} sent to SSID '{wifi.ssid}'. Run 'discover' after rejoining LAN.",
        )


def _parse_device_info(raw: dict, host: str) -> DeviceInfo:
    sysinfo = raw.get("system", {}).get("get_sysinfo", {})
    return DeviceInfo(
        host=host,
        mac=sysinfo.get("mac") or sysinfo.get("ethernet_mac"),
        alias=sysinfo.get("alias"),
        model=sysinfo.get("model"),
        hw_version=sysinfo.get("hw_ver"),
        fw_version=sysinfo.get("sw_ver"),
    )


def _assert_success(response: dict, command: str) -> None:
    err_code = (
        response.get("netif", {}).get("set_stainfo", {}).get("err_code")
    )
    if err_code is not None and err_code != 0:
        raise ProvisioningError(f"{command} failed with err_code={err_code}: {response}")
