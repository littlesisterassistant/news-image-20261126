# news-image-20261126 — entrypoint.
# Copies entry.png from this repository to $MAKEFUN_OUTPUT_DIR (default
# /output) and verifies the copy. Standard library only: no Pillow, no
# network. The file is a PNG or a JPEG, told apart by its first bytes,
# and the name stays entry.png either way.

import hashlib
import os
import shutil
import struct
import sys
import zlib

MAX_BYTES = 1_048_576
MAX_DIMENSION = 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"


def fail(message):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def png_dimensions(data):
    # IHDR is the first chunk: 8-byte magic, 4-byte length, 4-byte type,
    # then width and height as big-endian 32-bit integers.
    if len(data) < 24 or data[12:16] != b"IHDR":
        fail("PNG is missing its IHDR chunk")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def png_whole(data):
    # Walk every chunk, checking its CRC, until IEND.
    offset = 8
    saw_iend = False
    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        end = offset + 8 + length + 4
        if end > len(data):
            fail("PNG chunk runs past the end of the file")
        body = data[offset + 4:end - 4]
        crc = struct.unpack(">I", data[end - 4:end])[0]
        if crc != (zlib.crc32(body) & 0xFFFFFFFF):
            fail(f"PNG chunk {chunk_type!r} has a bad CRC")
        if chunk_type == b"IEND":
            saw_iend = True
            if end != len(data):
                fail("PNG has trailing bytes after IEND")
            break
        offset = end
    if not saw_iend:
        fail("PNG has no IEND chunk")


def jpeg_dimensions(data):
    # Scan segments for a Start Of Frame marker (0xC0-0xCF except 0xC4,
    # 0xC8, 0xCC), which carries height then width as big-endian 16-bit.
    offset = 2
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            fail("JPEG segment does not start with 0xFF")
        marker = data[offset + 1]
        if marker == 0xD8:  # SOI, no length field
            offset += 2
            continue
        if marker == 0xD9:  # EOI before any frame
            fail("JPEG ends before any frame")
        if 0xD0 <= marker <= 0xD7 or marker == 0x01:  # standalone
            offset += 2
            continue
        length = struct.unpack(">H", data[offset + 2:offset + 4])[0]
        if length < 2 or offset + 2 + length > len(data):
            fail("JPEG segment runs past the end of the file")
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height, width = struct.unpack(">HH", data[offset + 5:offset + 9])
            return width, height
        offset += 2 + length
    fail("JPEG has no Start Of Frame marker")


def jpeg_whole(data):
    if data[-2:] != b"\xff\xd9":
        fail("JPEG does not end with its EOI marker")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    source = os.path.join(here, "entry.png")
    if not os.path.isfile(source):
        fail(f"entry.png not found in {here}")
    with open(source, "rb") as handle:
        data = handle.read()
    if not data:
        fail("entry.png is empty")
    if len(data) > MAX_BYTES:
        fail(f"entry.png is {len(data)} bytes, over the 1 MiB limit")
    if data.startswith(PNG_MAGIC):
        kind = "PNG"
        width, height = png_dimensions(data)
        png_whole(data)
    elif data.startswith(JPEG_MAGIC):
        kind = "JPEG"
        width, height = jpeg_dimensions(data)
        jpeg_whole(data)
    else:
        fail("entry.png is neither PNG nor JPEG by its first bytes")
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        fail(f"image is {width}x{height}, over the 1024x1024 limit")
    if width < 1 or height < 1:
        fail(f"image has an invalid size {width}x{height}")

    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, "entry.png")
    shutil.copyfile(source, target)
    with open(target, "rb") as handle:
        copied = handle.read()
    if copied != data:
        fail("copy mismatch: output differs from entry.png")
    digest = hashlib.sha256(copied).hexdigest()
    print(f"wrote {target} ({kind} {width}x{height}, "
          f"{len(copied)} bytes, sha256 {digest})")


if __name__ == "__main__":
    main()
