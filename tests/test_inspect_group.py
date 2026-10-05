import importlib.util
import struct
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "inspect_group.py"
spec = importlib.util.spec_from_file_location("inspect_group", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def make_group(path: Path) -> None:
    names = [b"A.MSP", b"ZERO.MAZ", b"B.POJ"]
    payloads = [b"abc", b"", b"12345"]
    count = len(names)
    directory_end = 2 + count * mod.ENTRY_SIZE
    records = bytearray()
    start = directory_end
    for name, payload in zip(names, payloads):
        record = bytearray(mod.ENTRY_SIZE)
        record[:len(name)] = name
        struct.pack_into("<I", record, 0x0E, start)
        records += record
        start += len(payload)
    data = struct.pack("<H", count) + records + b"".join(payloads) + b"\0\0\0\0"
    path.write_bytes(data)


def test_parse_group_and_zero_length_entry(tmp_path: Path) -> None:
    path = tmp_path / "GROUP01"
    make_group(path)
    info = mod.parse(path)
    assert info["entry_count"] == 3
    assert info["directory_end"] == 2 + 3 * 22
    assert [e["name"] for e in info["entries"]] == ["A.MSP", "ZERO.MAZ", "B.POJ"]
    assert [e["payload_size"] for e in info["entries"]] == [3, 0, 5]
    assert [e["installed_payload_start"] for e in info["entries"]] == [0, 3, 3]
    assert info["trailer_hex"] == "00000000"


def test_first_offset_is_own_payload_start(tmp_path: Path) -> None:
    path = tmp_path / "GROUP02"
    make_group(path)
    data = path.read_bytes()
    directory_end = 2 + 3 * mod.ENTRY_SIZE
    first = struct.unpack_from("<I", data, 2 + 0x0E)[0]
    assert first == directory_end
    info = mod.parse(path)
    assert info["entries"][0]["payload_start"] == directory_end
    assert info["entries"][0]["payload_end"] == directory_end + 3


def test_rejects_installed_payload_without_directory(tmp_path: Path) -> None:
    path = tmp_path / "GROUP01"
    path.write_bytes(b"\x3c\x00" + b"payload")
    try:
        mod.parse(path)
    except ValueError as exc:
        assert "CD-style GROUP" in str(exc)
    else:
        raise AssertionError("directory-less installed GROUP was accepted")
