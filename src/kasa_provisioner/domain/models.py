"""Domain models for kasa-provisioner."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field


class ProtocolType(StrEnum):
    LEGACY = "legacy"   # XOR/TCP port 9999
    KLAP_V1 = "klap_v1"  # HTTP/80, md5-based auth_hash
    KLAP_V2 = "klap_v2"  # HTTP/80, sha256-based auth_hash


class KeyType(StrEnum):
    OPEN = "0"
    WPA2 = "3"


class WifiConfig(BaseModel):
    ssid: Annotated[str, Field(min_length=1, max_length=32)]
    password: Annotated[str, Field(min_length=0, max_length=63)]
    key_type: KeyType = KeyType.WPA2


class DeviceInfo(BaseModel):
    host: str  # IP or hostname
    mac: str | None = None
    alias: str | None = None
    model: str | None = None
    protocol: ProtocolType = ProtocolType.LEGACY
    hw_version: str | None = None
    fw_version: str | None = None


class DeviceState(StrEnum):
    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"


class PowerCommand(StrEnum):
    ON = "on"
    OFF = "off"
    TOGGLE = "toggle"
