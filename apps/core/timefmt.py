def t12(value):
    """A time of day for people to read: 6:30 PM. Works for datetimes and times.

    Parsing and form values stay 24 hour (`%H:%M`, `datetime-local`); this is for text a person reads.
    """
    return f"{value.hour % 12 or 12}:{value.minute:02d} {'AM' if value.hour < 12 else 'PM'}"
