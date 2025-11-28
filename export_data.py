"""Export helper for the SA2 chokepoint analysis app.

This script runs the same routing + analysis pipeline as the web UI and
writes the results to simple GeoJSON and CSV files so you can use them
in mapping tools or reference them directly in your report.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from app.analysis import full_analysis
from app.routing import compute_routes
from config import (
    DEFAULT_SCENARIO,
    ROTTERDAM_THE_HAGUE_SCENARIO,
    SCHIPHOL_SCENARIO,
)

LatLon = Tuple[float, float]


def _scenario_by_name(name: str):
    if name == SCHIPHOL_SCENARIO.name:
        return SCHIPHOL_SCENARIO
    if name == ROTTERDAM_THE_HAGUE_SCENARIO.name:
        return ROTTERDAM_THE_HAGUE_SCENARIO
    return DEFAULT_SCENARIO


def _to_geojson_point_features(items: Dict[str, Dict], coord_key: str) -> Dict:
    features: List[Dict] = []
    for _, payload in items.items():
        lat, lon = payload[coord_key]
        props = {k: v for k, v in payload.items() if k != coord_key}
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": props,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _to_geojson_route_features(routes: Dict[str, Dict]) -> Dict:
    features: List[Dict] = []
    for _, r in routes.items():
        coords: Iterable[LatLon] = r["path"]
        line_coords = [[lon, lat] for (lat, lon) in coords]
        props = {
          "id": r["id"],
          "label": r["label"],
          "kind": r["kind"],
          "length_m": r["length_m"],
          "turn_count": r["turn_count"],
          "risk_score": r.get("risk_score", 0.0),
        }
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": line_coords},
                "properties": props,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _write_csv(path: Path, rows: Iterable[Dict]):
    rows = list(rows)
    if not rows:
        return
    fieldnames = sorted(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run_export(scenario_name: str) -> None:
    scenario = _scenario_by_name(scenario_name)

    routes = compute_routes(scenario.start, scenario.via, scenario.end)
    analysis = full_analysis(routes)

    out_dir = Path(__file__).parent / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)

    # GeoJSON exports
    routes_geo = _to_geojson_route_features(analysis["routes"])
    with (out_dir / f"routes_{scenario.name}.geojson").open("w", encoding="utf-8") as f:
        json.dump(routes_geo, f, indent=2)

    cps_geo = _to_geojson_point_features(analysis["chokepoints"], "location")
    with (out_dir / f"chokepoints_{scenario.name}.geojson").open(
        "w", encoding="utf-8"
    ) as f:
        json.dump(cps_geo, f, indent=2)

    pois_geo = _to_geojson_point_features(analysis["pois"], "location")
    with (out_dir / f"pois_{scenario.name}.geojson").open("w", encoding="utf-8") as f:
        json.dump(pois_geo, f, indent=2)

    teams_geo = _to_geojson_point_features(analysis["teams"], "location")
    with (out_dir / f"teams_{scenario.name}.geojson").open("w", encoding="utf-8") as f:
        json.dump(teams_geo, f, indent=2)

    # CSV exports – useful as tables in the written report.
    routes_rows = []
    for r in analysis["routes"].values():
        routes_rows.append(
            {
                "id": r["id"],
                "label": r["label"],
                "kind": r["kind"],
                "length_m": r["length_m"],
                "turn_count": r["turn_count"],
            }
        )
    _write_csv(out_dir / f"routes_{scenario.name}.csv", routes_rows)

    _write_csv(
        out_dir / f"chokepoints_{scenario.name}.csv",
        analysis["chokepoints"].values(),
    )
    _write_csv(out_dir / f"pois_{scenario.name}.csv", analysis["pois"].values())
    _write_csv(out_dir / f"teams_{scenario.name}.csv", analysis["teams"].values())

    print(f"Exported analysis for scenario '{scenario.name}' to {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export SA2 chokepoint analysis results to GeoJSON and CSV."
    )
    parser.add_argument(
        "--scenario",
        choices=[
            SCHIPHOL_SCENARIO.name,
            ROTTERDAM_THE_HAGUE_SCENARIO.name,
            DEFAULT_SCENARIO.name,
        ],
        default=DEFAULT_SCENARIO.name,
        help="Scenario to export (defaults to the configured default).",
    )
    args = parser.parse_args()
    run_export(args.scenario)


if __name__ == "__main__":
    main()


