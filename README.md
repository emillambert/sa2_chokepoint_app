# SA2 Chokepoint Analysis Tool (From-Scratch Implementation)

This is a small, self-contained Python/Flask application created from scratch
to support the **Secret Affairs 2 chokepoint-analysis assignment**. It is
independent of the other project code and focuses on:

- computing three distinct routes (shortest, most logical, safest)
- identifying chokepoints and scoring their vulnerability
- highlighting points of interest (POIs)
- suggesting placements for six SDT teams and three CS teams

## Quick start

1. Create and activate a virtual environment (optional but recommended).
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run the development server:

   ```bash
   python run.py
   ```

4. Open the app in your browser at `http://127.0.0.1:5000/`.

The app will show an interactive map of the The Hague region. Use the scenario
selector (Schiphol vs. Rotterdam/The Hague airport) and click the button to
compute the chokepoint analysis.

## How the analysis maps to the assignment

- **Part 1 – Routes**: the backend uses OpenStreetMap data to construct a road
  network and computes three routes between the airport, World Forum and
  Mauritshuis:
  - *Shortest*: graph shortest-path by distance.
  - *Most logical*: prefers main roads and penalises frequent turns.
  - *Safest*: avoids tunnels, narrow residential streets and complex dense
    areas where possible.
- **Part 2 – Chokepoints**: nodes that appear on multiple routes (especially
  all three) and/or at major intersections are treated as chokepoints and are
  scored (1–10) using simple, transparent heuristics such as:
  - shared by multiple routes
  - major intersection
  - near tunnels, bridges or dense urban areas
- **Part 3 – POIs**: for each route and chokepoint the app proposes:
  - *ambush locations* (constrained segments where the convoy must slow)
  - *enemy firing points* (positions with line of sight to chokepoints)
  - *observation points* (overwatch of routes/chokepoints)
  - *surveillance points* (intersections with many access/exit options)
- **Part 4 – Countermeasures**: the six SDT teams and three CS teams are
  placed near the highest‑risk chokepoints with role descriptions that you can
  adapt into your own plan (advance recon, static protection, overwatch, QRF,
  etc.).

The tool is deliberately rule‑based so you can explain and, if needed,
critically evaluate its assumptions in your written report.

## Exporting data for maps and tables

You can export the current logic to GeoJSON and CSV for use in GIS tools
or directly in your paper.

From the `sa2_chokepoint_app` directory:

```bash
python export_data.py --scenario schiphol
```

This writes the following files into `exports/`:

- `routes_<scenario>.geojson` and `.csv`
- `chokepoints_<scenario>.geojson` and `.csv`
- `pois_<scenario>.geojson` and `.csv`
- `teams_<scenario>.geojson` and `.csv`

These contain exactly what you see on the map: geometry plus attributes you
can summarise in text or convert into figures/tables for the assignment.



