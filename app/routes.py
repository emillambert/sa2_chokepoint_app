import logging

from flask import Blueprint, current_app, jsonify, render_template, request

from config import (
    DEFAULT_SCENARIO,
    ROTTERDAM_THE_HAGUE_SCENARIO,
    SCHIPHOL_SCENARIO,
)
from .analysis import full_analysis
from .routing import compute_routes


bp = Blueprint("main", __name__)
logger = logging.getLogger(__name__)


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
    """Compute routes and a high-level analysis for the selected scenario."""
    body = request.get_json(silent=True) or {}
    scenario_name = body.get("scenario") or DEFAULT_SCENARIO.name

    if scenario_name == SCHIPHOL_SCENARIO.name:
        scenario = SCHIPHOL_SCENARIO
    elif scenario_name == ROTTERDAM_THE_HAGUE_SCENARIO.name:
        scenario = ROTTERDAM_THE_HAGUE_SCENARIO
    else:
        scenario = DEFAULT_SCENARIO

    logger.info("Starting analysis for scenario=%s", scenario.name)
    try:
        routes = compute_routes(scenario.start, scenario.via, scenario.end)
        analysis = full_analysis(routes)
        analysis["scenario"] = {
            "name": scenario.name,
            "start": scenario.start,
            "via": scenario.via,
            "end": scenario.end,
        }
        logger.info(
            "Analysis complete scenario=%s routes=%d chokepoints=%d pois=%d teams=%d",
            scenario.name,
            len(analysis["routes"]),
            len(analysis["chokepoints"]),
            len(analysis["pois"]),
            len(analysis["teams"]),
        )
        return jsonify(analysis)
    except Exception:
        logger.exception("Analysis failed for scenario=%s", scenario.name)
        return (
            jsonify({"error": "Analysis failed on the server. Check logs for details."}),
            500,
        )


