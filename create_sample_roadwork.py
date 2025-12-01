#!/usr/bin/env python3
"""Create sample road work data for Rotterdam/The Hague scenario."""

import json
import csv
from pathlib import Path

# Sample road work locations in The Hague area for January 2026
roadwork_data = [
    {
        "id": "ndw_001",
        "location": [4.32, 52.08],  # Near Konningskade
        "description": "Road maintenance on Konningskade - lane closures expected",
        "start_date": "2026-01-15",
        "end_date": "2026-01-20",
        "affected_roads": ["Konninginnegracht", "Konnningskade"]
    },
    {
        "id": "ndw_002",
        "location": [4.29, 52.085],  # Near Hubertus Viaduct
        "description": "Bridge inspection and maintenance on Hubertus Viaduct",
        "start_date": "2026-01-08",
        "end_date": "2026-01-12",
        "affected_roads": ["Hubertus Viaduct"]
    },
    {
        "id": "ndw_003",
        "location": [4.28, 52.09],  # Near S100
        "description": "Utility work on S100 - temporary traffic lights",
        "start_date": "2026-01-22",
        "end_date": "2026-01-26",
        "affected_roads": ["S100"]
    }
]

exports_dir = Path(__file__).parent / "exports"

# Create CSV
with open(exports_dir / "roadwork_rotterdam_the_hague.csv", 'w', newline='', encoding='utf-8') as f:
    if roadwork_data:
        fieldnames = roadwork_data[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(roadwork_data)

# Create GeoJSON
geojson_features = []
for item in roadwork_data:
    feature = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [item["location"][0], item["location"][1]]  # [lon, lat]
        },
        "properties": {k: v for k, v in item.items() if k != "location"}
    }
    geojson_features.append(feature)

geojson_data = {
    "type": "FeatureCollection",
    "features": geojson_features
}

with open(exports_dir / "roadwork_rotterdam_the_hague.geojson", 'w', encoding='utf-8') as f:
    json.dump(geojson_data, f, indent=2)

print("Created sample road work data for Rotterdam/The Hague scenario")
print(f"Added {len(roadwork_data)} road work locations")

