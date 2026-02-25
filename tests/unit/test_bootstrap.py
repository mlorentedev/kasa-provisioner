"""Unit tests for BootstrapUseCase with mocked LegacyClient."""

from unittest.mock import AsyncMock, patch

import pytest

from kasa_provisioner.application.bootstrap import BootstrapUseCase
from kasa_provisioner.domain.exceptions import ProvisioningError
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

_MOCK_SET_WIFI_OK = {"netif": {"set_stainfo": {"err_code": 0}}}
_MOCK_SET_WIFI_FAIL = {"netif": {"set_stainfo": {"err_code": -3}}}


@pytest.fixture
def wifi() -> WifiConfig:
    return WifiConfig(ssid="TestSSID", password="testpass")


class TestBootstrapUseCase:
    @pytest.mark.asyncio
    async def test_success_returns_device_info(self, wifi: WifiConfig) -> None:
        use_case = BootstrapUseCase(ap_host="192.168.0.1")

        with (
            patch.object(use_case._client, "get_info", new=AsyncMock(return_value=_MOCK_SYSINFO)),
            patch.object(use_case._client, "set_wifi", new=AsyncMock(return_value=_MOCK_SET_WIFI_OK)),
            patch("asyncio.sleep", new=AsyncMock()),
        ):
            result = await use_case.run(wifi)

        assert result.device.model == "HS110"
        assert result.device.mac == "AA:BB:CC:DD:EE:FF"

    @pytest.mark.asyncio
    async def test_raises_on_set_wifi_error(self, wifi: WifiConfig) -> None:
        use_case = BootstrapUseCase(ap_host="192.168.0.1")

        with (
            patch.object(use_case._client, "get_info", new=AsyncMock(return_value=_MOCK_SYSINFO)),
            patch.object(use_case._client, "set_wifi", new=AsyncMock(return_value=_MOCK_SET_WIFI_FAIL)),
        ):
            with pytest.raises(ProvisioningError):
                await use_case.run(wifi)
