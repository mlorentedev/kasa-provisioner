"""
Control use case: toggle power state on a provisioned device.

For legacy devices: LegacyClient.set_power()
For KLAP devices: python-kasa SmartDevice with credential fallback chain.

Credential fallback order:
  1. Blank credentials (device never cloud-paired)
  2. kasa@tp-link.net / kasa (TP-Link default, found in APK)
  3. User-provided credentials
"""

import logging
from dataclasses import dataclass

from kasa import Credentials, Device, DeviceConfig
from kasa.exceptions import AuthenticationError as KasaAuthError

from kasa_provisioner.domain.exceptions import AuthenticationError
from kasa_provisioner.domain.models import DeviceState, PowerCommand, ProtocolType

logger = logging.getLogger(__name__)

_KLAP_CREDENTIAL_CHAIN: list[tuple[str, str]] = [
    ("", ""),                      # Never cloud-paired
    ("kasa@tp-link.net", "kasa"),  # TP-Link APK default
]


@dataclass
class ControlResult:
    host: str
    previous_state: DeviceState
    new_state: DeviceState


@dataclass
class StatusResult:
    host: str
    state: DeviceState
    on_time_secs: int | None = None


class ControlUseCase:
    """Execute a power command on a device by host IP."""

    def __init__(
        self,
        host: str,
        protocol: ProtocolType = ProtocolType.LEGACY,
        username: str = "",
        password: str = "",
    ) -> None:
        self._host = host
        self._protocol = protocol
        self._username = username
        self._password = password

    async def run(self, command: PowerCommand) -> ControlResult:
        # Legacy devices (port 9999 / XorTransport) work without credentials.
        # KLAP devices need the fallback credential chain.
        credential_chain: list[tuple[str, str]] = (
            [("", "")]
            if self._protocol == ProtocolType.LEGACY
            else list(_KLAP_CREDENTIAL_CHAIN) + (
                [(self._username, self._password)] if self._username else []
            )
        )

        for username, password in credential_chain:
            try:
                device = await Device.connect(
                    config=DeviceConfig(
                        host=self._host,
                        credentials=(
                            Credentials(username, password)
                            if (username or password)
                            else None
                        ),
                    )
                )
                try:
                    await device.update()
                    previous = DeviceState.ON if device.is_on else DeviceState.OFF
                    target = _resolve_target(command, previous)
                    if target == DeviceState.ON:
                        await device.turn_on()
                    else:
                        await device.turn_off()
                finally:
                    await device.disconnect()

                logger.info("%s → %s at %s", previous, target, self._host)
                return ControlResult(host=self._host, previous_state=previous, new_state=target)
            except KasaAuthError:
                logger.debug("Auth failed with credentials: %s", username or "blank")
                continue

        raise AuthenticationError(
            f"All credential candidates failed for {self._host}. "
            "Pass explicit --username/--password if device is cloud-paired."
        )

    async def get_status(self) -> StatusResult:
        """Read current power state without changing it."""
        credential_chain: list[tuple[str, str]] = (
            [("", "")]
            if self._protocol == ProtocolType.LEGACY
            else list(_KLAP_CREDENTIAL_CHAIN) + (
                [(self._username, self._password)] if self._username else []
            )
        )

        for username, password in credential_chain:
            try:
                device = await Device.connect(
                    config=DeviceConfig(
                        host=self._host,
                        credentials=(
                            Credentials(username, password)
                            if (username or password)
                            else None
                        ),
                    )
                )
                try:
                    await device.update()
                    state = DeviceState.ON if device.is_on else DeviceState.OFF
                    sys_info = getattr(device, "sys_info", {}) or {}
                    on_time = sys_info.get("on_time") if state == DeviceState.ON else None
                finally:
                    await device.disconnect()

                return StatusResult(host=self._host, state=state, on_time_secs=on_time)
            except KasaAuthError:
                continue

        raise AuthenticationError(
            f"All credential candidates failed for {self._host}."
        )


def _resolve_target(command: PowerCommand, current: DeviceState) -> DeviceState:
    match command:
        case PowerCommand.ON:
            return DeviceState.ON
        case PowerCommand.OFF:
            return DeviceState.OFF
        case PowerCommand.TOGGLE:
            return DeviceState.OFF if current == DeviceState.ON else DeviceState.ON
