"""Small JavaScript-compatible helpers so the Python port of the engine behaves exactly like the original
TypeScript: Math.round (half up), Number#toFixed, String(number), Number#toString(base) and the seeded PRNG."""
import math
from decimal import ROUND_HALF_UP, Decimal

MASK32 = 0xFFFFFFFF


def js_round(x: float) -> int:
    """Math.round: halves round towards +infinity (Python's round() rounds halves to even)."""
    return math.floor(x + 0.5)


def to_fixed(x: float, digits: int) -> str:
    """Number#toFixed: exact binary value, ties rounded up in magnitude."""
    q = Decimal(1).scaleb(-digits)
    d = Decimal(x).quantize(q, rounding=ROUND_HALF_UP)
    return format(d, "f")


def js_str(x) -> str:
    """String(number): integers print without a decimal point."""
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        if math.isnan(x):
            return "NaN"
        if math.isinf(x):
            return "Infinity" if x > 0 else "-Infinity"
        if x == int(x) and abs(x) < 1e21:
            return str(int(x))
        r = repr(x)
        if "e" in r:
            mant, exp = r.split("e")
            sign = "-" if exp.startswith("-") else "+"
            return f"{mant}e{sign}{int(exp.lstrip('+-'))}"
        return r
    return str(x)


def num(x):
    """A float that holds a whole number becomes an int, as JSON.stringify would print it."""
    if isinstance(x, float) and x.is_integer() and abs(x) < 2 ** 53:
        return int(x)
    return x


def to_base(v: int, base: int) -> str:
    """Number#toString(base) for integers (lower-case digits)."""
    if base == 10:
        return str(v)
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    if v == 0:
        return "0"
    neg, v = v < 0, abs(v)
    out = []
    while v:
        v, r = divmod(v, base)
        out.append(digits[r])
    return ("-" if neg else "") + "".join(reversed(out))


def imul(a: int, b: int) -> int:
    """Math.imul: 32-bit signed multiply."""
    r = ((a & MASK32) * (b & MASK32)) & MASK32
    return r - 0x100000000 if r & 0x80000000 else r


def to_int32(x: int) -> int:
    x &= MASK32
    return x - 0x100000000 if x & 0x80000000 else x


def urshift(x: int, n: int) -> int:
    """x >>> n"""
    return (x & MASK32) >> n


class Rng:
    """Port of engine/rng.ts: reproducible PRNG, the same seed always yields the same puzzle."""

    def __init__(self, seed: str):
        h = to_int32(1779033703 ^ len(seed))
        for ch in seed:
            h = imul(h ^ ord(ch), 3432918353)
            h = to_int32((h << 13) | urshift(h, 19))
        self._a = urshift(h, 0)

    def next(self) -> float:
        a = to_int32(self._a)
        a = to_int32(a + 0x6D2B79F5)
        self._a = a
        t = imul(a ^ urshift(a, 15), 1 | a)
        t = to_int32(to_int32(t + imul(t ^ urshift(t, 7), 61 | t)) ^ t)
        return urshift(t ^ urshift(t, 14), 0) / 4294967296

    def int(self, lo: int, hi: int) -> int:
        return lo + math.floor(self.next() * (hi - lo + 1))

    def pick(self, arr):
        return arr[math.floor(self.next() * len(arr))]

    def shuffle(self, arr):
        out = list(arr)
        for i in range(len(out) - 1, 0, -1):
            j = math.floor(self.next() * (i + 1))
            out[i], out[j] = out[j], out[i]
        return out

    def chance(self, p: float) -> bool:
        return self.next() < p
