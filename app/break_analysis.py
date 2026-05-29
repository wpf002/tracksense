"""
break_analysis.py

Starting-gate break classification. A horse's "break" is how quickly it
leaves the gate when the latch springs — measured as a reaction time in
milliseconds from the gun to clearing the start-gate reader.

Fixed reaction-time bands are the primary verdict; a secondary delta against
the horse's own rolling baseline is computed separately at persist time.
"""

# Fixed reaction-time bands (milliseconds from gun to clearing the start gate)
ANTICIPATED_MAX_MS = 200   # below this the horse pre-empted the latch (too fast)
GOOD_MAX_MS = 450          # clean, well-timed break

VERDICTS = ("anticipated", "good", "slow")


def classify_break(reaction_ms: int) -> str:
    """Classify a break by its reaction time against fixed bands."""
    if reaction_ms < ANTICIPATED_MAX_MS:
        return "anticipated"
    if reaction_ms <= GOOD_MAX_MS:
        return "good"
    return "slow"
