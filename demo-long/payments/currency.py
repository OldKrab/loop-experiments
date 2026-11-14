"""Money amounts are stored as integers in the currency's minor unit (cents, yen, fils)."""
from decimal import Decimal, ROUND_HALF_EVEN

# Units of each currency per 1 USD.
RATES = {"USD": Decimal("1"), "EUR": Decimal("0.92"), "GBP": Decimal("0.79"),
         "JPY": Decimal("149.50"), "KWD": Decimal("0.307")}

# ISO 4217 minor-unit exponent: how many decimal places the currency has.
MINOR_UNITS = {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0, "KWD": 3}


def to_major(amount_minor: int, currency: str) -> Decimal:
    """Minor units -> major units, e.g. 1050 USD cents -> Decimal('10.50')."""
    return Decimal(amount_minor) / 100


def to_minor(amount: Decimal, currency: str) -> int:
    """Major units -> minor units, rounded half-even."""
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


def convert(amount_minor: int, src: str, dst: str) -> int:
    """Convert an amount in `src` minor units to `dst` minor units."""
    if src not in RATES or dst not in RATES:
        raise ValueError(f"unsupported currency: {src if src not in RATES else dst}")
    usd = to_major(amount_minor, src) / RATES[src]
    return to_minor(usd * RATES[dst], dst)


def format_amount(amount_minor: int, currency: str) -> str:
    """Human-readable amount, e.g. '10.50 USD' or '1495 JPY'."""
    places = MINOR_UNITS[currency]
    major = to_major(amount_minor, currency)
    return f"{major:.{places}f} {currency}"
