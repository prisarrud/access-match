from decimal import Decimal


WIDTH_FACTORS = {"mm": Decimal("0.1"), "cm": Decimal("1"), "m": Decimal("100")}


def width_cm(value: float | str, unit: str) -> Decimal:
    return Decimal(str(value).replace(",", ".")) * WIDTH_FACTORS[unit]
