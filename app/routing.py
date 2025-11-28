from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import networkx as nx
import osmnx as ox
from osmnx import distance as ox_distance
import logging

from .models import Route

LatLon = Tuple[float, float]

# Configure OSMnx caching so we don't keep refetching the same tiles.
BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)
ox.settings.cache_folder = str(CACHE_DIR)
ox.settings.use_cache = True
ox.settings.timeout = 60  # seconds
ox.settings.log_console = False

GRAPH_CACHE_FILE = CACHE_DIR / "the_hague.graphml"
logger = logging.getLogger(__name__)


def build_graph(center: LatLon, dist_m: int = 20000) -> nx.MultiDiGraph:
    """Download and build a drivable road network around the given center.

    The graph is cached by osmnx internally so repeated calls are cheap when
    the user runs the app multiple times.
    """

    if GRAPH_CACHE_FILE.exists():
        logger.info("Loading cached road network from %s", GRAPH_CACHE_FILE)
        return ox.load_graphml(GRAPH_CACHE_FILE)

    logger.info("Downloading road network from OSM (dist=%sm)", dist_m)
    G = ox.graph_from_point(center, dist=dist_m, network_type="drive")
    G = ox_distance.add_edge_lengths(G)
    ox.save_graphml(G, GRAPH_CACHE_FILE)
    logger.info("Road network downloaded and cached (%d nodes)", len(G.nodes))
    return G


def _node_for_point(G: nx.MultiDiGraph, point: LatLon) -> int:
    """Find the nearest graph node for a given (lat, lon) point."""
    lat, lon = point
    return ox.nearest_nodes(G, lon, lat)


def _path_length(G: nx.MultiDiGraph, path: List[int]) -> float:
    """Compute the total length of a path in meters."""
    length = 0.0
    for u, v in zip(path[:-1], path[1:]):
        data = min(G.get_edge_data(u, v).values(), key=lambda d: d.get("length", 0))
        length += float(data.get("length", 0.0))
    return length


def _path_to_coords(G: nx.MultiDiGraph, path: List[int]) -> List[LatLon]:
    return [(float(G.nodes[n]["y"]), float(G.nodes[n]["x"])) for n in path]


def _nodes_metadata(G: nx.MultiDiGraph, path: List[int]) -> List[Dict]:
    """Light-weight per-node metadata used later for chokepoint analysis."""
    meta: List[Dict] = []
    for n in path:
        degree = int(G.degree[n])
        meta.append(
            {
                "id": int(n),
                "is_intersection": degree > 2,
                "degree": degree,
            }
        )
    return meta


def _edges_metadata(G: nx.MultiDiGraph, path: List[int]) -> List[Dict]:
    """Light-weight per-edge metadata for risk heuristics."""
    meta: List[Dict] = []
    for idx, (u, v) in enumerate(zip(path[:-1], path[1:])):
        data = min(G.get_edge_data(u, v).values(), key=lambda d: d.get("length", 0))
        highway = _normalize_highway(data.get("highway"))
        tunnel = _has_attr(data.get("tunnel"), {"yes", "building_passage"})
        bridge = _has_attr(data.get("bridge"), {"yes", "viaduct"})
        meta.append(
            {
                "index": idx,
                "u": int(u),
                "v": int(v),
                "highway": highway,
                "is_tunnel": tunnel,
                "is_bridge": bridge,
                "length": float(data.get("length", 0.0)),
            }
        )
    return meta


def _normalize_highway(value: Any) -> str:
    """Highway tags can be strings, lists or missing."""
    if isinstance(value, list):
        return str(value[0])
    if isinstance(value, tuple):
        return str(value[0])
    if value is None:
        return ""
    return str(value)


def _has_attr(value: Any, allowed: set[str]) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set)):
        return any(str(v) in allowed for v in value)
    return str(value) in allowed


def _extract_edge_attrs(data: Any) -> Dict:
    """Normalize edge data for both simple and multi graphs.

    NetworkX passes a single attribute dict for DiGraph edges but a mapping of
    edge keys -> attribute dicts for Multi(Di)Graphs. We always want the
    attribute dict, selecting the lowest-length edge if multiple exist.
    """

    if not isinstance(data, dict):
        return {}

    if data and all(isinstance(v, dict) for v in data.values()):
        # MultiDiGraph: choose the edge with the smallest length (fallback 0).
        return min(data.values(), key=lambda d: d.get("length", 0))

    return data


def _estimate_turns(G: nx.MultiDiGraph, path: List[int]) -> int:
    # Simple proxy: treat each node with degree > 2 as a potential turn.
    turns = 0
    for n in path[1:-1]:
        if G.degree[n] > 2:
            turns += 1
    return turns


def _route_from_path(
    G: nx.MultiDiGraph, path: List[int], route_id: str, label: str, kind: str
) -> Dict:
    length_m = _path_length(G, path)
    coords = _path_to_coords(G, path)
    turns = _estimate_turns(G, path)
    # A simple baseline risk score will be refined later in the analysis module.
    risk_score = 0.0
    description = ""
    route = Route(
        id=route_id,
        label=label,
        kind=kind,  # type: ignore[arg-type]
        path=coords,
        length_m=length_m,
        estimated_time_min=None,
        turn_count=turns,
        risk_score=risk_score,
        description=description,
    )
    # Extend with routing metadata that the analysis module can use later.
    payload = asdict(route)
    payload["nodes"] = [int(n) for n in path]
    payload["nodes_meta"] = _nodes_metadata(G, path)
    payload["edges_meta"] = _edges_metadata(G, path)
    return payload


def _shortest_route(G: nx.MultiDiGraph, start: int, via: int, end: int) -> List[int]:
    """Compute the globally shortest route via the conference location."""
    path1 = nx.shortest_path(G, start, via, weight="length")
    path2 = nx.shortest_path(G, via, end, weight="length")
    return path1 + path2[1:]


def _logical_route(
    G: nx.MultiDiGraph, start: int, via: int, end: int, avoid_edges: set[Tuple[int, int]]
) -> List[int]:
    """Favor higher-category roads and fewer turns using a custom weight."""

    def edge_weight(u: int, v: int, data: Dict) -> float:
        attrs = _extract_edge_attrs(data)
        base = float(attrs.get("length", 1.0))
        highway = _normalize_highway(attrs.get("highway"))
        # Prefer motorways and trunks slightly by making them effectively shorter.
        if highway in {"motorway", "trunk"}:
            base *= 0.7
        elif highway in {"primary", "secondary"}:
            base *= 0.85

        if (u, v) in avoid_edges:
            base *= 5.0
        return base

    path1 = nx.shortest_path(G, start, via, weight=edge_weight)
    path2 = nx.shortest_path(G, via, end, weight=edge_weight)
    return path1 + path2[1:]


def _safest_route(
    G: nx.MultiDiGraph, start: int, via: int, end: int, avoid_edges: set[Tuple[int, int]]
) -> List[int]:
    """Avoid tunnels and narrow residential streets where possible."""

    def edge_weight(u: int, v: int, data: Dict) -> float:
        attrs = _extract_edge_attrs(data)
        base = float(attrs.get("length", 1.0))
        highway = _normalize_highway(attrs.get("highway"))
        tunnel = _has_attr(attrs.get("tunnel"), {"yes", "building_passage"})

        if tunnel:
            base *= 3.0
        if highway in {"living_street", "residential"}:
            base *= 1.6
        elif highway in {"motorway", "trunk"}:
            base *= 0.9

        if (u, v) in avoid_edges:
            base *= 5.0
        return base

    path1 = nx.shortest_path(G, start, via, weight=edge_weight)
    path2 = nx.shortest_path(G, via, end, weight=edge_weight)
    return path1 + path2[1:]


def _edge_set(path: List[int]) -> set[Tuple[int, int]]:
    return {(u, v) for u, v in zip(path[:-1], path[1:])}


def compute_routes(start: LatLon, via: LatLon, end: LatLon) -> Dict[str, Dict]:
    """Compute three distinct routes (shortest, logical, safest) between waypoints.

    Returns a JSON-serialisable dictionary for easy use in the API layer.
    """
    try:
        logger.info("Computing routes between %s -> %s -> %s", start, via, end)
        # Use the via point as rough center for the graph.
        G = build_graph(via)
        start_n = _node_for_point(G, start)
        via_n = _node_for_point(G, via)
        end_n = _node_for_point(G, end)
        logger.info(
            "Graph nodes resolved: start=%s via=%s end=%s (nodes=%d edges=%d)",
            start_n,
            via_n,
            end_n,
            len(G.nodes),
            len(G.edges),
        )

        logger.info("Computing shortest route")
        shortest_path = _shortest_route(G, start_n, via_n, end_n)
        shortest_edges = _edge_set(shortest_path)

        logger.info("Computing logical route")
        logical_path = _logical_route(
            G, start_n, via_n, end_n, avoid_edges=shortest_edges
        )
        logical_edges = _edge_set(logical_path)

        logger.info("Computing safest route")
        # Penalise edges already used by previous routes to encourage diversity.
        avoid_for_safest = shortest_edges | logical_edges
        safest_path = _safest_route(
            G, start_n, via_n, end_n, avoid_edges=avoid_for_safest
        )

        routes = {
            "r_shortest": _route_from_path(
                G, shortest_path, "r_shortest", "Shortest route", "shortest"
            ),
            "r_logical": _route_from_path(
                G, logical_path, "r_logical", "Most logical route", "logical"
            ),
            "r_safest": _route_from_path(
                G, safest_path, "r_safest", "Safest route", "safest"
            ),
        }
        logger.info("Route computation finished successfully")
        return routes
    except Exception as exc:
        # In constrained environments (no network, Overpass downtime, etc.),
        # return a lightweight built-in fallback so the UI remains usable.
        logger.exception("Routing failed; falling back to sample routes")
        return _sample_routes()


def _sample_routes() -> Dict[str, Dict]:
    """Fallback route geometries covering the Schiphol → Hague scenario."""

    def build_route(
        route_id: str,
        label: str,
        kind: str,
        coords: List[LatLon],
        length_m: float,
        turns: int,
        description: str,
    ) -> Dict:
        nodes: List[int] = []
        nodes_meta: List[Dict] = []
        chokepoint_coords = {
            (52.3105, 4.7683),  # Airport
            (52.0930, 4.2867),  # World Forum
            (52.0809, 4.3146),  # Mauritshuis
        }

        for lat, lon in coords:
            node_id = hash((round(lat, 4), round(lon, 4)))
            is_intersection = (lat, lon) in chokepoint_coords
            nodes.append(node_id)
            nodes_meta.append(
                {
                    "id": node_id,
                    "is_intersection": is_intersection,
                    "degree": 3 if is_intersection else 2,
                }
            )

        edges_meta: List[Dict] = []
        if len(coords) > 1:
            segment_len = length_m / (len(coords) - 1)
            for idx in range(len(coords) - 1):
                edges_meta.append(
                    {
                        "index": idx,
                        "u": nodes[idx],
                        "v": nodes[idx + 1],
                        "highway": "motorway" if idx < 3 else "primary",
                        "is_tunnel": False,
                        "is_bridge": False,
                        "length": segment_len,
                    }
                )

        return {
            "id": route_id,
            "label": label,
            "kind": kind,
            "path": coords,
            "length_m": length_m,
            "estimated_time_min": length_m / 1000 / 1.2,  # assume 72 km/h
            "turn_count": turns,
            "risk_score": 2.5,
            "description": description,
            "nodes": nodes,
            "nodes_meta": nodes_meta,
            "edges_meta": edges_meta,
        }

    routes = {
        "r_shortest": build_route(
            "r_shortest",
            "Shortest route (fallback)",
            "shortest",
            [
                (52.3105, 4.7683),
                (52.239, 4.708),
                (52.184, 4.553),
                (52.120, 4.420),
                (52.0930, 4.2867),
                (52.085, 4.300),
                (52.0809, 4.3146),
            ],
            47000,
            18,
            "Fallback baseline path using major A4/A12 corridors.",
        ),
        "r_logical": build_route(
            "r_logical",
            "Most logical route (fallback)",
            "logical",
            [
                (52.3105, 4.7683),
                (52.287, 4.755),
                (52.220, 4.650),
                (52.160, 4.480),
                (52.120, 4.420),
                (52.100, 4.330),
                (52.0930, 4.2867),
                (52.0809, 4.3146),
            ],
            49500,
            15,
            "Fallback route prioritising wide arterial roads with fewer turns.",
        ),
        "r_safest": build_route(
            "r_safest",
            "Safest route (fallback)",
            "safest",
            [
                (52.3105, 4.7683),
                (52.330, 4.750),
                (52.280, 4.620),
                (52.210, 4.500),
                (52.150, 4.380),
                (52.120, 4.340),
                (52.0930, 4.2867),
                (52.085, 4.300),
                (52.0809, 4.3146),
            ],
            52000,
            20,
            "Fallback route avoiding tunnels/underpasses by swinging north then west.",
        ),
    }
    logger.info(
        "Returning %d fallback routes (no live OSM data available)", len(routes)
    )
    return routes




