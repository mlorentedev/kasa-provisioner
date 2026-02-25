"""
Legacy TP-Link protocol client (XOR autokey cipher over TCP/9999).

Protocol reference: https://www.softscheck.com/en/blog/tp-link-reverse-engineering/

Frame format: [4-byte big-endian length][XOR-encoded JSON payload]
Cipher: autokey XOR — key starts at 0xAB; each plaintext byte becomes next key.
"""

import asyncio
import json
import struct
from typing import Any

from kasa_provisioner.domain.exceptions import ConnectionError, ProvisioningError

_INITIAL_KEY: int = 0xAB
_PORT: int = 9999
_CONNECT_TIMEOUT: float = 5.0
_READ_TIMEOUT: float = 5.0


def _xor_encode(plaintext: bytes) -> bytes:
    key = _INITIAL_KEY
    result = bytearray(len(plaintext))
    for i, byte in enumerate(plaintext):
        encoded = byte ^ key
        result[i] = encoded
        key = byte  # autokey: next key = current plaintext byte
    return bytes(result)


def _xor_decode(ciphertext: bytes) -> bytes:
    key = _INITIAL_KEY
    result = bytearray(len(ciphertext))
    for i, byte in enumerate(ciphertext):
        result[i] = byte ^ key
        key = result[i]  # autokey: next key = current plaintext byte
    return bytes(result)


def _pack(payload: dict[str, Any]) -> bytes:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    encoded = _xor_encode(raw)
    return struct.pack(">I", len(encoded)) + encoded


def _unpack(frame: bytes) -> dict[str, Any]:
    if len(frame) < 4:
        raise ProvisioningError(f"Malformed response: only {len(frame)} bytes")
    length = struct.unpack(">I", frame[:4])[0]
    payload = frame[4 : 4 + length]
    return json.loads(_xor_decode(payload))


class LegacyClient:
    """Async client for the TP-Link legacy (XOR) protocol."""

    def __init__(self, host: str, port: int = _PORT) -> None:
        self.host = host
        self.port = port

    async def send(self, command: dict[str, Any]) -> dict[str, Any]:
        """Send a command and return the parsed response."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=_CONNECT_TIMEOUT,
            )
        except (OSError, asyncio.TimeoutError) as exc:
            raise ConnectionError(f"Cannot connect to {self.host}:{self.port}") from exc

        try:
            writer.write(_pack(command))
            await writer.drain()

            header = await asyncio.wait_for(reader.readexactly(4), timeout=_READ_TIMEOUT)
            length = struct.unpack(">I", header)[0]
            body = await asyncio.wait_for(reader.readexactly(length), timeout=_READ_TIMEOUT)
            return _unpack(header + body)
        except asyncio.IncompleteReadError as exc:
            # AP mode closes the connection without sending any response — that is
            # normal behaviour (no ACK).  Return empty dict; callers must handle it.
            if not exc.partial:
                return {}
            raise ProvisioningError(f"Truncated response from {self.host}") from exc
        except asyncio.TimeoutError as exc:
            raise ProvisioningError(f"Read timeout from {self.host}") from exc
        finally:
            writer.close()
            await writer.wait_closed()

    async def get_info(self) -> dict[str, Any]:
        return await self.send({"system": {"get_sysinfo": {}}})

    async def set_wifi(self, ssid: str, password: str, key_type: int = 3) -> dict[str, Any]:
        """Inject WiFi credentials — the core bootstrap command."""
        return await self.send(
            {"netif": {"set_stainfo": {"ssid": ssid, "password": password, "key_type": key_type}}}
        )

    async def set_power(self, *, state: bool) -> dict[str, Any]:
        return await self.send({"system": {"set_relay_state": {"state": int(state)}}})
