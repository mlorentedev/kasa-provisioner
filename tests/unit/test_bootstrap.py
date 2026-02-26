"""Unit tests for BootstrapUseCase with mocked LegacyClient."""

from unittest.mock import AsyncMock, patch

from kasa_provisioner.application.bootstrap import BootstrapUseCase
from kasa_provisioner.domain.models import WifiConfig

_MOCK_SYSINFO = {
    "system": {
        "get_sysinfo": {
            "model": "HS110",
            "mac": "AA:BB:CC:DD:EE:FF",
            "alias": "My Plug",
            "hw_ver": "2.0",
            "sw_ver": "1.2.3",
        }
    }
}


def _wifi() -> WifiConfig:
    return WifiConfig(ssid="TestSSID", password="testpass")


class TestBootstrapUseCase:
    async def test_success_returns_device_info(self) -> None:
        use_case = BootstrapUseCase(ap_host="192.168.0.1")

        with (
            patch.object(use_case._client, "get_info", new=AsyncMock(return_value=_MOCK_SYSINFO)),
            patch.object(use_case._client, "set_wifi_udp", new=AsyncMock()),
            patch("asyncio.sleep", new=AsyncMock()),
        ):
            result = await use_case.run(_wifi())

        assert result.device.model == "HS110"
        assert result.device.mac == "AA:BB:CC:DD:EE:FF"

    async def test_success_with_empty_sysinfo(self) -> None:
        """AP mode: device returns {} for get_info — bootstrap still works."""
        use_case = BootstrapUseCase(ap_host="192.168.0.1")

        with (
            patch.object(use_case._client, "get_info", new=AsyncMock(return_value={})),
            patch.object(use_case._client, "set_wifi_udp", new=AsyncMock()),
            patch("asyncio.sleep", new=AsyncMock()),
        ):
            result = await use_case.run(_wifi())

        assert result.device.model is None
        assert result.device.host == "192.168.0.1"
        assert "TestSSID" in result.message

    async def test_set_wifi_udp_called_with_correct_args(self) -> None:
        use_case = BootstrapUseCase(ap_host="192.168.0.1")
        mock_udp = AsyncMock()

        with (
            patch.object(use_case._client, "get_info", new=AsyncMock(return_value={})),
            patch.object(use_case._client, "set_wifi_udp", new=mock_udp),
            patch("asyncio.sleep", new=AsyncMock()),
        ):
            await use_case.run(_wifi())

        mock_udp.assert_called_once_with(ssid="TestSSID", password="testpass", key_type=3)
