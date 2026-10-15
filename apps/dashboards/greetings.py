"""The Home greeting: every line, and the Pintu frames played while it is typed.

Pintu is the pixel mascot from pintumcp. His art and timing live in `pintu.json`, copied
from that project (`frames`, `palette`, `tints`, `sequence`, `delay_ms`); this module only
says which of his frames each line plays: a short reaction of two or three beats that ends on the
face he holds while the line is on screen. No two lines react the same way, and the page draws them
as pixels, never smoothed.
"""

import json
from pathlib import Path

PINTU = json.loads((Path(__file__).with_name("pintu.json")).read_text())
FRAMES = tuple(PINTU["frames"])

GREETINGS = {
    "morning": [
        ("Pick the one thing that matters today.", ("question", "thinking", "cool")),
        ("A clear head makes the first hour count.", ("sleepy", "blink", "cool")),
        ("Start with the smallest ticket and build momentum.", ("thinking", "wink", "done")),
        ("Chai first, bugs second.", ("love", "wink", "drink")),
        ("The standup is not going to attend itself.", ("surprised", "dizzy", "sleepy")),
        ("Today's plan: fewer errors, more chai.", ("thinking", "cool", "drink")),
        ("Coffee loaded. Ticket queue loading...", ("drink", "dizzy", "thinking")),
        ("Nobody ever regretted closing a ticket before lunch.", ("wink", "done", "party")),
        ("It worked yesterday. Let's see if it still does.", ("idle", "question", "surprised")),
    ],
    "afternoon": [
        ("Halfway there. Keep the momentum.", ("waveA", "waveB", "cool")),
        ("Close one thing before the next one opens.", ("thinking", "approval", "done")),
        ("A quick DSR line now saves the evening.", ("approval", "thinking", "wink")),
        ("Post-lunch slump detected. Try a small ticket.", ("drink", "blink", "sleepy")),
        ("It is not a bug, it is a surprise feature.", ("surprised", "wink", "party")),
        ("Ctrl+S your good mood.", ("wink", "love", "cool")),
        ("The error log is judging you silently.", ("question", "angry", "sad")),
        ("Tea break is a valid deployment strategy.", ("cool", "drink", "wink")),
        ("Ship it, then tell no one it was a Friday.", ("approval", "cool", "party")),
    ],
    "evening": [
        ("Time to wrap up. Log your day.", ("thinking", "done", "blink")),
        ("Leave tomorrow a clean board.", ("blink", "done", "cool")),
        ("Resolve what you can, hand off the rest.", ("approval", "waveA", "waveB")),
        ("Your DSR is lonely. Give it a line.", ("sad", "question", "love")),
        ("Close the tabs. All forty of them.", ("dizzy", "surprised", "sleepy")),
        ("Future you says thanks for the tidy board.", ("idle", "love", "cool")),
        ("Nothing breaks if you push at 6:29. Probably.", ("cool", "question", "surprised")),
        ("Punch out before the next \"quick fix\" arrives.", ("waveA", "surprised", "angry")),
        ("Git commit, then go home.", ("done", "party", "waveB")),
    ],
    "night": [
        ("Rest counts as work too.", ("thinking", "sleepy", "wink")),
        ("Whatever is left will keep until morning.", ("idle", "blink", "sleepy")),
        ("Log it, then log off.", ("done", "blink", "sleepy")),
        ("The bug will still be there tomorrow. Sadly.", ("dizzy", "sad", "sleepy")),
        ("Sleep is the best garbage collector.", ("cool", "dizzy", "sleepy")),
        ("Working late? The tickets can wait, your eyes cannot.", ("surprised", "drink", "sleepy")),
        ("It is dark outside. Even the cron jobs are asleep.", ("idle", "wink", "sleepy")),
        ("Go to sleep. The error rate will behave tomorrow.", ("cool", "wink", "sleepy")),
        ("Close the laptop, open the biryani.", ("done", "drink", "love")),
    ],
}


def as_json_data():
    """What the page needs: the lines with their frames, and Pintu's own art and timing."""
    return {
        "lines": {period: [{"t": t, "f": list(f)} for t, f in lines] for period, lines in GREETINGS.items()},
        "pintu": PINTU,
    }
