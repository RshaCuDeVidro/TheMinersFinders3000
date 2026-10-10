"""Minecraft Java protocol helpers (VarInt, handshake, whitelist probe)."""

import asyncio
import struct

from .constants import DEFAULT_PORT, PROTOCOL_VERSION, WL_KEYWORDS


def write_varint(d):
    out = b""
    while True:
        b = d & 0x7F
        d >>= 7
        if d > 0:
            out += struct.pack("B", b | 0x80)
        else:
            out += struct.pack("B", b)
            break
    return out


def read_varint_sync(data: bytes):
    value = shift = idx = 0
    while idx < len(data):
        b = data[idx]
        idx += 1
        value |= (b & 0x7F) << shift
        if not (b & 0x80):
            return value, idx
        shift += 7
        if shift > 35:
            break
    return value, idx


def parse_first_string(data: bytes) -> str:
    length, idx = read_varint_sync(data)
    return data[idx:idx + length].decode('utf-8', errors='ignore')


async def read_varint(reader):
    result = shift = 0
    while True:
        raw = await reader.read(1)
        if not raw:
            raise ConnectionError("eof")
        byte = raw[0]
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result
        shift += 7
        if shift > 35:
            raise ValueError("varint too big")


def parse_host_port(host: str):
    """Split ``host[:port]`` (IPv4, hostname or ``[IPv6]``) into ``(addr, port)``."""
    host = host.strip()
    if host.startswith("["):
        end = host.find("]")
        if end != -1:
            addr = host[1:end]
            rest = host[end + 1:]
            try:
                return addr, int(rest[1:]) if rest.startswith(":") else DEFAULT_PORT
            except ValueError:
                return addr, DEFAULT_PORT
    if host.count(":") == 1:
        addr, port = host.rsplit(":", 1)
        try:
            return addr, int(port)
        except ValueError:
            return host, DEFAULT_PORT
    return host, DEFAULT_PORT


def classify_whitelist(msg: str) -> str:
    low = msg.lower()
    return "yes" if any(k in low for k in WL_KEYWORDS) else "no"


async def check_whitelist_aggressive(ip, port, timeout=1.5):
    """Attempt a login and inspect the disconnect reason to detect a whitelist.

    Returns ``"yes"``, ``"no"`` or ``"unknown"``. *timeout* bounds both the
    initial connect and each subsequent read.
    """
    writer = None
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
        host_bytes = ip.encode('utf-8')
        handshake = (write_varint(0x00) + write_varint(PROTOCOL_VERSION) + write_varint(len(host_bytes))
                     + host_bytes + struct.pack(">H", port) + write_varint(2))
        writer.write(write_varint(len(handshake)) + handshake)
        name = b"reescanner"
        login_start = write_varint(0x00) + write_varint(len(name)) + name
        writer.write(write_varint(len(login_start)) + login_start)
        await writer.drain()

        for _ in range(3):
            try:
                packet_len = await asyncio.wait_for(read_varint(reader), timeout=timeout)
                packet_id = await asyncio.wait_for(read_varint(reader), timeout=timeout)
                consumed = len(write_varint(packet_id))
                payload = await asyncio.wait_for(reader.readexactly(max(0, packet_len - consumed)), timeout=timeout)
            except (asyncio.IncompleteReadError, ConnectionError, asyncio.TimeoutError, ValueError):
                break
            if packet_id == 0x00:
                return classify_whitelist(parse_first_string(payload))
        return "unknown"
    except Exception:
        return "unknown"
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
