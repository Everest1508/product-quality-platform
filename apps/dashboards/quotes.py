"""Short lines for the home page. Plain sentences, no attributions, so none of
them can be pinned on someone who never said it."""

import random

QUOTES = [
    "Small steps every day still add up to a finished product.",
    "Fix the thing in front of you, then pick the next one.",
    "A bug you understand is already half fixed.",
    "Done and shipped beats perfect and waiting.",
    "Write it down. Future you will not remember why.",
    "The quiet days are when the good work gets finished.",
    "Ask the question. Someone else was about to.",
    "Clear tickets, clear head.",
    "Progress is rarely loud. Keep going.",
    "Every resolved error is one less 3am message.",
    "Start with the smallest piece you can finish before lunch.",
    "Good teams make each other's days easier. Be that.",
    "You do not need the whole plan to take the first step.",
    "Tired code is slow code. Take your break.",
    "Say thanks when someone unblocks you.",
    "Rework is what rushing costs. Take the extra minute.",
    "Today's boring fix is next week's calm release.",
    "Be kind in code review. Be curious too.",
    "The best feature is the one that works on the first try.",
    "Finish one thing properly before starting three.",
    "Leave the code a little cleaner than you found it.",
    "A short, honest status update helps more than a long one.",
    "Rest is part of the job.",
    "Measure first, then guess less.",
    "Your work matters to the person who will use it.",
]


def pick(seed=None, exclude=None):
    """The same quote all day for a given seed, or a random one other than ``exclude``."""
    if seed is not None:
        return QUOTES[seed % len(QUOTES)]
    choices = [q for q in QUOTES if q != exclude] or QUOTES
    return random.choice(choices)
