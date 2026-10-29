"""
Pure-Python Windows .ICO & .PNG Generator for the "SETS" Logo.
Generates `assets/sets_logo.ico` (multi-size 256x256, 64x64, 48x48, 32x32, 16x16)
and `assets/sets_logo.png` featuring the SETS emerald & navy shield with "SETS" typography.
"""

import os
import struct
import zlib

# 5x7 bitmap font for "S", "E", "T"
GLYPHS = {
    "S": [
        "01111",
        "10000",
        "10000",
        "01110",
        "00001",
        "00001",
        "11110",
    ],
    "E": [
        "11111",
        "10000",
        "10000",
        "11110",
        "10000",
        "10000",
        "11111",
    ],
    "T": [
        "11111",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
    ],
}


def render_sets_rgba(size: int) -> bytes:
    """Render an RGBA image of given square `size` with the SETS shield & text."""
    rows = []
    half = size / 2.0
    radius = size * 0.46
    corner_r = size * 0.22

    # Text layout for "SETS" (4 chars, each 5x7, 1 col spacing => 23 cols wide, 7 rows tall)
    word = "SETS"
    grid_w = 23
    grid_h = 7

    for y in range(size):
        row = bytearray()
        ny = y / float(size)
        for x in range(size):
            nx = x / float(size)
            # Rounded square distance check
            dx = max(abs(x - half) - (radius - corner_r), 0.0)
            dy = max(abs(y - half) - (radius - corner_r), 0.0)
            dist = (dx * dx + dy * dy) ** 0.5

            if dist > corner_r:
                # Transparent outside rounded badge
                row.extend((0, 0, 0, 0))
                continue

            # Border highlight vs inner emerald-navy gradient
            if dist > corner_r - max(1.5, size * 0.04):
                # Bright emerald border
                r, g, b, a = 16, 185, 129, 255
            else:
                # Deep navy to emerald diagonal gradient
                t = (nx * 0.55 + ny * 0.45)
                r = int(11 * (1 - t) + 6 * t)
                g = int(25 * (1 - t) + 95 * t)
                b = int(48 * (1 - t) + 70 * t)
                a = 255

                # Top subtle energy arc
                if 0.16 <= ny <= 0.22 and 0.20 <= nx <= 0.80:
                    r, g, b = 52, 211, 153
                # Bottom subtle accent bar
                elif 0.78 <= ny <= 0.83 and 0.25 <= nx <= 0.75:
                    r, g, b = 16, 185, 129

            # Render crisp "SETS" text in the middle band (ny in 0.34 .. 0.68, nx in 0.11 .. 0.89)
            if 0.34 <= ny <= 0.68 and 0.11 <= nx <= 0.89:
                gx = int(((nx - 0.11) / 0.78) * grid_w)
                gy = int(((ny - 0.34) / 0.34) * grid_h)
                if 0 <= gx < grid_w and 0 <= gy < grid_h:
                    char_idx = gx // 6
                    col_in_char = gx % 6
                    if char_idx < 4 and col_in_char < 5:
                        ch = word[char_idx]
                        if GLYPHS[ch][gy][col_in_char] == "1":
                            r, g, b, a = 248, 250, 252, 255

            row.extend((r, g, b, a))
        rows.append(bytes(row))
    return b"".join(rows)


def encode_png(size: int, rgba_bytes: bytes) -> bytes:
    """Encode raw RGBA bytes into a valid PNG image."""
    stride = size * 4
    raw_scanlines = bytearray()
    for y in range(size):
        raw_scanlines.append(0)  # Filter type 0 (None)
        raw_scanlines.extend(rgba_bytes[y * stride : (y + 1) * stride])

    def make_chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw_scanlines), level=9)
    return (
        b"\x89PNG\r\n\x1a\n"
        + make_chunk(b"IHDR", ihdr)
        + make_chunk(b"IDAT", idat)
        + make_chunk(b"IEND", b"")
    )


def generate_sets_icons(output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    sizes = [256, 64, 48, 32, 16]
    png_blobs = []

    for sz in sizes:
        rgba = render_sets_rgba(sz)
        png_blobs.append((sz, encode_png(sz, rgba)))

    # Save 256x256 PNG
    png_path = os.path.join(output_dir, "sets_logo.png")
    with open(png_path, "wb") as f:
        f.write(png_blobs[0][1])

    # Build multi-icon Windows .ico file
    ico_path = os.path.join(output_dir, "sets_logo.ico")
    num_images = len(png_blobs)
    header = struct.pack("<HHH", 0, 1, num_images)
    offset = 6 + num_images * 16
    dir_entries = bytearray()
    image_data = bytearray()

    for sz, blob in png_blobs:
        w_byte = 0 if sz >= 256 else sz
        h_byte = 0 if sz >= 256 else sz
        entry = struct.pack(
            "<BBBBHHII",
            w_byte,
            h_byte,
            0,
            0,
            1,
            32,
            len(blob),
            offset,
        )
        dir_entries.extend(entry)
        image_data.extend(blob)
        offset += len(blob)

    with open(ico_path, "wb") as f:
        f.write(header + bytes(dir_entries) + bytes(image_data))

    print(f"Generated SETS icons: {ico_path} and {png_path}")
    return ico_path


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    generate_sets_icons(os.path.join(base, "assets"))
    generate_sets_icons(os.path.join(base, "static"))

