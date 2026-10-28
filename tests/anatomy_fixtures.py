"""Code-drawn diagrams with known limb counts, encoded as PNG using only the stdlib."""
import math
import struct
import zlib


class Diagram:
    width, height = 512, 640

    def __init__(self):
        self.pixels = bytearray([255]) * (self.width * self.height * 3)

    def rect(self, x0, y0, x1, y1, color):
        for y in range(max(0, int(y0)), min(self.height, int(y1) + 1)):
            start, end = max(0, int(x0)), min(self.width, int(x1) + 1)
            if start < end:
                offset = (y * self.width + start) * 3
                self.pixels[offset:offset + (end - start) * 3] = bytes(color) * (end - start)

    def circle(self, x, y, radius, color):
        for row in range(int(y - radius), int(y + radius) + 1):
            span = int(math.sqrt(max(0, radius * radius - (row - y) ** 2)))
            self.rect(x - span, row, x + span, row, color)

    def line(self, x0, y0, x1, y1, radius, color):
        steps = max(abs(int(x1 - x0)), abs(int(y1 - y0)), 1)
        for step in range(steps + 1):
            t = step / steps
            self.circle(int(x0 + t * (x1 - x0)), int(y0 + t * (y1 - y0)), radius, color)

    def person(self, extra_arm=False, extra_leg=False):
        skin, shirt, pants, black = (234, 173, 124), (35, 115, 190), (45, 55, 75), (15, 18, 23)
        self.line(236, 320, 215, 470, 22, pants)
        self.line(215, 470, 185, 570, 22, pants)
        self.line(280, 320, 300, 470, 22, pants)
        self.line(300, 470, 335, 570, 22, pants)
        if extra_leg:
            self.line(256, 330, 256, 595, 19, pants)
            self.line(252, 595, 274, 595, 17, black)
        self.line(170, 577, 198, 577, 18, black)
        self.line(325, 577, 355, 577, 18, black)
        self.rect(210, 155, 300, 335, shirt)
        self.line(214, 175, 145, 245, 20, shirt)
        self.line(145, 245, 85, 205, 15, skin)
        self.circle(78, 200, 19, skin)
        self.line(298, 175, 370, 240, 20, shirt)
        self.line(370, 240, 425, 180, 15, skin)
        self.circle(431, 173, 19, skin)
        if extra_arm:
            self.line(300, 245, 370, 335, 17, shirt)
            self.line(370, 335, 440, 325, 14, skin)
            self.circle(447, 325, 18, skin)
        self.rect(237, 118, 274, 164, skin)
        self.circle(256, 91, 44, skin)
        self.circle(241, 84, 4, black)
        self.circle(271, 84, 4, black)
        self.line(244, 109, 269, 109, 2, black)

    def png(self):
        def chunk(name, data):
            return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))
        rows = b"".join(b"\0" + self.pixels[y * self.width * 3:(y + 1) * self.width * 3]
                        for y in range(self.height))
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def fixtures():
    for name, arm, leg in (("normal", False, False), ("three_arms", True, False), ("three_legs", False, True)):
        diagram = Diagram()
        diagram.person(extra_arm=arm, extra_leg=leg)
        yield name, diagram.png()
    portrait = Diagram()
    portrait.person()
    portrait.rect(0, 150, 511, 639, (230, 230, 230))
    yield "occluded_body", portrait.png()
    empty = Diagram()
    yield "no_people", empty.png()
