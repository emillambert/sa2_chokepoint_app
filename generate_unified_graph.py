#!/usr/bin/env python3
"""Generate a unified road network graph covering both airports and The Hague."""

import osmnx as ox
from pathlib import Path
from config import ROTTERDAM_THE_HAGUE_SCENARIO, SCHIPHOL_SCENARIO
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

def calculate_center_and_radius(points):
    """Calculate center point and required radius for all waypoints."""
    # Calculate bounding box
    lats = [lat for lat, lon in points]
    lons = [lon for lat, lon in points]

    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    # Center of bounding box
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2
    center = (center_lat, center_lon)

    # Maximum distance from center to any point
    max_distance = 0
    for point in points:
        distance = haversine_distance(center, point)
        max_distance = max(max_distance, distance)

    # Add 8km buffer for safety
    radius_m = max_distance + 8000

    return center, radius_m

def generate_unified_graph():
    """Generate one graph covering both airports and The Hague."""
    print("🗺️  Generating Unified Road Network Graph")
    print("=" * 60)

    # All waypoints from both scenarios
    all_points = [
        SCHIPHOL_SCENARIO.start,      # Schiphol airport
        SCHIPHOL_SCENARIO.via,         # World Forum (The Hague)
        SCHIPHOL_SCENARIO.end,         # Mauritshuis (The Hague)
        ROTTERDAM_THE_HAGUE_SCENARIO.start,  # Rotterdam airport
    ]

    print("📍 Waypoints to cover:")
    print(f"   • Schiphol Airport: {SCHIPHOL_SCENARIO.start}")
    print(f"   • Rotterdam Airport: {ROTTERDAM_THE_HAGUE_SCENARIO.start}")
    print(f"   • World Forum: {SCHIPHOL_SCENARIO.via}")
    print(f"   • Mauritshuis: {SCHIPHOL_SCENARIO.end}")

    # Calculate center and radius
    center, radius_m = calculate_center_and_radius(all_points)
    print(f"\\n📐 Coverage area:")
    print(f"   • Center: ({center[0]:.4f}, {center[1]:.4f})")
    print(f"   • Radius: {radius_m/1000:.1f} km")

    print("\\n⏳ Downloading unified road network from OpenStreetMap...")
    # Download the graph with high resolution geometries
    G = ox.graph_from_point(center, dist=radius_m, network_type="drive", simplify=False)
    G = ox.distance.add_edge_lengths(G)

    print("🧹 Filtering unsuitable roads for motorcade routes...")

    # Filter out roads unsuitable for motorcades
    edges_to_remove = []
    for u, v, k, data in G.edges(keys=True, data=True):
        highway = data.get("highway", "")
        if isinstance(highway, list):
            highway = highway[0] if highway else ""
        elif not isinstance(highway, str):
            highway = str(highway)

        # Remove completely unusable roads
        if highway in {"footway", "pedestrian", "cycleway", "path", "steps", "track"}:
            edges_to_remove.append((u, v, k))

    # Remove the filtered edges
    for u, v, k in edges_to_remove:
        if G.has_edge(u, v, k):
            G.remove_edge(u, v, k)

    # Clean up isolated nodes
    isolated_nodes = [node for node in G.nodes() if G.degree(node) == 0]
    G.remove_nodes_from(isolated_nodes)

    # Save the unified graph
    output_path = Path("precomputed") / "unified_graph.graphml"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(G, output_path)

    print("✅ Unified graph saved!")
    print(f"   📊 Nodes: {len(G.nodes):,}")
    print(f"   🛣️  Edges: {len(G.edges):,}")
    print(f"   💾 File: {output_path}")

    return G

def verify_airport_coverage(G):
    """Verify that both airports are within the graph coverage."""
    print("\\n🔍 Verifying airport coverage...")

    airports = {
        "Schiphol": SCHIPHOL_SCENARIO.start,
        "Rotterdam": ROTTERDAM_THE_HAGUE_SCENARIO.start
    }

    for name, coords in airports.items():
        # Find nearest node in graph
        nearest_node = ox.nearest_nodes(G, coords[1], coords[0])  # lon, lat
        node_coords = (G.nodes[nearest_node]['y'], G.nodes[nearest_node]['x'])  # lat, lon

        distance = haversine_distance(coords, node_coords)

        if distance < 1000:  # Within 1km = good coverage
            print(f"   ✅ {name}: {distance:.0f}m from terminal")
        else:
            print(f"   ⚠️  {name}: {distance:.0f}m from terminal (may be outside coverage)")

if __name__ == "__main__":
    try:
        G = generate_unified_graph()
        verify_airport_coverage(G)

        print("\\n" + "=" * 60)
        print("🎉 Unified graph generation complete!")
        print("   • Covers both airports and The Hague")
        print("   • Single download for all scenarios")
        print("   • No more coverage gaps at airports")

    except Exception as e:
        print(f"❌ Error generating unified graph: {e}")
        raise

