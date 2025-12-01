from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import math
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

# Priority order: precomputed (repo-included) -> cache (runtime) -> download (fallback)
logger = logging.getLogger(__name__)


def build_graph(center: LatLon, dist_m: int = 20000, scenario_name: str = "default") -> nx.MultiDiGraph:
    """Download and build a drivable road network around the given center.

    The graph is cached by osmnx internally so repeated calls are cheap when
    the user runs the app multiple times.
    """

    # Priority 1: Unified graph (covers everything - new approach)
    UNIFIED_GRAPH_FILE = BASE_DIR / "precomputed" / "unified_graph.graphml"
    if UNIFIED_GRAPH_FILE.exists():
        logger.info("Loading unified road network from %s", UNIFIED_GRAPH_FILE)
        return ox.load_graphml(UNIFIED_GRAPH_FILE)

    # Priority 2: Scenario-specific precomputed graphs (fallback)
    PRECOMPUTED_GRAPH_FILE = BASE_DIR / "precomputed" / f"{scenario_name}_graph.graphml"
    if PRECOMPUTED_GRAPH_FILE.exists():
        logger.info("Loading scenario-specific graph from %s", PRECOMPUTED_GRAPH_FILE)
        return ox.load_graphml(PRECOMPUTED_GRAPH_FILE)

    # Priority 3: Runtime cache
    GRAPH_CACHE_FILE = CACHE_DIR / f"{scenario_name}_graph.graphml"
    if GRAPH_CACHE_FILE.exists():
        logger.info("Loading cached road network from %s", GRAPH_CACHE_FILE)
        return ox.load_graphml(GRAPH_CACHE_FILE)

    logger.info("Downloading road network from OSM (dist=%sm)", dist_m)
    # Get the full road network with high resolution geometries
    G = ox.graph_from_point(center, dist=dist_m, network_type="drive", simplify=False)
    G = ox_distance.add_edge_lengths(G)

    # Filter out roads that are unsuitable for motorcades
    # Remove pedestrian-only ways, cycleways, and minor roads to force major road usage
    edges_to_remove = []
    for u, v, k, data in G.edges(keys=True, data=True):
        highway = _normalize_highway(data.get("highway", ""))
        # Remove paths that aren't suitable for motorcade routes
        if highway in {"footway", "pedestrian", "cycleway", "path", "steps", "track"}:
            edges_to_remove.append((u, v, k))
        # Remove residential streets and living streets (too narrow for motorcades)
        elif highway in {"residential", "living_street", "unclassified"}:
            edges_to_remove.append((u, v, k))
        # Remove service roads that are likely to be narrow alleys
        elif highway == "service":
            edges_to_remove.append((u, v, k))
        # Remove tertiary roads unless they're important connectors
        elif highway == "tertiary":
            # Keep some tertiary roads that connect major routes, but penalize them heavily
            pass  # We'll handle tertiary roads in the weighting instead

    for u, v, k in edges_to_remove:
        if G.has_edge(u, v, k):
            G.remove_edge(u, v, k)

    # Remove isolated nodes (nodes with no edges)
    isolated_nodes = [node for node in G.nodes() if G.degree(node) == 0]
    G.remove_nodes_from(isolated_nodes)

    ox.save_graphml(G, GRAPH_CACHE_FILE)
    logger.info("Road network downloaded, filtered and cached (%d nodes, %d edges)",
                len(G.nodes), len(G.edges))
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
    """Extract coordinates that perfectly follow road geometries, not just node points."""
    coords = []

    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]

        # Get edge data (handle MultiDiGraph)
        edge_data = G.get_edge_data(u, v)
        if not edge_data:
            continue

        # Get the edge with the shortest length (or any if no length data)
        edge = min(edge_data.values(), key=lambda d: d.get("length", 0))

        # Check if edge has geometry data
        if "geometry" in edge and edge["geometry"] is not None:
            # Use the full road geometry
            geometry = edge["geometry"]
            # Convert shapely LineString to coordinate list
            edge_coords = list(geometry.coords)
            # Convert to (lat, lon) tuples
            edge_coords = [(float(coord[1]), float(coord[0])) for coord in edge_coords]

            # Add coordinates, but avoid duplicating the connection point
            if coords:
                # Skip the first coordinate if it matches the last one added
                start_idx = 1 if edge_coords and coords[-1] == edge_coords[0] else 0
                coords.extend(edge_coords[start_idx:])
            else:
                coords.extend(edge_coords)
        else:
            # Fallback: use node coordinates if no geometry available
            if not coords or coords[-1] != (float(G.nodes[u]["y"]), float(G.nodes[u]["x"])):
                coords.append((float(G.nodes[u]["y"]), float(G.nodes[u]["x"])))
            if i == len(path) - 2:  # Last edge
                coords.append((float(G.nodes[v]["y"]), float(G.nodes[v]["x"])))

    return coords


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
    """Estimate the number of turns in a path by analyzing node connectivity."""
    turns = 0
    for i in range(1, len(path) - 1):
        node = path[i]
        # A turn occurs at intersections with multiple possible directions
        if G.degree[node] > 2:
            turns += 1
    return turns


def _route_from_path(
    G: nx.MultiDiGraph, path: List[int], route_id: str, label: str, kind: str
) -> Dict:
    length_m = _path_length(G, path)
    coords = _path_to_coords(G, path)
    turns = _estimate_turns(G, path)

    # Check for tunnels on the route
    tunnels = _check_tunnels_on_route(G, path)

    # A simple baseline risk score will be refined later in the analysis module.
    risk_score = 0.0

    # Build description with tunnel information
    description_parts = []
    if tunnels:
        tunnel_count = len(tunnels)
        total_tunnel_length = sum(t["length_m"] for t in tunnels)
        description_parts.append(f"Contains {tunnel_count} tunnel(s) with total length {total_tunnel_length:.0f}m")
        if tunnel_count <= 2:  # Only detail short tunnel routes
            tunnel_names = [t["road_name"] for t in tunnels]
            description_parts.append(f"Tunnels: {', '.join(tunnel_names)}")

    description = ". ".join(description_parts) if description_parts else ""

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
    # Use A* with straight-line distance heuristic for better performance
    def heuristic(u, v):
        # Simple Euclidean distance as heuristic
        u_coords = (G.nodes[u]['y'], G.nodes[u]['x'])
        v_coords = (G.nodes[v]['y'], G.nodes[v]['x'])
        return ox.distance.great_circle(u_coords[0], u_coords[1], v_coords[0], v_coords[1])

    try:
        path1 = nx.astar_path(G, start, via, heuristic=heuristic, weight="length")
        path2 = nx.astar_path(G, via, end, heuristic=heuristic, weight="length")
    except nx.NetworkXNoPath:
        # Fallback to Dijkstra if A* fails
        path1 = nx.shortest_path(G, start, via, weight="length")
        path2 = nx.shortest_path(G, via, end, weight="length")

    return path1 + path2[1:]


def _calculate_turn_angle(G: nx.MultiDiGraph, prev_u: int, u: int, v: int) -> float:
    """Calculate the turning angle at node u when going from prev_u to v."""
    if prev_u == u or u == v:
        return 0.0

    # Get coordinates
    prev_coords = (G.nodes[prev_u]['x'], G.nodes[prev_u]['y'])
    u_coords = (G.nodes[u]['x'], G.nodes[u]['y'])
    v_coords = (G.nodes[v]['x'], G.nodes[v]['y'])

    # Calculate vectors
    vec1 = (u_coords[0] - prev_coords[0], u_coords[1] - prev_coords[1])
    vec2 = (v_coords[0] - u_coords[0], v_coords[1] - u_coords[1])

    # Calculate angle using dot product
    dot_product = vec1[0] * vec2[0] + vec1[1] * vec2[1]
    mag1 = (vec1[0]**2 + vec1[1]**2)**0.5
    mag2 = (vec2[0]**2 + vec2[1]**2)**0.5

    if mag1 == 0 or mag2 == 0:
        return 0.0

    cos_angle = dot_product / (mag1 * mag2)
    cos_angle = max(-1, min(1, cos_angle))  # Clamp to avoid floating point errors

    angle = abs(math.acos(cos_angle))
    return angle


def _logical_route(
    G: nx.MultiDiGraph, start: int, via: int, end: int, avoid_edges: set[Tuple[int, int]]
) -> List[int]:
    """Favor higher-category roads and fewer turns using a custom weight."""

    def edge_weight(u: int, v: int, data: Dict) -> float:
        attrs = _extract_edge_attrs(data)
        base = float(attrs.get("length", 1.0))
        highway = _normalize_highway(attrs.get("highway"))

        # Strong preference for highways and major roads
        if highway in {"motorway", "trunk"}:
            base *= 0.6  # Strong preference for highways
        elif highway == "primary":
            base *= 0.75  # Good preference for primary roads
        elif highway == "secondary":
            base *= 0.85  # Moderate preference for secondary roads
        elif highway == "tertiary":
            base *= 0.95  # Slight preference for tertiary roads
        elif highway in {"residential", "living_street"}:
            base *= 1.3  # Penalty for residential streets
        elif highway == "service":
            base *= 1.5  # Strong penalty for service roads

        if (u, v) in avoid_edges:
            base *= 4.0  # Reduced penalty to allow some overlap but discourage it
        return base

    # Use A* for better pathfinding with turn penalties
    def astar_edge_weight(u, v, data):
        base_weight = edge_weight(u, v, data)
        # Add turn penalty if we can determine it (this is simplified)
        # In a full implementation, you'd track the previous edge
        return base_weight

    try:
        path1 = nx.astar_path(G, start, via, weight=astar_edge_weight)
        path2 = nx.astar_path(G, via, end, weight=astar_edge_weight)
    except nx.NetworkXNoPath:
        # Fallback to regular shortest path
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
        bridge = _has_attr(attrs.get("bridge"), {"yes", "viaduct"})

        # Heavy penalties for dangerous infrastructure
        if tunnel:
            base *= 5.0  # Strong avoidance of tunnels
        if bridge:
            base *= 2.5  # Moderate avoidance of bridges (they can be choke points)

        # Road type preferences for safety
        if highway in {"motorway", "trunk"}:
            base *= 0.8  # Slight preference for controlled highways
        elif highway == "primary":
            base *= 0.9  # Slight preference for primary roads
        elif highway == "secondary":
            base *= 1.0  # Neutral for secondary roads
        elif highway == "tertiary":
            base *= 1.2  # Slight penalty for tertiary roads
        elif highway in {"residential", "living_street"}:
            base *= 2.0  # Strong penalty for residential areas
        elif highway == "service":
            base *= 3.0  # Heavy penalty for service roads

        # Avoid complex intersections
        if G.degree[u] > 3 or G.degree[v] > 3:
            base *= 1.3  # Penalty for complex intersections

        if (u, v) in avoid_edges:
            base *= 3.0  # Allow some reuse but discourage it
        return base

    try:
        path1 = nx.astar_path(G, start, via, weight=edge_weight)
        path2 = nx.astar_path(G, via, end, weight=edge_weight)
    except nx.NetworkXNoPath:
        # Fallback to regular shortest path
        path1 = nx.shortest_path(G, start, via, weight=edge_weight)
        path2 = nx.shortest_path(G, via, end, weight=edge_weight)

    return path1 + path2[1:]


def _safe_route_manual(G: nx.MultiDiGraph, start: int, via: int, end: int) -> List[int]:
    """Manually defined safe route following specific road segments.

    Route segments: A16-N209-A12-Konningskade-Hubertus Viaduct-S100-Korte Voorhout
    This function tries to find edges matching these road names and connect them.
    """
    # Road segments to match (in order)
    road_segments = [
        "A16", "N209", "A12", "Koninginnegracht", "Hubertus Viaduct",
        "S100", "Korte Voorhout"
    ]

    # Alternative names that might appear in OSM
    road_alternatives = {
        "A16": ["A16", "A 16", "rijksweg 16"],
        "N209": ["N209", "N 209", "rijksweg 209"],
        "A12": ["A12", "A 12", "rijksweg 12"],
        "Koninginnegracht": ["Koninginnegracht", "Koninginne gracht", "Koningskade"],
        "Hubertus Viaduct": ["Hubertus Viaduct", "Hubertusviaduct", "Hubertus"],
        "S100": ["S100", "S 100", "provincialeweg 100"],
        "Korte Voorhout": ["Korte Voorhout", "Kortevoorhout"]
    }

    def matches_road_name(edge_data: Dict, target_roads: List[str]) -> bool:
        """Check if edge name matches any of the target road names."""
        highway_name = _normalize_highway(edge_data.get("name", ""))
        highway_ref = _normalize_highway(edge_data.get("ref", ""))

        for target in target_roads:
            # Check exact matches and case-insensitive matches
            if (highway_name and target.lower() in highway_name.lower()) or \
               (highway_ref and target.lower() in highway_ref.lower()):
                return True
        return False

    # Find all edges that match our road segments
    segment_edges = {segment: [] for segment in road_segments}

    for u, v, k, data in G.edges(keys=True, data=True):
        for segment, alternatives in road_alternatives.items():
            if matches_road_name(data, alternatives):
                segment_edges[segment].append((u, v, k))

    # Try to build a path by connecting segments
    path = []
    current_node = start

    # First, get from start to the first road segment
    try:
        path_to_first = nx.shortest_path(G, current_node, via, weight="length")
        path.extend(path_to_first[:-1])  # Don't duplicate the via node
    except nx.NetworkXNoPath:
        # If direct path fails, use a basic approach
        path.append(current_node)

    # For each road segment, find the closest edge and add it
    for segment in road_segments:
        edges = segment_edges.get(segment, [])
        if not edges:
            logger.warning(f"No edges found for road segment: {segment}")
            continue

        # Find the closest edge to current position
        min_distance = float('inf')
        best_edge = None

        for u, v, k in edges:
            try:
                # Distance from current node to edge start
                dist_u = nx.shortest_path_length(G, current_node, u, weight="length")
                if dist_u < min_distance:
                    min_distance = dist_u
                    best_edge = (u, v, k)
            except nx.NetworkXNoPath:
                continue

        if best_edge:
            u, v, k = best_edge
            # Add path to reach this edge
            if current_node != u:
                try:
                    sub_path = nx.shortest_path(G, current_node, u, weight="length")
                    path.extend(sub_path[1:])  # Skip current node to avoid duplication
                except nx.NetworkXNoPath:
                    # Skip this edge if unreachable
                    continue

            # Add the edge nodes
            if path and path[-1] != u:
                path.append(u)
            path.append(v)
            current_node = v

    # Finally, get from last segment to end
    try:
        path_to_end = nx.shortest_path(G, current_node, end, weight="length")
        if path and path[-1] == path_to_end[0]:
            path.extend(path_to_end[1:])
        else:
            path.extend(path_to_end)
    except nx.NetworkXNoPath:
        # If we can't reach the end, at least include the end node
        if end not in path:
            path.append(end)

    # Remove duplicates that might have been introduced
    cleaned_path = []
    for node in path:
        if not cleaned_path or cleaned_path[-1] != node:
            cleaned_path.append(node)

    # Ensure we have at least start and end
    if not cleaned_path:
        cleaned_path = [start, end]
    elif cleaned_path[0] != start:
        cleaned_path.insert(0, start)
    if cleaned_path[-1] != end:
        cleaned_path.append(end)

    logger.info(f"Manual safe route: found {len(cleaned_path)} nodes through {len(road_segments)} road segments")
    return cleaned_path


def _check_tunnels_on_route(G: nx.MultiDiGraph, path: List[int]) -> List[Dict]:
    """Check for tunnels and underpasses on a route and return details."""
    tunnels = []

    for idx, (u, v) in enumerate(zip(path[:-1], path[1:])):
        edge_data = min(G.get_edge_data(u, v).values(), key=lambda d: d.get("length", 0))
        tunnel = _has_attr(edge_data.get("tunnel"), {"yes", "building_passage"})

        if tunnel:
            highway_name = _normalize_highway(edge_data.get("name", ""))
            highway_ref = _normalize_highway(edge_data.get("ref", ""))
            road_name = highway_name or highway_ref or "Unnamed road"

            tunnels.append({
                "index": idx,
                "road_name": road_name,
                "length_m": float(edge_data.get("length", 0)),
                "coordinates": [(G.nodes[u]["y"], G.nodes[u]["x"]), (G.nodes[v]["y"], G.nodes[v]["x"])]
            })

    return tunnels


def _edge_set(path: List[int]) -> set[Tuple[int, int]]:
    return {(u, v) for u, v in zip(path[:-1], path[1:])}


def compute_routes(start: LatLon, via: LatLon, end: LatLon, scenario_name: str = "default") -> Dict[str, Dict]:
    """Compute distinct routes (shortest, logical, safest, and manual safe for Rotterdam/The Hague) between waypoints.

    Returns a JSON-serialisable dictionary for easy use in the API layer.
    """
    try:
        logger.info("Computing routes between %s -> %s -> %s", start, via, end)
        # Use the via point as rough center for the graph.
        G = build_graph(via, scenario_name=scenario_name)
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

        # Add manual safe route for Rotterdam/The Hague scenario
        if scenario_name == "rotterdam_the_hague":
            logger.info("Computing manual safe route")
            safe_manual_path = _safe_route_manual(G, start_n, via_n, end_n)
            routes["r_safe_manual"] = _route_from_path(
                G, safe_manual_path, "r_safe_manual", "Safe route (manual)", "safe_manual"
            )
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




