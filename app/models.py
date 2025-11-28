from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Tuple

LatLon = Tuple[float, float]


RouteType = Literal["shortest", "logical", "safest"]


@dataclass
class Route:
    id: str
    label: str
    kind: RouteType
    path: List[LatLon]
    length_m: float
    estimated_time_min: float | None
    turn_count: int
    risk_score: float
    description: str


@dataclass
class Chokepoint:
    id: str
    location: LatLon
    type: str
    routes_affected: List[str]
    vulnerability_score: float
    factors: List[str]
    description: str


@dataclass
class PointOfInterest:
    id: str
    type: Literal[
        "ambush_location",
        "enemy_firing_point",
        "enemy_observation_point",
        "surveillance_point",
    ]
    location: LatLon
    related_route: str | None
    related_chokepoint: str | None
    description: str


@dataclass
class SecurityTeamPlacement:
    id: str
    type: Literal["SDT", "CS"]
    location: LatLon
    assigned_to: str | None
    role_description: str


