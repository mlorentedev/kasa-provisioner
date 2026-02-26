"""Unit tests for the XOR codec, TCP framing, and UDP transport of LegacyClient."""

import json
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kasa_provisioner.infra.legacy_client import (
    LegacyClient,
    _pack,
    _unpack,
    _xor_decode,
    _xor_encode,
)

# Known-good vector from the softscheck reverse engineering post
# "192.168.0.1" discovery — not testing network, only codec correctness


class TestXorCodec:
    def test_roundtrip_simple(self) -> None:
        plaintext = b'{"system":{"get_sysinfo":{}}}'
        assert _xor_decode(_xor_encode(plaintext)) == plaintext

    def test_roundtrip_empty(self) -> None:
        assert _xor_decode(_xor_encode(b"")) == b""

    def test_roundtrip_binary_like(self) -> None:
        data = bytes(range(256))
        assert _xor_decode(_xor_encode(data)) == data

    def test_initial_key_applied(self) -> None:
        # First byte: 0x00 XOR 0xAB == 0xAB
        encoded = _xor_encode(b"\x00")
        assert encoded[0] == 0xAB

    def test_autokey_progression(self) -> None:
        # First byte: 'A'(0x41) XOR 0xAB = 0xEA, key becomes 0x41
        # Second byte: 'B'(0x42) XOR 0x41 = 0x03
        encoded = _xor_encode(b"AB")
        assert encoded[0] == 0x41 ^ 0xAB
        assert encoded[1] == 0x42 ^ 0x41


class TestFraming:
    def test_pack_includes_length_prefix(self) -> None:
        command = {"system": {"get_sysinfo": {}}}
        frame = _pack(command)
        length = struct.unpack(">I", frame[:4])[0]
        assert length == len(frame) - 4

    def test_pack_unpack_roundtrip(self) -> None:
        command = {"netif": {"set_stainfo": {"ssid": "MyNet", "password": "s3cr3t", "key_type": 3}}}
        frame = _pack(command)
        result = _unpack(frame)
        assert result == command

    def test_unpack_raises_on_short_frame(self) -> None:
        from kasa_provisioner.domain.exceptions import ProvisioningError
        with pytest.raises(ProvisioningError):
            _unpack(b"\x00\x01")


class TestUdpTransport:
    async def test_send_udp_sends_xor_without_length_header(self) -> None:
        """UDP frames must NOT include the 4-byte length prefix."""
        client = LegacyClient("192.168.0.1")
        command = {"system": {"get_sysinfo": {}}}

        raw = json.dumps(command, separators=(",", ":")).encode()
        expected_payload = _xor_encode(raw)

        mock_transport = MagicMock()
        mock_transport.sendto = MagicMock()
        mock_transport.close = MagicMock()

        async def fake_endpoint(*args, **kwargs):  # type: ignore[no-untyped-def]
            return mock_transport, None

        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop.return_value.create_datagram_endpoint = fake_endpoint
            await client.send_udp(command)

        mock_transport.sendto.assert_called_once_with(expected_payload)
        mock_transport.close.assert_called_once()

    async def test_set_wifi_udp_sends_both_namespaces(self) -> None:
        """set_wifi_udp sends netif first, then softaponboarding fallback."""
        client = LegacyClient("192.168.0.1")
        client.send_udp = AsyncMock()  # type: ignore[method-assign]

        await client.set_wifi_udp(ssid="TestNet", password="pass123", key_type=3)

        assert client.send_udp.call_count == 2
        first_call = client.send_udp.call_args_list[0][0][0]
        second_call = client.send_udp.call_args_list[1][0][0]

        assert "netif" in first_call
        assert first_call["netif"]["set_stainfo"]["ssid"] == "TestNet"
        assert "smartlife.iot.common.softaponboarding" in second_call
        softonboarding = second_call["smartlife.iot.common.softaponboarding"]
        assert softonboarding["set_stainfo"]["ssid"] == "TestNet"
