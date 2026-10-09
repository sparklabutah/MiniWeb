"""Minimal, dependency-free QR Code encoder (byte mode).

Pure Python — no third-party libraries, no network. Produces a real,
standards-compliant QR Code matrix (and an SVG rendering) that actually
encodes the given text, so different short URLs yield different, scannable
QR codes.

Supports byte (ISO-8859-1 / UTF-8) mode, automatic version selection
(versions 1-40), Reed-Solomon error correction, all 8 data masks with
penalty-based auto-selection, and format/version information — i.e. a
genuine QR code, not a decorative placeholder.

The algorithm follows the QR Code specification (ISO/IEC 18004). The
lookup tables (ECC codewords per block, blocks per version, alignment
pattern positions) are the standard values defined by that spec.
"""

# ---------------------------------------------------------------------------
# Standard specification tables (indexed by version 1..40; index 0 unused)
# ---------------------------------------------------------------------------

# Error-correction codewords per block, per ECC level (L, M, Q, H).
_ECC_CODEWORDS_PER_BLOCK = (
    (-1,  7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28, 28, 28, 30, 30, 26, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),  # L
    (-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28),  # M
    (-1, 13, 22, 18, 26, 18, 24, 18, 22, 20, 24, 28, 26, 24, 20, 30, 24, 28, 28, 26, 30, 28, 30, 30, 30, 30, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),  # Q
    (-1, 17, 28, 22, 16, 22, 28, 26, 26, 24, 28, 24, 28, 22, 24, 24, 30, 28, 28, 26, 28, 30, 24, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),  # H
)

# Number of error-correction blocks, per ECC level (L, M, Q, H).
_NUM_ERROR_CORRECTION_BLOCKS = (
    (-1, 1, 1, 1, 1, 1, 2, 2, 2, 2,  4,  4,  4,  4,  4,  6,  6,  6,  6,  7,  8,  8,  9,  9, 10, 12, 12, 12, 13, 14, 15, 16, 17, 18, 19, 19, 20, 21, 22, 24, 25),  # L
    (-1, 1, 1, 1, 2, 2, 4, 4, 4, 5,  5,  5,  8,  9,  9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49),  # M
    (-1, 1, 1, 2, 2, 4, 4, 6, 6, 8,  8,  8, 10, 12, 16, 12, 17, 16, 18, 21, 20, 23, 23, 25, 27, 29, 34, 34, 35, 38, 40, 43, 45, 48, 51, 53, 56, 59, 62, 65, 68),  # Q
    (-1, 1, 1, 2, 4, 4, 4, 5, 6, 8,  8, 11, 11, 16, 16, 18, 16, 19, 21, 25, 25, 25, 34, 30, 32, 35, 37, 40, 42, 45, 48, 51, 54, 57, 60, 63, 66, 70, 74, 77, 81),  # H
)

# ECC level -> (table ordinal, 2-bit format value used in the format string)
_ECC_LEVELS = {
    "L": (0, 1),
    "M": (1, 0),
    "Q": (2, 3),
    "H": (3, 2),
}


# ---------------------------------------------------------------------------
# Reed-Solomon error correction over GF(256) with QR's primitive polynomial
# ---------------------------------------------------------------------------

def _rs_multiply(x, y):
    """Multiply two bytes in GF(2^8), modulo 0x11D (QR's field polynomial)."""
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z & 0xFF


def _rs_divisor(degree):
    """Compute the generator (divisor) polynomial for the given degree."""
    result = [0] * (degree - 1) + [1]  # monomial x^0 == 1
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _rs_multiply(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _rs_multiply(root, 0x02)
    return result


def _rs_remainder(data, divisor):
    """Polynomial remainder of data divided by divisor -> ECC codewords."""
    result = [0] * len(divisor)
    for b in data:
        factor = b ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _rs_multiply(coef, factor)
    return result


# ---------------------------------------------------------------------------
# Capacity helpers
# ---------------------------------------------------------------------------

def _num_raw_data_modules(ver):
    """Total number of data+ECC modules (not counting function patterns)."""
    result = (16 * ver + 128) * ver + 64
    if ver >= 2:
        numalign = ver // 7 + 2
        result -= (25 * numalign - 10) * numalign - 55
        if ver >= 7:
            result -= 36
    return result


def _num_data_codewords(ver, ecl_ordinal):
    """Number of usable 8-bit data codewords for a version + ECC level."""
    return (_num_raw_data_modules(ver) // 8
            - _ECC_CODEWORDS_PER_BLOCK[ecl_ordinal][ver]
            * _NUM_ERROR_CORRECTION_BLOCKS[ecl_ordinal][ver])


def _byte_mode_count_bits(ver):
    """Bit width of the character-count indicator for byte mode."""
    return 8 if ver <= 9 else 16


# ---------------------------------------------------------------------------
# The encoder
# ---------------------------------------------------------------------------

class QrCode:
    """A rendered QR Code: ``self.modules[y][x]`` is True for dark modules."""

    def __init__(self, text, ecc="M"):
        if ecc not in _ECC_LEVELS:
            raise ValueError("ecc must be one of L, M, Q, H")
        self.text = text
        self.ecc_level = ecc
        self._ecl_ordinal, self._ecl_formatbits = _ECC_LEVELS[ecc]

        data = text.encode("utf-8")
        self.version = self._choose_version(data)
        self.size = self.version * 4 + 17

        self.modules = [[False] * self.size for _ in range(self.size)]
        self._isfunction = [[False] * self.size for _ in range(self.size)]

        codewords = self._make_codewords(data)
        self._draw_function_patterns()
        self._draw_codewords(codewords)
        self._mask = self._pick_best_mask()
        # _pick_best_mask leaves the best mask applied and format bits drawn.

    # -- data encoding ------------------------------------------------------

    def _choose_version(self, data):
        for ver in range(1, 41):
            capacity_bits = _num_data_codewords(ver, self._ecl_ordinal) * 8
            needed = 4 + _byte_mode_count_bits(ver) + 8 * len(data)
            if needed <= capacity_bits:
                return ver
        raise ValueError("Data too long for a QR Code (max version 40)")

    def _make_codewords(self, data):
        """Build the full interleaved data+ECC codeword sequence."""
        ver = self.version
        bits = []

        def append_bits(value, n):
            for i in range(n - 1, -1, -1):
                bits.append((value >> i) & 1)

        # Byte mode segment: mode indicator (0b0100) + count + payload.
        append_bits(0x4, 4)
        append_bits(len(data), _byte_mode_count_bits(ver))
        for b in data:
            append_bits(b, 8)

        capacity_bits = _num_data_codewords(ver, self._ecl_ordinal) * 8
        # Terminator (up to 4 zero bits) then pad to a byte boundary.
        bits += [0] * min(4, capacity_bits - len(bits))
        bits += [0] * (-len(bits) % 8)

        # Pad with the alternating bytes 0xEC, 0x11 per the spec.
        for pad in (0xEC, 0x11) * ((capacity_bits - len(bits)) // 8 // 1):
            if len(bits) >= capacity_bits:
                break
            append_bits(pad, 8)

        # Pack into data codewords (bytes).
        data_codewords = bytearray(len(bits) // 8)
        for i, bit in enumerate(bits):
            data_codewords[i >> 3] |= bit << (7 - (i & 7))

        return self._add_ecc_and_interleave(data_codewords)

    def _add_ecc_and_interleave(self, data):
        ver = self.version
        ecl = self._ecl_ordinal
        numblocks = _NUM_ERROR_CORRECTION_BLOCKS[ecl][ver]
        blockecclen = _ECC_CODEWORDS_PER_BLOCK[ecl][ver]
        rawcodewords = _num_raw_data_modules(ver) // 8
        numshortblocks = numblocks - rawcodewords % numblocks
        shortblocklen = rawcodewords // numblocks

        blocks = []
        rsdiv = _rs_divisor(blockecclen)
        k = 0
        for i in range(numblocks):
            datalen = shortblocklen - blockecclen + (0 if i < numshortblocks else 1)
            dat = list(data[k:k + datalen])
            k += datalen
            ecc = _rs_remainder(dat, rsdiv)
            if i < numshortblocks:
                dat.append(0)  # placeholder to align columns
            blocks.append(dat + ecc)

        # Interleave data + ECC codewords across the blocks.
        result = []
        for i in range(len(blocks[0])):
            for j, blk in enumerate(blocks):
                # Skip the placeholder column of the short blocks.
                if i != shortblocklen - blockecclen or j >= numshortblocks:
                    result.append(blk[i])
        return result

    # -- module placement ---------------------------------------------------

    def _set_function(self, x, y, dark):
        self.modules[y][x] = dark
        self._isfunction[y][x] = True

    def _draw_function_patterns(self):
        size = self.size
        # Timing patterns.
        for i in range(size):
            self._set_function(6, i, i % 2 == 0)
            self._set_function(i, 6, i % 2 == 0)
        # Three finder patterns (top-left, top-right, bottom-left).
        self._draw_finder(3, 3)
        self._draw_finder(size - 4, 3)
        self._draw_finder(3, size - 4)
        # Alignment patterns.
        positions = self._alignment_positions()
        n = len(positions)
        skips = ((0, 0), (0, n - 1), (n - 1, 0))
        for i in range(n):
            for j in range(n):
                if (i, j) not in skips:
                    self._draw_alignment(positions[i], positions[j])
        # Reserve format + version areas (values drawn later).
        self._draw_format_bits(0)
        self._draw_version()

    def _draw_finder(self, cx, cy):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx + dx, cy + dy
                if 0 <= x < self.size and 0 <= y < self.size:
                    dist = max(abs(dx), abs(dy))
                    self._set_function(x, y, dist not in (2, 4))

    def _draw_alignment(self, cx, cy):
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                self._set_function(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)

    def _alignment_positions(self):
        ver = self.version
        if ver == 1:
            return []
        numalign = ver // 7 + 2
        step = (ver * 8 + numalign * 2 + 1) // (numalign * 2 - 2) * 2
        result = [6]
        pos = ver * 4 + 10
        for _ in range(numalign - 1):
            result.insert(1, pos)
            pos -= step
        return result

    def _draw_format_bits(self, mask):
        data = self._ecl_formatbits << 3 | mask  # 5 bits
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = (data << 10 | rem) ^ 0x5412  # 15-bit BCH, XOR-masked
        size = self.size

        # First copy (around the top-left finder).
        for i in range(6):
            self._set_function(8, i, _get_bit(bits, i))
        self._set_function(8, 7, _get_bit(bits, 6))
        self._set_function(8, 8, _get_bit(bits, 7))
        self._set_function(7, 8, _get_bit(bits, 8))
        for i in range(9, 15):
            self._set_function(14 - i, 8, _get_bit(bits, i))

        # Second copy (split across the other two finders).
        for i in range(8):
            self._set_function(size - 1 - i, 8, _get_bit(bits, i))
        for i in range(8, 15):
            self._set_function(8, size - 15 + i, _get_bit(bits, i))
        self._set_function(8, size - 8, True)  # always-dark module

    def _draw_version(self):
        if self.version < 7:
            return
        rem = self.version
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        bits = self.version << 12 | rem  # 18-bit BCH
        for i in range(18):
            bit = _get_bit(bits, i)
            a = self.size - 11 + i % 3
            b = i // 3
            self._set_function(a, b, bit)
            self._set_function(b, a, bit)

    def _draw_codewords(self, codewords):
        size = self.size
        i = 0  # bit index into codewords
        total = len(codewords) * 8
        col = size - 1
        while col >= 1:
            if col == 6:  # skip the vertical timing column
                col -= 1
            for vert in range(size):
                for j in range(2):
                    x = col - j
                    upward = ((col + 1) & 2) == 0
                    y = (size - 1 - vert) if upward else vert
                    if not self._isfunction[y][x] and i < total:
                        self.modules[y][x] = _get_bit(codewords[i >> 3], 7 - (i & 7))
                        i += 1
                    # remaining positions are implicitly 0 (already False)
            col -= 2

    # -- masking ------------------------------------------------------------

    def _apply_mask(self, mask):
        for y in range(self.size):
            for x in range(self.size):
                if self._isfunction[y][x]:
                    continue
                if mask == 0:
                    invert = (x + y) % 2 == 0
                elif mask == 1:
                    invert = y % 2 == 0
                elif mask == 2:
                    invert = x % 3 == 0
                elif mask == 3:
                    invert = (x + y) % 3 == 0
                elif mask == 4:
                    invert = (x // 3 + y // 2) % 2 == 0
                elif mask == 5:
                    invert = (x * y) % 2 + (x * y) % 3 == 0
                elif mask == 6:
                    invert = ((x * y) % 2 + (x * y) % 3) % 2 == 0
                else:
                    invert = ((x + y) % 2 + (x * y) % 3) % 2 == 0
                if invert:
                    self.modules[y][x] = not self.modules[y][x]

    def _pick_best_mask(self):
        best_mask = 0
        best_penalty = None
        for mask in range(8):
            self._apply_mask(mask)
            self._draw_format_bits(mask)
            penalty = self._penalty_score()
            if best_penalty is None or penalty < best_penalty:
                best_penalty = penalty
                best_mask = mask
            self._apply_mask(mask)  # undo (XOR is its own inverse)
        self._apply_mask(best_mask)
        self._draw_format_bits(best_mask)
        return best_mask

    def _penalty_score(self):
        size = self.size
        mods = self.modules
        score = 0

        # Rule 1: runs of 5+ same-color modules in each row/column.
        for k in range(size):
            runcolor = False
            runx = 0
            runy = False
            runylen = 0
            colorx = False
            for i in range(size):
                if mods[k][i] == colorx:
                    runx += 1
                    if runx == 5:
                        score += 3
                    elif runx > 5:
                        score += 1
                else:
                    colorx = mods[k][i]
                    runx = 1
                if mods[i][k] == runy:
                    runylen += 1
                    if runylen == 5:
                        score += 3
                    elif runylen > 5:
                        score += 1
                else:
                    runy = mods[i][k]
                    runylen = 1

        # Rule 2: 2x2 blocks of the same color.
        for y in range(size - 1):
            for x in range(size - 1):
                c = mods[y][x]
                if c == mods[y][x + 1] == mods[y + 1][x] == mods[y + 1][x + 1]:
                    score += 3

        # Rule 3: finder-like 1:1:3:1:1 patterns in rows and columns.
        pat1 = [True, False, True, True, True, False, True, False, False, False, False]
        pat2 = list(reversed(pat1))
        for y in range(size):
            for x in range(size - 10):
                rowseg = [mods[y][x + i] for i in range(11)]
                if rowseg == pat1 or rowseg == pat2:
                    score += 40
        for x in range(size):
            for y in range(size - 10):
                colseg = [mods[y + i][x] for i in range(11)]
                if colseg == pat1 or colseg == pat2:
                    score += 40

        # Rule 4: overall balance of dark vs light modules.
        dark = sum(row.count(True) for row in mods)
        total = size * size
        ratio = dark * 20 // total  # dark percentage / 5
        score += min(abs(ratio - 10), abs(ratio - 9)) * 10
        return score

    # -- output -------------------------------------------------------------

    def matrix(self):
        """Return the module matrix as a list of lists of 0/1 ints."""
        return [[1 if cell else 0 for cell in row] for row in self.modules]

    def to_svg(self, scale=8, border=4, dark="#000000", light="#ffffff"):
        """Render the QR Code to a standalone, scannable SVG string."""
        if border < 0 or scale <= 0:
            raise ValueError("Invalid scale or border")
        dim = (self.size + border * 2) * scale
        parts = []
        for y in range(self.size):
            for x in range(self.size):
                if self.modules[y][x]:
                    px = (x + border) * scale
                    py = (y + border) * scale
                    parts.append("M{0},{1}h{2}v{2}h-{2}z".format(px, py, scale))
        path = "".join(parts)
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
            'width="{d}" height="{d}" viewBox="0 0 {d} {d}" '
            'shape-rendering="crispEdges" role="img" '
            'aria-label="QR code">'
            '<rect width="{d}" height="{d}" fill="{light}"/>'
            '<path d="{path}" fill="{dark}"/>'
            '</svg>'
        ).format(d=dim, light=light, dark=dark, path=path)


def _get_bit(value, i):
    return (value >> i) & 1 != 0


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def make_qr_matrix(text, ecc="M"):
    """Return the module matrix (list of list of 0/1) encoding ``text``."""
    return QrCode(text, ecc).matrix()


def make_qr_svg(text, ecc="M", scale=8, border=4,
                dark="#000000", light="#ffffff"):
    """Return an SVG string of a real QR code encoding ``text``."""
    return QrCode(text, ecc).to_svg(scale=scale, border=border,
                                    dark=dark, light=light)
