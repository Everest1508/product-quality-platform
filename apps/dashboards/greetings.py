"""The Home greeting: every line, and the Pintu frames played while it is typed.

Pintu is the pixel mascot from pintumcp. His art and timing live in `pintu.json`, copied
from that project (`frames`, `palette`, `tints`, `sequence`, `delay_ms`); this module only
says which of his frames each line plays, in order, on a loop. No two lines play the same
frames, and the page draws them as pixels, never smoothed.
"""

import json
from pathlib import Path

PINTU = json.loads((Path(__file__).with_name("pintu.json")).read_text())
FRAMES = tuple(PINTU["frames"])

GREETINGS = {
    "morning": [
        ("Pick the one thing that matters today.", ("thinking", "idle", "thinking", "blink")),
        ("A clear head makes the first hour count.", ("idle", "blink", "idle", "cool")),
        ("Start with the smallest ticket and build momentum.", ("question", "thinking", "idle", "done")),
        ("Chai first, bugs second.", ("drink", "drink", "love", "drink")),
        ("The standup is not going to attend itself.", ("sleepy", "idle", "sleepy", "surprised")),
        ("Today's plan: fewer errors, more chai.", ("drink", "cool", "drink", "party")),
        ("Coffee loaded. Ticket queue loading...", ("thinking", "thinking", "blink", "dizzy")),
        ("Nobody ever regretted closing a ticket before lunch.", ("done", "party", "done", "cool")),
        ("It worked yesterday. Let's see if it still does.", ("surprised", "question", "thinking", "blink")),
    ],
    "afternoon": [
        ("Halfway there. Keep the momentum.", ("waveA", "waveB", "cool", "idle")),
        ("Close one thing before the next one opens.", ("thinking", "done", "idle", "thinking")),
        ("A quick DSR line now saves the evening.", ("idle", "wink", "thinking", "wink")),
        ("Post-lunch slump detected. Try a small ticket.", ("sleepy", "sleepy", "idle", "sleepy")),
        ("It is not a bug, it is a surprise feature.", ("surprised", "wink", "party", "wink")),
        ("Ctrl+S your good mood.", ("love", "idle", "love", "wink")),
        ("The error log is judging you silently.", ("question", "angry", "idle", "blink")),
        ("Tea break is a valid deployment strategy.", ("drink", "idle", "drink", "wink")),
        ("Ship it, then tell no one it was a Friday.", ("cool", "party", "cool", "wink")),
    ],
    "evening": [
        ("Time to wrap up. Log your day.", ("thinking", "done", "idle", "done")),
        ("Leave tomorrow a clean board.", ("blink", "done", "idle", "cool")),
        ("Resolve what you can, hand off the rest.", ("approval", "idle", "waveA", "waveB")),
        ("Your DSR is lonely. Give it a line.", ("sad", "idle", "sad", "love")),
        ("Close the tabs. All forty of them.", ("dizzy", "surprised", "dizzy", "idle")),
        ("Future you says thanks for the tidy board.", ("love", "cool", "love", "blink")),
        ("Nothing breaks if you push at 6:29. Probably.", ("surprised", "cool", "surprised", "wink")),
        ("Punch out before the next \"quick fix\" arrives.", ("surprised", "angry", "idle", "approval")),
        ("Git commit, then go home.", ("done", "waveA", "waveB", "party")),
    ],
    "night": [
        ("Rest counts as work too.", ("idle", "sleepy", "blink", "sleepy")),
        ("Whatever is left will keep until morning.", ("thinking", "sleepy", "idle", "sleepy")),
        ("Log it, then log off.", ("done", "sleepy", "done", "sleepy")),
        ("The bug will still be there tomorrow. Sadly.", ("sad", "dizzy", "sad", "idle")),
        ("Sleep is the best garbage collector.", ("sleepy", "dizzy", "sleepy", "cool")),
        ("Working late? The tickets can wait, your eyes cannot.", ("sleepy", "surprised", "sleepy", "drink")),
        ("It is dark outside. Even the cron jobs are asleep.", ("idle", "sleepy", "wink", "sleepy")),
        ("Go to sleep. The error rate will behave tomorrow.", ("cool", "sleepy", "wink", "sleepy")),
        ("Close the laptop, open the biryani.", ("drink", "party", "love", "drink")),
    ],
}


def as_json_data():
    """What the page needs: the lines with their frames, and Pintu's own art and timing."""
    return {
        "lines": {period: [{"t": t, "f": list(f)} for t, f in lines] for period, lines in GREETINGS.items()},
        "pintu": PINTU,
    }
