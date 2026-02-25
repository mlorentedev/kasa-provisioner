"""Unit tests for the XOR codec and TCP framing of LegacyClient."""

import json
import struct

import pytest

from kasa_provisioner.infra.legacy_client import _xor_decode, _xor_encode, _pack, _unpack

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
