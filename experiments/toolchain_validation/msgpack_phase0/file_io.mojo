"""Phase 0 probe: binary file read/write used by CLI encode/decode harnesses."""

from std.collections import List
from std.io import FileHandle


comptime PATH: String = "/tmp/pyromojo_phase0_io.bin"


def write_sample() raises:
    var payload = List[UInt8](capacity=6)
    payload.append(0x00)
    payload.append(0xFF)
    payload.append(0x80)
    payload.append(0xC3)
    payload.append(0xA9)
    payload.append(0x7F)

    var f = FileHandle(PATH, "w")
    f.write_all(payload)
    f.close()
    print("write: PASS (6 bytes incl 0x00, 0xFF, 0x80)")


def read_all() raises -> List[UInt8]:
    var f = FileHandle(PATH, "r")
    var data = f.read_bytes()
    f.close()
    return data^


def check_full_read() raises:
    var data = read_all()
    assert len(data) == 6
    assert data[0] == 0x00
    assert data[1] == 0xFF
    assert data[2] == 0x80
    assert data[3] == 0xC3
    assert data[4] == 0xA9
    assert data[5] == 0x7F
    print("read_bytes(-1): PASS")


def check_chunked_read() raises:
    var f = FileHandle(PATH, "r")
    var first = f.read_bytes(size=2)
    var second = f.read_bytes(size=2)
    var rest = f.read_bytes()
    var eof = f.read_bytes()
    f.close()

    assert len(first) == 2
    assert first[0] == 0x00
    assert first[1] == 0xFF
    assert len(second) == 2
    assert second[0] == 0x80
    assert len(rest) == 2
    assert len(eof) == 0
    print("read_bytes(size): PASS (2 + 2 + 2, then empty at EOF)")


def check_seek() raises:
    var f = FileHandle(PATH, "r")
    var skipped = f.seek(4)
    assert skipped == 4
    var tail = f.read_bytes()
    f.close()
    assert len(tail) == 2
    assert tail[0] == 0xA9
    print("seek: PASS (offset 4 -> 2 bytes)")


def check_missing_file() raises:
    var raised = False
    try:
        var f = FileHandle("/tmp/pyromojo_phase0_missing_file.bin", "r")
        f.close()
    except e:
        raised = True
        print("missing file rejected:", e)
    assert raised
    print("missing file: PASS")


def main() raises:
    write_sample()
    check_full_read()
    check_chunked_read()
    check_seek()
    check_missing_file()
    print("file_io: PASS")
