"""Invoice totals in the customer's billing currency."""
from dataclasses import dataclass

from payments.currency import convert


@dataclass
class Line:
    description: str
    unit_price_minor: int  # in the line's own currency
    currency: str
    quantity: int = 1


def invoice_total(lines: list[Line], billing_currency: str) -> int:
    """Sum of all lines, each converted to the billing currency, in minor units."""
    return sum(convert(line.unit_price_minor * line.quantity, line.currency, billing_currency)
               for line in lines)
