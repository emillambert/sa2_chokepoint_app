#!/usr/bin/env python3
"""Update the safe route to use actual road-following coordinates."""

import sys
import json
from pathlib import Path

# Add app to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir / "app"))

from app.routing import compute_routes
from config import ROTTERDAM_THE_HAGUE_SCENARIO

def update_safe_route():
    """Compute the safe route using road matching and update the GeoJSON."""
    print("Computing safe route with road-following coordinates...")

    # Compute all routes (this will use the road-matching algorithm for safe route)
    routes = compute_routes(
        ROTTERDAM_THE_HAGUE_SCENARIO.start,
        ROTTERDAM_THE_HAGUE_SCENARIO.via,
        ROTTERDAM_THE_HAGUE_SCENARIO.end,
        scenario_name="rotterdam_the_hague"
    )

    safe_route = routes.get("r_safe_manual")
    if not safe_route:
        print("❌ Safe route not computed")
        return

    print(f"✅ Safe route computed: {len(safe_route['path'])} coordinate points")
    print(f"   Length: {safe_route['length_m']:.0f}m")
    print(f"   Turns: {safe_route['turn_count']}")

    # Update the GeoJSON file
    geojson_path = current_dir / "exports" / "routes_rotterdam_the_hague.geojson"
    with open(geojson_path, 'r') as f:
        data = json.load(f)

    # Find and update the safe route
    for feature in data['features']:
        if feature['properties']['id'] == 'r_safe_manual':
            # Convert path to GeoJSON coordinates format (lon, lat)
            coordinates = [[lon, lat] for lat, lon in safe_route['path']]
            feature['geometry']['coordinates'] = coordinates
            feature['properties']['length_m'] = safe_route['length_m']
            feature['properties']['turn_count'] = safe_route['turn_count']
            feature['properties']['description'] = safe_route.get('description', 'Safe route following major roads with tunnel verification')
            break

    # Save updated GeoJSON
    with open(geojson_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"✅ Updated routes GeoJSON with {len(coordinates)} road-following coordinates")
    print("🔄 Refresh your browser to see the updated route!")

if __name__ == "__main__":
    update_safe_route()
