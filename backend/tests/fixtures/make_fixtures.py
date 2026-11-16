"""Regenerate the parser fixtures: .venv/bin/python -m backend.tests.fixtures.make_fixtures"""
from pathlib import Path

HERE = Path(__file__).parent
F008 = b"850101s1999    nyu           000 0 eng d"  # 40 bytes


def build(fields, enc=b"a", leader_tail=b"2200000 a 4500"):
    """fields: list of (tag, bytes) without terminator."""
    directory, body, off = b"", b"", 0
    for tag, data in fields:
        data += b"\x1e"
        directory += tag.encode() + b"%04d%05d" % (len(data), off)
        body += data
        off += len(data)
    directory += b"\x1e"
    base = 24 + len(directory)
    total = base + len(body) + 1
    leader = b"%05d" % total + b"nam " + enc + b"22" + b"%05d" % base + b" a 4500"
    assert len(leader) == 24
    return leader + directory + body + b"\x1d"


def df(i1, i2, *subs):
    return i1 + i2 + b"".join(b"\x1f" + c + v for c, v in subs)


def std(title: bytes, enc=b"a", f008=F008, author=b"Doe, Jane,"):
    fields = [("001", b"ctl001")]
    if f008 is not None:
        fields.append(("008", f008))
    fields += [
        ("020", df(b" ", b" ", (b"a", b"9780306406157"))),
        ("100", df(b"1", b" ", (b"a", author), (b"d", b"1900-1980"))),
        ("245", df(b"1", b"0", (b"a", title), (b"c", b"by Jane Doe."))),
        ("650", df(b" ", b"0", (b"a", b"Libraries"), (b"z", b"France"))),
    ]
    return build(fields, enc)


def main():
    (HERE / "clean_utf8.mrc").write_bytes(std("Café /".encode(), b"a"))
    (HERE / "marc8_diacritics.mrc").write_bytes(std(b"Caf\xe2e /", b" "))
    (HERE / "latin1.mrc").write_bytes(std(b"Caf\xe9 /", b"a"))
    clean = std(b"Title /", b"a")
    (HERE / "truncated.mrc").write_bytes(clean[:-30])
    bad = bytearray(clean)
    bad[24 + 3:24 + 7] = b"ABCD"  # non-numeric field length in first entry
    (HERE / "bad_directory.mrc").write_bytes(bytes(bad))
    (HERE / "missing_008.mrc").write_bytes(std(b"Title /", b"a", f008=None))


if __name__ == "__main__":
    main()
