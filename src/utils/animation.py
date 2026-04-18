"""Animation timing helpers."""


def is_blink_visible(timer: float, interval: float) -> bool:
    """Return True during the 'on' phase of a 2*interval blink cycle.

    A blink cycle is 2*interval long: the first half is visible,
    the second half is hidden.
    """
    return timer % (interval * 2) < interval
