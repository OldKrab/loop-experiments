"""Partial and full refunds."""


def refundable(paid_minor: int, refunded_minor: int, requested_minor: int) -> int:
    """How much of `requested_minor` can still be refunded."""
    if requested_minor <= 0:
        raise ValueError("refund amount must be positive")
    return max(0, min(requested_minor, paid_minor))
