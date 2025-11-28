"""Static configuration for the SA2 chokepoint analysis app.

All coordinates use (latitude, longitude) in WGS84.
You can update these to match your specific group assignment
once you know whether you start at Schiphol or Rotterdam/The Hague airport.
"""

from typing import Tuple

LatLon = Tuple[float, float]


class Scenario:
    """Named scenario with fixed waypoints."""

    def __init__(self, name: str, start: LatLon, via: LatLon, end: LatLon) -> None:
        self.name = name
        self.start = start
        self.via = via
        self.end = end


# NOTE: The coordinates below are approximate and intended as sensible defaults.
# You should refine them during your own reconnaissance for the assignment.

SCHIPHOL_SCENARIO = Scenario(
    name="schiphol",
    start=(52.3105, 4.7683),  # Schiphol Airport (approx)
    via=(52.0930, 4.2867),  # World Forum, The Hague (approx)
    end=(52.0809, 4.3146),  # Mauritshuis, The Hague (approx)
)

ROTTERDAM_THE_HAGUE_SCENARIO = Scenario(
    name="rotterdam_the_hague",
    start=(51.9569, 4.4372),  # Rotterdam/The Hague Airport (approx)
    via=SCHIPHOL_SCENARIO.via,
    end=SCHIPHOL_SCENARIO.end,
)


DEFAULT_SCENARIO = SCHIPHOL_SCENARIO


