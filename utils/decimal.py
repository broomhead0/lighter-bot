from decimal import Decimal, ROUND_DOWN

def quantize_down(value: float, precision: int = 4) -> Decimal:
    q = Decimal(str(value)).quantize(Decimal(10) ** -precision, rounding=ROUND_DOWN)
    return q
