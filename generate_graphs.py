#!/usr/bin/env python3
"""
Generate pre-computed road graphs for both Schiphol and Rotterdam scenarios.
These graphs are optimized for cloud deployment and include only major roads.
"""

import logging
import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from config import SCHIPHOL_SCENARIO, ROTTERDAM_THE_HAGUE_SCENARIO
import osmnx as ox
from osmnx import distance as ox_distance

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _normalize_highway(value):
    """Highway tags can be strings, lists or missing."""
    if isinstance(value, list):
        return str(value[0])
    if isinstance(value, tuple):
        return str(value[0])
    if value is None:
        return ""
    return str(value)

def generate_scenario_graph(scenario_name: str, scenario_obj, output_file: Path):
    """Generate and save an optimized graph for a specific scenario."""
    logger.info(f"Generating graph for {scenario_name}")

    # Calculate center point between start and end to ensure full route coverage
    center_lat = (scenario_obj.start[0] + scenario_obj.end[0]) / 2
    center_lon = (scenario_obj.start[1] + scenario_obj.end[1]) / 2
    center = (center_lat, center_lon)

    # Use larger radius to ensure route connectivity
    G = ox.graph_from_point(center, dist=20000, network_type="drive", simplify=True)
    G = ox_distance.add_edge_lengths(G)

    logger.info(f"Initial graph: {len(G.nodes)} nodes, {len(G.edges)} edges")

    # Conservative filtering to keep connectivity while prioritizing major roads
    edges_to_remove = []
    for u, v, k, data in G.edges(keys=True, data=True):
        highway = _normalize_highway(data.get("highway", ""))
        # Remove only the least suitable roads, keep more connectivity
        if highway in {"footway", "pedestrian", "cycleway", "path", "steps", "track", "service"}:
            edges_to_remove.append((u, v, k))
        # Keep residential but penalize it in routing weights
        # This maintains connectivity while still preferring major roads

    # Remove filtered edges
    for u, v, k in edges_to_remove:
        if G.has_edge(u, v, k):
            G.remove_edge(u, v, k)

    # Remove isolated nodes
    isolated_nodes = [node for node in G.nodes() if G.degree(node) == 0]
    G.remove_nodes_from(isolated_nodes)

    logger.info(f"Filtered graph: {len(G.nodes)} nodes, {len(G.edges)} edges")

    # Save the optimized graph
    ox.save_graphml(G, output_file)
    logger.info(f"Saved {scenario_name} graph to {output_file}")

    return G

def main():
    """Generate graphs for both scenarios."""
    logger.info("Starting graph generation for SA2 Chokepoint Analysis")

    # Create precomputed graphs directory
    graphs_dir = Path("precomputed_graphs")
    graphs_dir.mkdir(exist_ok=True)

    # Generate Schiphol graph
    schiphol_file = graphs_dir / "schiphol_graph.graphml"
    generate_scenario_graph("Schiphol", SCHIPHOL_SCENARIO, schiphol_file)

    # Generate Rotterdam graph
    rotterdam_file = graphs_dir / "rotterdam_graph.graphml"
    generate_scenario_graph("Rotterdam", ROTTERDAM_THE_HAGUE_SCENARIO, rotterdam_file)

    logger.info("Graph generation completed!")
    logger.info("Add the generated .graphml files to your repository for cloud deployment.")

if __name__ == "__main__":
    main()
