from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List, Tuple

from .models import Chokepoint, PointOfInterest, Route, SecurityTeamPlacement

LatLon = Tuple[float, float]


def _collect_routes(route_data: Dict[str, Dict]) -> List[Route]:
    routes: List[Route] = []
    for r_id, payload in route_data.items():
        routes.append(
            Route(
                id=r_id,
                label=payload["label"],
                kind=payload["kind"],
                path=[tuple(p) for p in payload["path"]],
                length_m=payload["length_m"],
                estimated_time_min=payload["estimated_time_min"],
                turn_count=payload["turn_count"],
                risk_score=payload["risk_score"],
                description=payload.get("description", ""),
            )
        )
    return routes


def cluster_chokepoints(chokepoints: Dict[str, Dict], max_distance_m: float = 100) -> Dict[str, Dict]:
    """Cluster nearby chokepoints to reduce clutter while maintaining security coverage."""
    import math

    def haversine_distance(coord1, coord2):
        """Calculate distance between two (lat, lon) coordinates in meters."""
        lat1, lon1 = coord1
        lat2, lon2 = coord2

        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))

        # Radius of Earth in meters
        r = 6371000
        return c * r

    def find_clusters(cp_list, distance_threshold):
        """Find clusters of nearby chokepoints."""
        clusters = []
        visited = set()

        for i, cp in enumerate(cp_list):
            if i in visited:
                continue

            cluster = [cp]
            visited.add(i)

            for j, other_cp in enumerate(cp_list):
                if j not in visited:
                    distance = haversine_distance(cp['location'], other_cp['location'])
                    if distance <= distance_threshold:
                        cluster.append(other_cp)
                        visited.add(j)

            clusters.append(cluster)

        return clusters

    if len(chokepoints) <= 10:
        # Keep small numbers of chokepoints as-is
        return chokepoints

    # Convert dict to list for clustering
    cp_list = list(chokepoints.values())

    # Find clusters
    clusters = find_clusters(cp_list, max_distance_m)

    # Create clustered chokepoints
    clustered_cps = {}

    for cluster_idx, cluster in enumerate(clusters):
        if len(cluster) == 1:
            # Single chokepoint, keep as-is
            cp = cluster[0]
            clustered_cps[cp['id']] = cp
        else:
            # Multiple chokepoints in cluster - merge them
            # Use the highest-scoring chokepoint as base
            representative = max(cluster, key=lambda cp: cp.get('vulnerability_score', 0))

            # Update ID to reflect clustering
            representative = representative.copy()
            representative['id'] = f"{representative['id']}_cluster_{cluster_idx}"

            # Combine routes affected from all chokepoints in cluster
            all_routes = set()
            for cp in cluster:
                all_routes.update(cp.get('routes_affected', []))
            representative['routes_affected'] = sorted(list(all_routes))

            # Update vulnerability score (take the highest)
            representative['vulnerability_score'] = max(cp.get('vulnerability_score', 0) for cp in cluster)

            # Combine factors
            all_factors = set()
            for cp in cluster:
                all_factors.update(cp.get('factors', []))
            representative['factors'] = list(all_factors)

            # Update description
            total_routes = len(set().union(*[cp.get('routes_affected', []) for cp in cluster]))
            original_desc = representative.get('description', '').split('.')[0]  # Get first sentence
            representative['description'] = f"{original_desc}. (Merged cluster of {len(cluster)} nearby chokepoints covering {total_routes} routes)"

            clustered_cps[representative['id']] = representative

    return clustered_cps


def identify_chokepoints(route_data: Dict[str, Dict]) -> Dict[str, Dict]:
    """Identify chokepoints shared across routes and score their vulnerability.

    A chokepoint here is primarily:
    - A graph node that appears on at least two routes, or
    - A node that appears on all three routes (strong chokepoint).
    """
    node_usage: Dict[int, Dict] = {}

    # Map nodes to routes, coordinates and edge context
    for route_id, payload in route_data.items():
        nodes = payload.get("nodes", [])
        coords = payload.get("path", [])
        nodes_meta = payload.get("nodes_meta", [])
        edges_meta = payload.get("edges_meta", [])

        for idx, (node_id, coord) in enumerate(zip(nodes, coords)):
            info = node_usage.setdefault(
                int(node_id),
                {
                    "routes": set(),
                    "coord": tuple(coord),
                    "is_intersection": False,
                    "edges": [],
                },
            )
            info["routes"].add(route_id)
            if idx < len(nodes_meta) and nodes_meta[idx].get("is_intersection"):
                info["is_intersection"] = True

        for edge in edges_meta:
            u = int(edge["u"])
            v = int(edge["v"])
            node_usage.setdefault(u, {"routes": set(), "coord": None, "is_intersection": False, "edges": []})[
                "edges"
            ].append(edge)
            node_usage.setdefault(v, {"routes": set(), "coord": None, "is_intersection": False, "edges": []})[
                "edges"
            ].append(edge)

    chokepoints: Dict[str, Dict] = {}
    total_routes = len(route_data)

    for node_id, info in node_usage.items():
        routes_here = info["routes"]
        if not routes_here:
            continue

        shared_all = len(routes_here) == total_routes
        shared_multiple = len(routes_here) >= 2

        # Only treat nodes used by multiple routes as chokepoints to avoid noise.
        if not (shared_all or shared_multiple):
            continue

        factors: List[str] = []
        score = 3.0

        if shared_all:
            score += 3.0
            factors.append("common_to_all_routes")
        elif shared_multiple:
            score += 2.0
            factors.append("shared_by_multiple_routes")

        if info.get("is_intersection"):
            score += 2.0
            factors.append("major_intersection")

        edges = info.get("edges", [])
        has_tunnel = any(e.get("is_tunnel") for e in edges)
        has_bridge = any(e.get("is_bridge") for e in edges)
        dense_env = any(
            e.get("highway")
            in {
                "residential",
                "living_street",
                "tertiary",
                "secondary",
            }
            for e in edges
        )

        if has_tunnel:
            score += 2.0
            factors.append("near_tunnel_or_underpass")
        if has_bridge:
            score += 2.0
            factors.append("bridge_or_viaduct")
        if dense_env:
            score += 1.0
            factors.append("dense_or_complex_urban_area")

        # Clamp the score to a 1–10 range.
        score = max(1.0, min(10.0, score))

        coord = info.get("coord")
        if coord is None:
            # If for some reason we lack coordinates, skip this node.
            continue

        lat, lon = coord
        cp_id = f"cp_{node_id}"

        description_parts = [
            f"Node used by {len(routes_here)} of {total_routes} routes.",
        ]
        if factors:
            description_parts.append("Factors: " + ", ".join(factors) + ".")

        cp = Chokepoint(
            id=cp_id,
            location=(float(lat), float(lon)),
            type="intersection",
            routes_affected=sorted(routes_here),
            vulnerability_score=score,
            factors=factors,
            description=" ".join(description_parts),
        )
        chokepoints[cp_id] = asdict(cp)

    # Cluster nearby chokepoints to reduce clutter
    clustered_chokepoints = cluster_chokepoints(chokepoints, max_distance_m=100)

    return clustered_chokepoints


def cluster_pois(pois: Dict[str, Dict], max_distance_m: float = 150) -> Dict[str, Dict]:
    """Cluster nearby POIs of the same type to reduce clutter while maintaining threat coverage."""
    import math

    def haversine_distance(coord1, coord2):
        """Calculate distance between two (lat, lon) coordinates in meters."""
        lat1, lon1 = coord1
        lat2, lon2 = coord2

        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))

        # Radius of Earth in meters
        r = 6371000
        return c * r

    def find_clusters(poi_list, distance_threshold):
        """Find clusters of nearby POIs."""
        clusters = []
        visited = set()

        for i, poi in enumerate(poi_list):
            if i in visited:
                continue

            cluster = [poi]
            visited.add(i)

            for j, other_poi in enumerate(poi_list):
                if j not in visited:
                    distance = haversine_distance(poi['location'], other_poi['location'])
                    if distance <= distance_threshold:
                        cluster.append(other_poi)
                        visited.add(j)

            clusters.append(cluster)

        return clusters

    # Group POIs by type
    pois_by_type = {}
    for poi_id, poi_data in pois.items():
        poi_type = poi_data['type']
        if poi_type not in pois_by_type:
            pois_by_type[poi_type] = []
        pois_by_type[poi_type].append(poi_data)

    # Cluster each type
    clustered_pois = {}

    for poi_type, poi_list in pois_by_type.items():
        if len(poi_list) <= 3:
            # Keep small groups as-is
            for poi in poi_list:
                clustered_pois[poi['id']] = poi
        else:
            # Cluster larger groups
            clusters = find_clusters(poi_list, max_distance_m)

            for cluster_idx, cluster in enumerate(clusters):
                if len(cluster) == 1:
                    # Single POI, keep as-is
                    clustered_pois[cluster[0]['id']] = cluster[0]
                else:
                    # Multiple POIs in cluster - create representative POI
                    representative = cluster[0].copy()

                    # Update ID to reflect clustering
                    representative['id'] = f"{representative['id']}_cluster_{cluster_idx}"

                    # Update description to mention clustering
                    original_desc = representative.get('description', '')
                    representative['description'] = f"{original_desc} (Represents cluster of {len(cluster)} nearby locations within {max_distance_m}m)"

                    clustered_pois[representative['id']] = representative

    return clustered_pois


def find_pois(route_data: Dict[str, Dict], chokepoints: Dict[str, Dict]) -> Dict[str, Dict]:
    """Identify POIs for ambush, firing, observation and surveillance."""
    pois: Dict[str, Dict] = {}

    # Route-based POIs
    for route_id, payload in route_data.items():
        coords = payload.get("path", [])
        edges = payload.get("edges_meta", [])
        nodes_meta = payload.get("nodes_meta", [])

        # 1) Ambush locations – narrow or constrained segments
        # Scale POI limits by route length for comprehensive coverage
        route_length = len(edges)
        ambush_limit = max(5, route_length // 40)  # ~1 POI per 40 edges, minimum 5

        ambush_count = 0
        for edge in edges:
            highway = edge.get("highway")
            is_tunnel = edge.get("is_tunnel")
            is_bridge = edge.get("is_bridge")
            if highway in {"residential", "living_street", "tertiary"} or is_tunnel or is_bridge:
                idx = int(edge.get("index", 0))
                coord_idx = min(idx + 1, len(coords) - 1)
                lat, lon = coords[coord_idx]
                poi_id = f"poi_ambush_{route_id}_{idx}"
                poi = PointOfInterest(
                    id=poi_id,
                    type="ambush_location",
                    location=(float(lat), float(lon)),
                    related_route=route_id,
                    related_chokepoint=None,
                    description=(
                        "Likely ambush location where the motorcade must slow down "
                        "near a constrained or structurally complex segment."
                    ),
                )
                pois[poi_id] = asdict(poi)
                ambush_count += 1
                if ambush_count >= ambush_limit:
                    break

        # 2) Surveillance points – intersections on major roads
        # Scale POI limits by route length for comprehensive coverage
        surveillance_limit = max(4, route_length // 30)  # ~1 POI per 30 edges, minimum 4

        surveillance_count = 0
        for edge in edges:
            idx = int(edge.get("index", 0))
            if idx + 1 >= len(nodes_meta):
                continue
            node_meta = nodes_meta[idx + 1]
            if not node_meta.get("is_intersection"):
                continue
            highway = edge.get("highway")
            if highway not in {"primary", "secondary", "tertiary"}:
                continue

            coord_idx = min(idx + 1, len(coords) - 1)
            lat, lon = coords[coord_idx]
            poi_id = f"poi_surv_{route_id}_{idx}"
            poi = PointOfInterest(
                id=poi_id,
                type="surveillance_point",
                location=(float(lat), float(lon)),
                related_route=route_id,
                related_chokepoint=None,
                description=(
                    "Intersection with multiple access routes suitable for hostile "
                    "or friendly surveillance of the motorcade."
                ),
            )
            pois[poi_id] = asdict(poi)
            surveillance_count += 1
            if surveillance_count >= surveillance_limit:
                break

    # Chokepoint-based POIs: observation and firing points
    for cp_id, cp in chokepoints.items():
        lat, lon = cp["location"]

        obs_id = f"poi_obs_{cp_id}"
        obs_poi = PointOfInterest(
            id=obs_id,
            type="enemy_observation_point",
            location=(float(lat), float(lon)),
            related_route=None,
            related_chokepoint=cp_id,
            description=(
                "Dominant observation point overlooking a key chokepoint, "
                "suitable for pre-attack surveillance."
            ),
        )
        pois[obs_id] = asdict(obs_poi)

        fire_id = f"poi_fire_{cp_id}"
        fire_poi = PointOfInterest(
            id=fire_id,
            type="enemy_firing_point",
            location=(float(lat), float(lon)),
            related_route=None,
            related_chokepoint=cp_id,
            description=(
                "Potential firing position with line-of-sight to the chokepoint, "
                "for example from elevated structures or cover near the route."
            ),
        )
        pois[fire_id] = asdict(fire_poi)

    # Cluster nearby POIs to reduce clutter
    clustered_pois = cluster_pois(pois, max_distance_m=150)

    return clustered_pois


def plan_security_assets(
    chokepoints: Dict[str, Dict], pois: Dict[str, Dict]
) -> Dict[str, Dict]:
    """Deploy 6 SDT teams and 3 CS teams based on chokepoint risk."""
    teams: Dict[str, Dict] = {}

    # Sort chokepoints by vulnerability
    sorted_cps = sorted(
        chokepoints.values(),
        key=lambda cp: cp.get("vulnerability_score", 0.0),
        reverse=True,
    )

    # Assign SDT teams to top chokepoints where possible
    sdt_roles = [
        "Advance team: reconnaissance and early road closure at the highest-risk chokepoint.",
        "Static protection team securing approaches to a high-risk chokepoint.",
        "Rear security team covering potential follow-up attacks near a critical chokepoint.",
        "Escort team integrated in the motorcade to respond at chokepoints.",
        "Reserve team positioned to reinforce any chokepoint if threatened.",
        "Quick reaction force covering alternative evacuation routes.",
    ]

    for i in range(6):
        team_id = f"SDT{i+1}"
        if i < len(sorted_cps):
            cp = sorted_cps[i]
            lat, lon = cp["location"]
            assigned_to = cp["id"]
            role_desc = sdt_roles[i]
        else:
            # If there are fewer chokepoints than teams, fall back to a generic role.
            any_cp = sorted_cps[0] if sorted_cps else None
            if any_cp:
                lat, lon = any_cp["location"]
                assigned_to = any_cp["id"]
            else:
                lat, lon = (0.0, 0.0)
                assigned_to = None
            role_desc = sdt_roles[i]

        team = SecurityTeamPlacement(
            id=team_id,
            type="SDT",
            location=(float(lat), float(lon)),
            assigned_to=assigned_to,
            role_description=role_desc,
        )
        teams[team_id] = asdict(team)

    # Assign 3 counter-sniper teams to the top three chokepoints
    cs_roles = [
        "Counter-sniper overwatch on the single most vulnerable chokepoint.",
        "Counter-sniper team covering the primary conference venue approach.",
        "Counter-sniper team covering the reception venue and surrounding access routes.",
    ]

    for i in range(3):
        team_id = f"CS{i+1}"
        if i < len(sorted_cps):
            cp = sorted_cps[i]
            lat, lon = cp["location"]
            assigned_to = cp["id"]
        else:
            any_cp = sorted_cps[0] if sorted_cps else None
            if any_cp:
                lat, lon = any_cp["location"]
                assigned_to = any_cp["id"]
            else:
                lat, lon = (0.0, 0.0)
                assigned_to = None

        team = SecurityTeamPlacement(
            id=team_id,
            type="CS",
            location=(float(lat), float(lon)),
            assigned_to=assigned_to,
            role_description=cs_roles[i],
        )
        teams[team_id] = asdict(team)

    return teams


def full_analysis(route_data: Dict[str, Dict]) -> Dict[str, Dict]:
    """Combine routes with chokepoints, POIs and security planning."""
    chokepoints = identify_chokepoints(route_data)
    pois = find_pois(route_data, chokepoints)
    teams = plan_security_assets(chokepoints, pois)

    return {
        "routes": route_data,
        "chokepoints": chokepoints,
        "pois": pois,
        "teams": teams,
    }


