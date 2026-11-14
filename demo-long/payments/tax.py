"""VAT on invoice amounts."""
from decimal import Decimal

# Standard VAT rate per customer country.
VAT_RATES = {"DE": Decimal("0.19"), "FR": Decimal("0.20"), "GB": Decimal("0.20"), "JP": Decimal("0.10")}


def vat_minor(net_minor: int, country: str) -> int:
    """VAT due on a net amount, in the same currency's minor units."""
    if country not in VAT_RATES:
        raise ValueError(f"no VAT rate for country: {country}")
    return int(Decimal(net_minor) * VAT_RATES[country])


def gross_minor(net_minor: int, country: str) -> int:
    """Net amount plus VAT."""
    return net_minor + vat_minor(net_minor, country)
