#!/usr/bin/env python3
"""Create analysis data for the safe route by filtering existing Rotterdam analysis."""

import sys
import json
import csv
import pandas as pd
import math
from pathlib import Path

current_dir = Path(__file__).parent

def haversine_distance(coord1, coord2):
    """Calculate distance between two (lat, lon) coordinates in meters."""
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    # Convert to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlng = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
    c = 2 * math.asin(math.sqrt(a))

    # Radius of Earth in meters
    r = 6371000
    return c * r

def load_safe_route():
    """Load the safe route coordinates."""
    with open(current_dir / "exports" / "routes_rotterdam_the_hague.geojson", 'r') as f:
        data = json.load(f)

    for feature in data['features']:
        if feature['properties']['id'] == 'r_safe_manual':
            return [(coord[1], coord[0]) for coord in feature['geometry']['coordinates']]  # Convert to (lat, lon)

    raise ValueError("Safe route not found")

def filter_chokepoints_for_safe_route():
    """Filter existing chokepoints to find those near the safe route."""
    safe_route_path = load_safe_route()

    # Load existing chokepoints
    cps_df = pd.read_csv(current_dir / "exports" / "chokepoints_rotterdam_the_hague.csv")

    filtered_cps = []

    for _, cp in cps_df.iterrows():
        # Parse location string like "(52.0928302, 4.2885914)"
        location_str = cp['location'].strip('()')
        lat, lon = map(float, location_str.split(', '))

        # Check if chokepoint is within 500m of any point on the safe route
        min_distance = min(haversine_distance((lat, lon), route_point) for route_point in safe_route_path)

        if min_distance <= 500:  # Within 500m of safe route
            # Update routes_affected to include safe route
            routes_affected = cp['routes_affected'].strip('[]').replace("'", "").split(', ')
            routes_affected = [r.strip() for r in routes_affected if r.strip()]
            if 'r_safe_manual' not in routes_affected:
                routes_affected.append('r_safe_manual')

            cp_copy = cp.copy()
            cp_copy['routes_affected'] = str(routes_affected)
            cp_copy['description'] = f"{cp['description']} (Near safe route - {min_distance:.0f}m away)"

            filtered_cps.append(cp_copy)

    return filtered_cps

def create_specific_safe_route_chokepoints():
    """Create specific chokepoints for the safe route segments."""
    safe_route_path = load_safe_route()

    # Create chokepoints at key junctions along the safe route
    safe_chokepoints = [
        {
            "id": "cp_safe_a16_start",
            "location": "(51.97, 4.45)",
            "type": "intersection",
            "routes_affected": "['r_safe_manual']",
            "vulnerability_score": 7.0,
            "factors": "['major_intersection', 'shared_by_multiple_routes']",
            "description": "A16 motorway start junction near Rotterdam Airport - high traffic intersection"
        },
        {
            "id": "cp_safe_n209_junction",
            "location": "(52.05, 4.51)",
            "type": "intersection",
            "routes_affected": "['r_safe_manual']",
            "vulnerability_score": 6.5,
            "factors": "['major_intersection']",
            "description": "N209 to A12 transition junction - potential bottleneck"
        },
        {
            "id": "cp_safe_a12_approach",
            "location": "(52.075, 4.50)",
            "type": "intersection",
            "routes_affected": "['r_safe_manual']",
            "vulnerability_score": 8.0,
            "factors": "['major_intersection', 'dense_or_complex_urban_area']",
            "description": "A12 approach to The Hague - urban transition zone"
        },
        {
            "id": "cp_safe_konnningskade",
            "location": "(52.085, 4.44)",
            "type": "intersection",
            "routes_affected": "['r_safe_manual']",
            "vulnerability_score": 7.5,
            "factors": "['major_intersection', 'dense_or_complex_urban_area']",
            "description": "Konnningskade urban intersection - high pedestrian/crowd density"
        },
        {
            "id": "cp_safe_hubertus_viaduct",
            "location": "(52.085, 4.36)",
            "type": "intersection",
            "routes_affected": "['r_safe_manual']",
            "vulnerability_score": 9.0,
            "factors": "['bridge_or_viaduct', 'major_intersection', 'dense_or_complex_urban_area']",
            "description": "Hubertus Viaduct - elevated bridge structure with limited escape routes"
        },
        {
            "id": "cp_safe_s100_junction",
            "location": "(52.082, 4.33)",
            "type": "intersection",
            "routes_affected": "['r_safe_manual']",
            "vulnerability_score": 6.0,
            "factors": "['major_intersection']",
            "description": "S100 junction near Mauritshuis - final approach intersection"
        }
    ]

    return safe_chokepoints

def filter_pois_for_safe_route():
    """Filter existing POIs to find those near the safe route."""
    safe_route_path = load_safe_route()

    # Load existing POIs
    pois_df = pd.read_csv(current_dir / "exports" / "pois_rotterdam_the_hague.csv")

    filtered_pois = []

    for _, poi in pois_df.iterrows():
        # Parse location string
        location_str = poi['location'].strip('()')
        lat, lon = map(float, location_str.split(', '))

        # Check if POI is within 300m of the safe route
        min_distance = min(haversine_distance((lat, lon), route_point) for route_point in safe_route_path)

        if min_distance <= 300:  # Within 300m of safe route
            poi_copy = poi.copy()
            poi_copy['related_route'] = 'r_safe_manual'
            poi_copy['description'] = f"{poi['description']} (Near safe route - {min_distance:.0f}m away)"

            filtered_pois.append(poi_copy)

    return filtered_pois

def create_specific_safe_route_pois():
    """Create specific POIs for the safe route."""
    safe_pois = [
        {
            "id": "poi_safe_ambush_a16",
            "type": "ambush_location",
            "location": "(52.00, 4.47)",
            "related_route": "r_safe_manual",
            "related_chokepoint": None,
            "description": "High-threat ambush location along A16 motorway segment - good visibility, limited escape routes",
            "priority_score": 7.5
        },
        {
            "id": "poi_safe_observation_hubertus",
            "type": "enemy_observation_point",
            "location": "(52.085, 4.36)",
            "related_route": "r_safe_manual",
            "related_chokepoint": "cp_safe_hubertus_viaduct",
            "description": "Elevated observation point at Hubertus Viaduct - commanding view of motorcade approach",
            "priority_score": 8.0
        },
        {
            "id": "poi_safe_firing_viaduct",
            "type": "enemy_firing_point",
            "location": "(52.085, 4.36)",
            "related_route": "r_safe_manual",
            "related_chokepoint": "cp_safe_hubertus_viaduct",
            "description": "Potential firing position overlooking Hubertus Viaduct - elevated bridge structure",
            "priority_score": 8.5
        },
        {
            "id": "poi_safe_surveillance_konnningskade",
            "type": "surveillance_point",
            "location": "(52.085, 4.44)",
            "related_route": "r_safe_manual",
            "related_chokepoint": "cp_safe_konnningskade",
            "description": "Urban surveillance position at Konnningskade intersection - multiple building vantage points",
            "priority_score": 6.0
        },
        {
            "id": "poi_safe_ambush_urban",
            "type": "ambush_location",
            "location": "(52.08, 4.32)",
            "related_route": "r_safe_manual",
            "related_chokepoint": None,
            "description": "Urban ambush opportunity near S100 junction - dense building cover, pedestrian crowds",
            "priority_score": 8.0
        }
    ]

    return safe_pois

def create_teams_for_safe_route():
    """Create security teams assigned to safe route chokepoints."""
    teams = [
        {
            "id": "SDT1",
            "type": "SDT",
            "location": "(51.97, 4.45)",
            "assigned_to": "cp_safe_a16_start",
            "role_description": "Advance team: reconnaissance and early road closure at A16 motorway start"
        },
        {
            "id": "SDT2",
            "type": "SDT",
            "location": "(52.05, 4.51)",
            "assigned_to": "cp_safe_n209_junction",
            "role_description": "Static protection team securing N209 to A12 transition junction"
        },
        {
            "id": "SDT3",
            "type": "SDT",
            "location": "(52.075, 4.50)",
            "assigned_to": "cp_safe_a12_approach",
            "role_description": "Rear security team covering A12 approach to The Hague"
        },
        {
            "id": "SDT4",
            "type": "SDT",
            "location": "(52.085, 4.44)",
            "assigned_to": "cp_safe_konnningskade",
            "role_description": "Escort team integrated in motorcade at Konnningskade intersection"
        },
        {
            "id": "SDT5",
            "type": "SDT",
            "location": "(52.085, 4.36)",
            "assigned_to": "cp_safe_hubertus_viaduct",
            "role_description": "Reserve team positioned at Hubertus Viaduct for reinforcement"
        },
        {
            "id": "SDT6",
            "type": "SDT",
            "location": "(52.082, 4.33)",
            "assigned_to": "cp_safe_s100_junction",
            "role_description": "Quick reaction force covering S100 junction near Mauritshuis"
        },
        {
            "id": "CS1",
            "type": "CS",
            "location": "(52.085, 4.36)",
            "assigned_to": "cp_safe_hubertus_viaduct",
            "role_description": "Counter-sniper overwatch on Hubertus Viaduct - highest vulnerability point"
        },
        {
            "id": "CS2",
            "type": "CS",
            "location": "(52.085, 4.44)",
            "assigned_to": "cp_safe_konnningskade",
            "role_description": "Counter-sniper team covering Konnningskade urban approach"
        },
        {
            "id": "CS3",
            "type": "CS",
            "location": "(52.08, 4.32)",
            "assigned_to": "cp_safe_s100_junction",
            "role_description": "Counter-sniper team covering S100 junction and Mauritshuis reception"
        }
    ]

    return teams

def main():
    print("Creating analysis data for safe route...")

    # Get all chokepoints for safe route
    safe_cps = filter_chokepoints_for_safe_route() + create_specific_safe_route_chokepoints()
    print(f"Created {len(safe_cps)} chokepoints for safe route")

    # Get all POIs for safe route
    safe_pois = filter_pois_for_safe_route() + create_specific_safe_route_pois()
    print(f"Created {len(safe_pois)} POIs for safe route")

    # Get teams for safe route
    safe_teams = create_teams_for_safe_route()
    print(f"Created {len(safe_teams)} teams for safe route")

    # Save to CSV files
    exports_dir = current_dir / "exports"

    # Save chokepoints
    if safe_cps:
        with open(exports_dir / "chokepoints_safe_manual.csv", 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Write header
            if safe_cps:
                header = list(safe_cps[0].keys())
                writer.writerow(header)

                # Write data
                for cp in safe_cps:
                    row = []
                    for key in header:
                        value = cp.get(key, '')
                        if isinstance(value, list):
                            value = str(value)
                        row.append(value)
                    writer.writerow(row)
        print("Saved chokepoints_safe_manual.csv")

    # Save POIs
    if safe_pois:
        with open(exports_dir / "pois_safe_manual.csv", 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Write header
            if safe_pois:
                header = list(safe_pois[0].keys())
                writer.writerow(header)

                # Write data
                for poi in safe_pois:
                    row = []
                    for key in header:
                        value = poi.get(key, '')
                        row.append(value)
                    writer.writerow(row)
        print("Saved pois_safe_manual.csv")

    # Save teams
    if safe_teams:
        with open(exports_dir / "teams_safe_manual.csv", 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Write header
            if safe_teams:
                header = list(safe_teams[0].keys())
                writer.writerow(header)

                # Write data
                for team in safe_teams:
                    row = []
                    for key in header:
                        value = team.get(key, '')
                        row.append(value)
                    writer.writerow(row)
        print("Saved teams_safe_manual.csv")

    # Create GeoJSON files
    exports_dir = current_dir / "exports"

    # Chokepoints GeoJSON
    if safe_cps:
        features = []
        for cp in safe_cps:
            location_str = cp['location'].strip('()')
            lat, lon = map(float, location_str.split(', '))
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {k: v for k, v in cp.items() if k != 'location'}
            })

        geojson = {"type": "FeatureCollection", "features": features}
        with open(exports_dir / "chokepoints_safe_manual.geojson", 'w') as f:
            json.dump(geojson, f, indent=2)

    # POIs GeoJSON
    if safe_pois:
        features = []
        for poi in safe_pois:
            location_str = poi['location'].strip('()')
            lat, lon = map(float, location_str.split(', '))
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {k: v for k, v in poi.items() if k != 'location'}
            })

        geojson = {"type": "FeatureCollection", "features": features}
        with open(exports_dir / "pois_safe_manual.geojson", 'w') as f:
            json.dump(geojson, f, indent=2)

    # Teams GeoJSON
    if safe_teams:
        features = []
        for team in safe_teams:
            location = team['location']
            if isinstance(location, str):
                # Parse string format like "(52.08, 4.31)"
                location_str = location.strip('()')
                lat, lon = map(float, location_str.split(', '))
            else:
                # Already a tuple
                lat, lon = location
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {k: v for k, v in team.items() if k != 'location'}
            })

        geojson = {"type": "FeatureCollection", "features": features}
        with open(exports_dir / "teams_safe_manual.geojson", 'w') as f:
            json.dump(geojson, f, indent=2)

    print("Safe route analysis complete!")
    print("Files created:")
    print("  - chokepoints_safe_manual.csv/geojson")
    print("  - pois_safe_manual.csv/geojson")
    print("  - teams_safe_manual.csv/geojson")

if __name__ == "__main__":
    main()
