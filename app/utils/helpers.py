from __future__ import annotations

from decimal import Decimal, ROUND_DOWN


def round_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    quantized = Decimal(str(value)).quantize(Decimal(str(step)), rounding=ROUND_DOWN)
    return float(quantized)

