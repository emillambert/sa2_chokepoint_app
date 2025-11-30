import logging
import json
import pandas as pd
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

from config import (
    DEFAULT_SCENARIO,
    ROTTERDAM_THE_HAGUE_SCENARIO,
    SCHIPHOL_SCENARIO,
)


bp = Blueprint("main", __name__)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
EXPORTS_DIR = BASE_DIR / "exports"


def load_precomputed_analysis(scenario_name: str) -> dict:
    """Load precomputed route analysis data instead of computing it live.

    This avoids loading massive graph files into memory and is suitable for
    memory-constrained environments like render.com.
    """
    try:
        # Map scenario names to export file prefixes
        if scenario_name == SCHIPHOL_SCENARIO.name:
            prefix = "schiphol"
        elif scenario_name == ROTTERDAM_THE_HAGUE_SCENARIO.name:
            prefix = "rotterdam_the_hague"
        else:
            prefix = "schiphol"  # default fallback

        logger.info("Loading precomputed data for scenario=%s", scenario_name)

        # Load routes data
        routes_df = pd.read_csv(EXPORTS_DIR / f"routes_{prefix}.csv")
        routes_geojson = json.loads((EXPORTS_DIR / f"routes_{prefix}.geojson").read_text())

        # Convert routes to the expected format
        routes = {}
        for _, row in routes_df.iterrows():
            route_id = row['id']
            # Find corresponding GeoJSON feature
            feature = next((f for f in routes_geojson['features'] if f['properties'].get('id') == route_id), None)
            if feature:
                # Convert GeoJSON coordinates [lon, lat] to [lat, lon]
                coords = [(coord[1], coord[0]) for coord in feature['geometry']['coordinates']]

                routes[route_id] = {
                    "id": route_id,
                    "label": row['label'],
                    "kind": row['kind'],
                    "path": coords,
                    "length_m": row['length_m'],
                    "estimated_time_min": row['length_m'] / 1000 / 50.0,  # assume 50 km/h average
                    "turn_count": row['turn_count'],
                    "risk_score": 2.5,  # default risk score
                    "description": f"Precomputed {row['kind']} route",
                    "nodes": [],  # Will be populated by analysis
                    "nodes_meta": [],
                    "edges_meta": []
                }

        # Load chokepoints
        chokepoints_df = pd.read_csv(EXPORTS_DIR / f"chokepoints_{prefix}.csv")
        chokepoints = {}
        for _, row in chokepoints_df.iterrows():
            # Parse location string like "(52.2726471, 4.5761073)"
            location_str = row['location'].strip('()')
            lat, lon = map(float, location_str.split(', '))

            # Parse routes_affected string like "['r_logical', 'r_safest', 'r_shortest']"
            routes_affected = row['routes_affected'].strip('[]').replace("'", "").split(', ')
            routes_affected = [r.strip() for r in routes_affected]

            # Parse factors string
            factors_str = row['factors'].strip('[]').replace("'", "").split(', ')
            factors = [f.strip() for f in factors_str if f.strip()]

            chokepoints[row['id']] = {
                "id": row['id'],
                "location": (lat, lon),
                "type": row['type'],
                "routes_affected": routes_affected,
                "vulnerability_score": row['vulnerability_score'],
                "factors": factors,
                "description": row['description']
            }

        # Load POIs
        pois_df = pd.read_csv(EXPORTS_DIR / f"pois_{prefix}.csv")
        pois = {}
        for _, row in pois_df.iterrows():
            # Parse location string
            location_str = row['location'].strip('()')
            lat, lon = map(float, location_str.split(', '))

            pois[row['id']] = {
                "id": row['id'],
                "type": row['type'],
                "location": (lat, lon),
                "related_route": row['related_route'] if pd.notna(row['related_route']) else None,
                "related_chokepoint": row['related_chokepoint'] if pd.notna(row['related_chokepoint']) else None,
                "description": row['description']
            }

        # Load teams
        teams_df = pd.read_csv(EXPORTS_DIR / f"teams_{prefix}.csv")
        teams = {}
        for _, row in teams_df.iterrows():
            # Parse location string
            location_str = row['location'].strip('()')
            lat, lon = map(float, location_str.split(', '))

            teams[row['id']] = {
                "id": row['id'],
                "type": row['type'],
                "location": (lat, lon),
                "assigned_to": row['assigned_to'] if pd.notna(row['assigned_to']) else None,
                "role_description": row['role_description']
            }

        # Build the analysis result
        analysis = {
            "routes": routes,
            "chokepoints": chokepoints,
            "pois": pois,
            "teams": teams,
        }

        logger.info(
            "Loaded precomputed analysis: routes=%d chokepoints=%d pois=%d teams=%d",
            len(analysis["routes"]),
            len(analysis["chokepoints"]),
            len(analysis["pois"]),
            len(analysis["teams"]),
        )

        return analysis

    except Exception as e:
        logger.exception("Failed to load precomputed analysis for scenario=%s", scenario_name)
        raise


@bp.route("/")
def index():
    """Render the main map UI."""
    return render_template("index.html")


@bp.route("/favicon.ico")
def favicon():
    """Serve the favicon so browsers do not log a 404."""
    return current_app.send_static_file("favicon.png")


@bp.route("/api/health")
def health():
    """Simple health check endpoint."""
    return jsonify({"status": "ok"})


@bp.route("/api/analyze", methods=["POST"])
def analyze():
    """Load precomputed routes and analysis for the selected scenario."""
    body = request.get_json(silent=True) or {}
    scenario_name = body.get("scenario") or DEFAULT_SCENARIO.name

    if scenario_name == SCHIPHOL_SCENARIO.name:
        scenario = SCHIPHOL_SCENARIO
    elif scenario_name == ROTTERDAM_THE_HAGUE_SCENARIO.name:
        scenario = ROTTERDAM_THE_HAGUE_SCENARIO
    else:
        scenario = DEFAULT_SCENARIO

    logger.info("Loading analysis for scenario=%s", scenario.name)
    try:
        # Load precomputed data with improved POI coverage
        analysis = load_precomputed_analysis(scenario.name)
        analysis["scenario"] = {
            "name": scenario.name,
            "start": scenario.start,
            "via": scenario.via,
            "end": scenario.end,
        }
        logger.info(
            "Analysis loaded scenario=%s routes=%d chokepoints=%d pois=%d teams=%d",
            scenario.name,
            len(analysis["routes"]),
            len(analysis["chokepoints"]),
            len(analysis["pois"]),
            len(analysis["teams"]),
        )
        # Add cache control headers to prevent browser caching
        response = jsonify(analysis)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except Exception:
        logger.exception("Analysis failed for scenario=%s", scenario.name)
        response = jsonify({"error": "Analysis failed on the server. Check logs for details."})
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response, 500


