#!/usr/bin/env python3
"""Quick script to update just the Rotterdam scenario with new safe route."""

import sys
import json
import pandas as pd
from pathlib import Path

# Add app to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir / "app"))

from app.routing import compute_routes
from app.analysis import full_analysis
from config import ROTTERDAM_THE_HAGUE_SCENARIO

def quick_export_rotterdam():
    """Quick export just for Rotterdam scenario."""
    print("Computing Rotterdam routes with safe route...")

    # Compute routes (should use cached graph)
    routes = compute_routes(
        ROTTERDAM_THE_HAGUE_SCENARIO.start,
        ROTTERDAM_THE_HAGUE_SCENARIO.via,
        ROTTERDAM_THE_HAGUE_SCENARIO.end,
        scenario_name="rotterdam_the_hague"
    )

    print(f"Routes computed: {list(routes.keys())}")

    # Check if safe route was created
    safe_route = routes.get("r_safe_manual")
    if safe_route:
        print(f"✅ Safe route: {safe_route['label']}")
        print(f"   Length: {safe_route['length_m']:.0f}m")
        print(f"   Description: {safe_route.get('description', 'No description')}")
    else:
        print("❌ Safe route not found")

    # Quick analysis (skip full POI analysis for speed)
    print("Running quick analysis...")
    analysis = full_analysis(routes)

    print(f"Analysis complete: {len(analysis['routes'])} routes, {len(analysis.get('chokepoints', []))} chokepoints")

    # Save to exports
    out_dir = current_dir / "exports"
    out_dir.mkdir(exist_ok=True)

    # Save routes CSV
    routes_data = []
    for r in analysis["routes"].values():
        routes_data.append({
            "id": r["id"],
            "label": r["label"],
            "kind": r["kind"],
            "length_m": r["length_m"],
            "turn_count": r["turn_count"],
        })

    df = pd.DataFrame(routes_data)
    df.to_csv(out_dir / "routes_rotterdam_the_hague.csv", index=False)
    print(f"Saved routes to {out_dir / 'routes_rotterdam_the_hague.csv'}")

    print("✅ Rotterdam scenario updated with safe route!")

if __name__ == "__main__":
    quick_export_rotterdam()

