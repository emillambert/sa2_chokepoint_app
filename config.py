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


# NOTE: The coordinates below represent the actual terminal locations where
# motorcades would depart from the airport terminals before entering public roads.

SCHIPHOL_SCENARIO = Scenario(
    name="schiphol",
    start=(52.3090, 4.7640),  # Schiphol Airport main terminal (Schiphol Plaza)
    via=(52.0930, 4.2867),  # World Forum, The Hague (approx)
    end=(52.0809, 4.3146),  # Mauritshuis, The Hague (approx)
)

ROTTERDAM_THE_HAGUE_SCENARIO = Scenario(
    name="rotterdam_the_hague",
    start=(51.9567, 4.4378),  # Rotterdam/The Hague Airport main terminal
    via=SCHIPHOL_SCENARIO.via,
    end=SCHIPHOL_SCENARIO.end,
)


DEFAULT_SCENARIO = SCHIPHOL_SCENARIO


