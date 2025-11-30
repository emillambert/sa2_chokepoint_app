from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List, Tuple

from .models import Chokepoint, PointOfInterest, Route, SecurityTeamPlacement

LatLon = Tuple[float, float]


def _haversine_distance(coord1: LatLon, coord2: LatLon) -> float:
    """Calculate distance between two (lat, lon) coordinates in meters."""
    import math
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


def _get_route_center(coords: List[LatLon]) -> LatLon:
    """Calculate the geographic center of a route."""
    if not coords:
        return (0.0, 0.0)

    lats = [lat for lat, lon in coords]
    lons = [lon for lat, lon in coords]

    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    return (center_lat, center_lon)


def _estimate_motorcade_speed(edge: Dict, route_metadata: Dict) -> float:
    """Estimate motorcade speed based on road type and constraints."""
    highway = edge.get("highway", "")
    is_tunnel = edge.get("is_tunnel", False)
    is_bridge = edge.get("is_bridge", False)

    # Base speeds (km/h)
    speed_map = {
        "motorway": 80,
        "trunk": 70,
        "primary": 60,
        "secondary": 50,
        "tertiary": 40,
        "residential": 20,
        "living_street": 15
    }

    base_speed = speed_map.get(highway, 30)

    # Speed penalties
    if is_tunnel:
        base_speed *= 0.7  # 30% reduction in tunnels
    if is_bridge:
        base_speed *= 0.8  # 20% reduction on bridges
    if highway in {"residential", "living_street"}:
        base_speed *= 0.6  # 40% reduction in residential areas

    return base_speed


def _calculate_isolation_score(edge: Dict, adjacent_edges: List[Dict]) -> float:
    """Calculate isolation score (higher = more isolated = better for ambush)."""
    highway = edge.get("highway", "")

    # Major roads are less isolated
    if highway in {"motorway", "trunk", "primary"}:
        return 2.0

    # Secondary/tertiary roads moderately isolated
    if highway in {"secondary", "tertiary"}:
        return 4.0

    # Residential areas most isolated
    return 6.0


def _estimate_urban_density(edge: Dict, surrounding_edges: List[Dict]) -> float:
    """Estimate urban density proxy (higher = more urban = harder ambush)."""
    highway = edge.get("highway", "")

    # Motorways = low density (rural/highway)
    if highway == "motorway":
        return 2.0

    # Primary/secondary = medium density
    if highway in {"primary", "secondary"}:
        return 4.0

    # Tertiary/residential = high density
    if highway in {"tertiary", "residential", "living_street"}:
        return 7.0

    return 5.0


def _calculate_ambush_threat(speed: float, isolation: float, urban_density: float) -> float:
    """Calculate ambush threat score (higher = more threatening)."""
    # Speed factor: slower = more vulnerable (motorcade has less momentum)
    speed_factor = max(1.0, 60.0 / speed)  # Normalize against 60 km/h for better range

    # Isolation factor: more isolated = higher threat
    isolation_factor = isolation / 2.0  # Normalize to 0-3 range

    # Urban density factor: lower density = higher threat (fewer witnesses)
    density_factor = max(1.0, 10.0 - urban_density)  # Inverse relationship, better range

    threat_score = (speed_factor * 0.5) + (isolation_factor * 0.3) + (density_factor * 0.2)
    return min(10.0, threat_score)  # Cap at 10


def _calculate_surveillance_priority(distance_from_center: float, access_routes: int, highway_type: str) -> float:
    """Calculate surveillance priority score."""
    # Distance factor: closer to route center = higher priority
    distance_factor = max(1.0, 2000.0 / (distance_from_center + 200))  # Better range

    # Access factor: more access routes = higher priority
    access_factor = min(4.0, access_routes)  # Direct count, cap at 4.0

    # Highway factor: higher capacity roads = higher priority
    highway_scores = {
        "motorway": 4.0,
        "trunk": 3.5,
        "primary": 3.0,
        "secondary": 2.5,
        "tertiary": 2.0
    }
    highway_factor = highway_scores.get(highway_type, 1.5)

    priority_score = (distance_factor * 0.4) + (access_factor * 0.3) + (highway_factor * 0.3)
    return priority_score


def _count_connected_roads(edge: Dict, nodes_meta: List[Dict], edge_idx: int) -> int:
    """Count roads connected to an intersection (basic connectivity proxy)."""
    if edge_idx + 1 >= len(nodes_meta):
        return 1

    node_degree = nodes_meta[edge_idx + 1].get("degree", 2)
    return max(1, node_degree - 1)  # Subtract 1 for the incoming road


def _is_elevated_position(chokepoint: Dict) -> bool:
    """Check if chokepoint has elevation advantage (bridges, tunnels nearby)."""
    # This is a simplified proxy - in reality would need terrain data
    # For now, assume urban chokepoints have more elevation opportunities
    return chokepoint.get("type") == "intersection"


def _min_distance_to_route(chokepoint: Dict, route_data: Dict) -> float:
    """Calculate minimum distance from chokepoint to any route coordinate."""
    cp_lat, cp_lon = chokepoint["location"]
    cp_coord = (cp_lat, cp_lon)

    min_distance = float('inf')

    for route_payload in route_data.values():
        coords = route_payload.get("path", [])
        for coord in coords:
            distance = _haversine_distance(cp_coord, coord)
            min_distance = min(min_distance, distance)

    return min_distance


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
    """Intelligently cluster POIs by threat type and tactical value."""

    # Group POIs by type
    pois_by_type = {}
    for poi_id, poi_data in pois.items():
        poi_type = poi_data['type']
        if poi_type not in pois_by_type:
            pois_by_type[poi_type] = []
        pois_by_type[poi_type].append(poi_data)

    # Apply intelligent clustering per threat type
    clustered_pois = {}

    for poi_type, poi_list in pois_by_type.items():
        # Sort by priority score (add default if missing)
        for poi in poi_list:
            if 'priority_score' not in poi:
                poi['priority_score'] = 1.0  # Default priority

        poi_list.sort(key=lambda p: p.get('priority_score', 1.0), reverse=True)

        # Threat-specific limits and clustering radii
        threat_config = {
            'ambush_location': {'max_individual': 6, 'cluster_radius': 200},
            'surveillance_point': {'max_individual': 8, 'cluster_radius': 300},
            'enemy_observation_point': {'max_individual': 4, 'cluster_radius': 150},
            'enemy_firing_point': {'max_individual': 4, 'cluster_radius': 150}
        }

        config = threat_config.get(poi_type, {'max_individual': 5, 'cluster_radius': 150})
        max_individual = config['max_individual']
        cluster_radius = config['cluster_radius']

        # Keep top priority POIs as individual
        keep_individual = poi_list[:max_individual]
        to_cluster = poi_list[max_individual:]

        # Add individual high-priority POIs
        for poi in keep_individual:
            clustered_pois[poi['id']] = poi

        # Cluster lower-priority POIs
        if to_cluster:
            clustered_low_priority = _cluster_low_priority_pois(to_cluster, cluster_radius)
            clustered_pois.update(clustered_low_priority)

    return clustered_pois


def _cluster_low_priority_pois(poi_list: List[Dict], radius_m: float) -> Dict[str, Dict]:
    """Cluster lower-priority POIs using distance-based clustering."""
    if not poi_list:
        return {}

    clustered = {}

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
                    distance = _haversine_distance(poi['location'], other_poi['location'])
                    if distance <= distance_threshold:
                        cluster.append(other_poi)
                        visited.add(j)

            clusters.append(cluster)

        return clusters

    clusters = find_clusters(poi_list, radius_m)

    for cluster_idx, cluster in enumerate(clusters):
        if len(cluster) == 1:
            # Single POI, keep as-is
            clustered[cluster[0]['id']] = cluster[0]
        else:
            # Multiple POIs in cluster - create representative POI
            # Use highest priority POI as representative
            representative = max(cluster, key=lambda p: p.get('priority_score', 1.0))
            representative = representative.copy()

            # Update ID to reflect clustering
            representative['id'] = f"{representative['id']}_cluster_{cluster_idx}"

            # Update description to mention clustering
            original_desc = representative.get('description', '')
            threat_count = len(cluster)
            representative['description'] = f"{original_desc} (Represents cluster of {threat_count} nearby threat locations)"

            clustered[representative['id']] = representative

    return clustered


def find_pois(route_data: Dict[str, Dict], chokepoints: Dict[str, Dict]) -> Dict[str, Dict]:
    """Identify POIs for ambush, firing, observation and surveillance using tactical reasoning."""
    pois: Dict[str, Dict] = {}

    # Route-based POIs with intelligent filtering
    for route_id, payload in route_data.items():
        coords = payload.get("path", [])
        edges = payload.get("edges_meta", [])
        nodes_meta = payload.get("nodes_meta", [])

        if not coords:
            continue

        route_center = _get_route_center(coords)

        # 1) Ambush locations – Intelligent speed + context analysis
        ambush_candidates = []
        for idx, edge in enumerate(edges):
            highway = edge.get("highway", "")
            is_tunnel = edge.get("is_tunnel", False)
            is_bridge = edge.get("is_bridge", False)

            # Only consider constrained segments
            if not (highway in {"residential", "living_street", "tertiary"} or is_tunnel or is_bridge):
                continue

            # Calculate tactical factors
            speed = _estimate_motorcade_speed(edge, payload)

            # Get adjacent edges for context (simplified)
            adjacent_edges = []
            if idx > 0:
                adjacent_edges.append(edges[idx-1])
            if idx < len(edges) - 1:
                adjacent_edges.append(edges[idx+1])

            isolation = _calculate_isolation_score(edge, adjacent_edges)
            urban_density = _estimate_urban_density(edge, adjacent_edges)
            threat_score = _calculate_ambush_threat(speed, isolation, urban_density)

            # Only create POI if threat score is high enough
            if threat_score >= 2.5:
                coord_idx = min(idx + 1, len(coords) - 1)
                lat, lon = coords[coord_idx]

                poi_id = f"poi_ambush_{route_id}_{idx}"
                poi = PointOfInterest(
                    id=poi_id,
                    type="ambush_location",
                    location=(float(lat), float(lon)),
                    related_route=route_id,
                    related_chokepoint=None,
                    description=f"High-threat ambush location (threat score: {threat_score:.1f}). Motorcade speed: {speed:.0f} km/h in {highway} segment.",
                )
                poi_dict = asdict(poi)
                poi_dict['priority_score'] = threat_score
                ambush_candidates.append(poi_dict)

        # Limit ambush POIs per route and add to main collection
        ambush_candidates.sort(key=lambda p: p['priority_score'], reverse=True)
        for poi in ambush_candidates[:8]:  # Max 8 per route
            pois[poi['id']] = poi

        # 2) Surveillance points – Distance + access filtering
        surveillance_candidates = []
        for idx, edge in enumerate(edges):
            # Only consider major intersections
            if idx + 1 >= len(nodes_meta):
                continue
            node_meta = nodes_meta[idx + 1]
            if not node_meta.get("is_intersection"):
                continue
            highway = edge.get("highway", "")
            if highway not in {"primary", "secondary", "tertiary"}:
                continue

            # Calculate surveillance priority
            coord_idx = min(idx + 1, len(coords) - 1)
            intersection_pos = coords[coord_idx]
            distance_from_center = _haversine_distance(intersection_pos, route_center)
            access_routes = _count_connected_roads(edge, nodes_meta, idx)
            priority_score = _calculate_surveillance_priority(distance_from_center, access_routes, highway)

            # Only create high-priority surveillance points
            if priority_score >= 2.0:
                lat, lon = intersection_pos
                poi_id = f"poi_surv_{route_id}_{idx}"
                poi = PointOfInterest(
                    id=poi_id,
                    type="surveillance_point",
                    location=(float(lat), float(lon)),
                    related_route=route_id,
                    related_chokepoint=None,
                    description=f"High-priority surveillance position (priority: {priority_score:.1f}). {access_routes} access routes, {distance_from_center:.0f}m from route center.",
                )
                poi_dict = asdict(poi)
                poi_dict['priority_score'] = priority_score
                surveillance_candidates.append(poi_dict)

        # Limit surveillance POIs per route
        surveillance_candidates.sort(key=lambda p: p['priority_score'], reverse=True)
        for poi in surveillance_candidates[:10]:  # Max 10 per route
            pois[poi['id']] = poi

    # Chokepoint-based POIs: filtered by tactical value
    for cp_id, cp in chokepoints.items():
        cp_score = cp.get("vulnerability_score", 0.0)

        # Only create POIs for high-value chokepoints
        if cp_score < 6.0:
            continue

        lat, lon = cp["location"]
        has_elevation = _is_elevated_position(cp)
        route_distance = _min_distance_to_route(cp, route_data)

        # Only create POIs if tactically viable
        if has_elevation or route_distance < 500:
            priority_score = cp_score / 2.0  # Normalize to reasonable priority range

            obs_id = f"poi_obs_{cp_id}"
            obs_poi = PointOfInterest(
                id=obs_id,
                type="enemy_observation_point",
                location=(float(lat), float(lon)),
                related_route=None,
                related_chokepoint=cp_id,
                description=(
                    f"High-value observation point at chokepoint (vulnerability: {cp_score:.1f}). "
                    f"Elevation advantage: {'Yes' if has_elevation else 'Limited'}. "
                    f"Distance to route: {route_distance:.0f}m."
                ),
            )
            obs_dict = asdict(obs_poi)
            obs_dict['priority_score'] = priority_score
            pois[obs_id] = obs_dict

            fire_id = f"poi_fire_{cp_id}"
            fire_poi = PointOfInterest(
                id=fire_id,
                type="enemy_firing_point",
                location=(float(lat), float(lon)),
                related_route=None,
                related_chokepoint=cp_id,
                description=(
                    f"High-value firing position at chokepoint (vulnerability: {cp_score:.1f}). "
                    f"Elevation advantage: {'Yes' if has_elevation else 'Limited'}. "
                    f"Distance to route: {route_distance:.0f}m."
                ),
            )
            fire_dict = asdict(fire_poi)
            fire_dict['priority_score'] = priority_score
            pois[fire_id] = fire_dict

    # Apply intelligent clustering
    clustered_pois = cluster_pois(pois)

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


