"""The Home greeting: the lines typed under "Good morning", one set per time of day."""

GREETINGS = {
    "morning": [
        "Pick the one thing that matters today.",
        "A clear head makes the first hour count.",
        "Start with the smallest ticket and build momentum.",
        "Chai first, bugs second.",
        "The standup is not going to attend itself.",
        "Today's plan: fewer errors, more chai.",
        "Coffee loaded. Ticket queue loading...",
        "Nobody ever regretted closing a ticket before lunch.",
        "It worked yesterday. Let's see if it still does.",
    ],
    "afternoon": [
        "Halfway there. Keep the momentum.",
        "Close one thing before the next one opens.",
        "A quick DSR line now saves the evening.",
        "Post-lunch slump detected. Try a small ticket.",
        "It is not a bug, it is a surprise feature.",
        "Ctrl+S your good mood.",
        "The error log is judging you silently.",
        "Tea break is a valid deployment strategy.",
        "Ship it, then tell no one it was a Friday.",
    ],
    "evening": [
        "Time to wrap up. Log your day.",
        "Leave tomorrow a clean board.",
        "Resolve what you can, hand off the rest.",
        "Your DSR is lonely. Give it a line.",
        "Close the tabs. All forty of them.",
        "Future you says thanks for the tidy board.",
        "Nothing breaks if you push at 6:29. Probably.",
        "Punch out before the next \"quick fix\" arrives.",
        "Git commit, then go home.",
    ],
    "night": [
        "Rest counts as work too.",
        "Whatever is left will keep until morning.",
        "Log it, then log off.",
        "The bug will still be there tomorrow. Sadly.",
        "Sleep is the best garbage collector.",
        "Working late? The tickets can wait, your eyes cannot.",
        "It is dark outside. Even the cron jobs are asleep.",
        "Go to sleep. The error rate will behave tomorrow.",
        "Close the laptop, open the biryani.",
    ],
}


def as_json_data():
    """What the Home page needs: just the lines for each time of day."""
    return {"lines": {period: list(lines) for period, lines in GREETINGS.items()}}
