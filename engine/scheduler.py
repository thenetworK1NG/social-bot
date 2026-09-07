import random
import time
from collections import deque


class SmartScheduler:
    """
    Produces realistic inter-post timings with natural clustering:
    sometimes bursts of activity, sometimes long silences.
    Uses a log-normal-ish distribution plus occasional clusters.
    """

    def __init__(self, base_mean=10.0, base_std=6.0):
        self.base_mean = base_mean
        self.base_std = base_std
        self._recent_gaps = deque(maxlen=8)
        self._in_cluster = False
        self._cluster_remaining = 0

    def next_post_delay(self, minutes_window=60) -> int:
        """Return delay in seconds until next post."""
        if self._in_cluster and self._cluster_remaining > 0:
            self._cluster_remaining -= 1
            if self._cluster_remaining == 0:
                self._in_cluster = False
            return random.randint(1, 4) * 60

        gap = random.lognormvariate(2.2, 0.9)
        delay_minutes = max(3.0, min(gap, 30.0))

        # 30% chance to start a cluster (2-3 posts close together)
        if random.random() < 0.30:
            self._in_cluster = True
            self._cluster_remaining = random.randint(1, 2)
            delay_minutes = random.uniform(2, 5)

        self._recent_gaps.append(delay_minutes)
        return int(delay_minutes * 60)


def is_bot_active(personality, now):
    """Check if a bot is likely active right now based on active hours."""
    hour = now.hour
    hours = personality.active_hours
    if hour in hours:
        return True
    # handle overnight ranges like [22,23,0,1] approximated by membership
    return False
