<div align="center">

# SA2 Chokepoint Analysis Tool  

### Motorcade Security Assessment – European Intelligence Summit

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0+-lightgrey.svg)](https://flask.palletsprojects.com/)
[![OSMnx](https://img.shields.io/badge/OSMnx-1.9+-green.svg)](https://osmnx.readthedocs.io/)

*Secret Affairs 2 – Minor Intelligence Studies, Leiden University*  [oai_citation:0‡2025-2026 Syllabus Secret Affairs 2.pdf](file-service://file-Tb6ZzZ53kfZMWUoJYVSaYY)  

</div>

---

## 1. Purpose of this Project

This repository contains a student-built analysis tool for the **chokepoint assignment** in the course **Secret Affairs 2** (SA2).

Scenario (as in the assignment):

- In **January 2026**, the first **European Intelligence Summit** takes place in The Hague.
- Heads of European intelligence services attend, accompanied by high-risk delegations (red threat level).
- A motorcade in armoured vehicles, with police escort, must travel:
  - From an **airport** (Schiphol or Rotterdam/The Hague),
  - To the **World Forum** (conference venue),
  - And then to the **Mauritshuis** (reception with the heads of MIVD/AIVD).

The task is to identify vulnerable parts of the routes (“chokepoints”), assess risk, and recommend realistic security countermeasures.

This tool supports that task by turning the assignment into a structured, repeatable analysis based on real-world map data.

---

## 2. What the Tool Does (In Plain Language)

For each airport scenario (Schiphol or Rotterdam/The Hague), the tool:

1. **Generates three distinct routes** between:
   - Airport → World Forum → Mauritshuis  
   - Routes are:
     - **Shortest route** – minimal travel time.
     - **Most logical route** – practical, with fewer turns and clear routing.
     - **Safest route** – prioritises security over speed (e.g. avoids tunnels and dense urban areas).

2. **Identifies chokepoints**  
   - Points that **must** be passed, regardless of the route chosen  
     (e.g. departure areas, key junctions, bridges, tunnels).
   - Each chokepoint is given a **1–10 vulnerability score** based on:
     - Route convergence (how many routes share it),
     - Road layout (intersections, merges, forced slow-downs),
     - Surrounding environment (urban density, terrain),
     - Potential for concealment or surprise.

3. **Maps points of interest (POIs) relevant to hostile action**
   - **Ambush locations** – where the motorcade must slow down and has limited options.
   - **Enemy firing points** – elevated or covered positions with a line of sight on the route.
   - **Observation points** – good positions for discreet, long-range surveillance.
   - **Surveillance points** – major junctions and interchanges that facilitate monitoring of multiple access routes.

4. **Suggests deployment of security assets**
   - Placement of **6 Security Detail Teams (SDT)** along the routes.
   - Placement of **3 Counter-Sniper (CS) teams** on suitable overwatch positions.
   - Basic **evacuation routes and contingencies** for high-risk chokepoints.

5. **Produces maps and data tables**
   - Output can be used directly in the written assignment:
     - Route overviews,
     - Chokepoint lists,
     - POI overviews,
     - Security team positioning maps.

---

## 3. Overview of the Analysis Logic

### 3.1 Route Types

For each airport:

- **Route A – Shortest**
  - Objective: minimise time and total distance.
  - Typical pattern: major highways, as direct as possible.
  - Advantage: reduced time “on the road”.
  - Disadvantage: predictable and more easily targeted.

- **Route B – Most Logical**
  - Objective: balance between speed, clarity, and operational practicality.
  - Fewer sharp turns and fewer changes in direction.
  - Suitable as a “standard” option that still stays relatively efficient.

- **Route C – Safest**
  - Objective: limit exposure to high-risk environments.
  - Avoids (as far as possible):
    - Tunnels, underpasses, tight urban areas.
  - Might be longer in time and distance, but more defensible.

### 3.2 Chokepoint Scoring (1–10)

The vulnerability score combines:

- **Structural factors**  
  – bridges, tunnels, roundabouts, forced lane merges.
- **Route convergence**  
  – chokepoints used by multiple routes.
- **Surrounding environment**  
  – dense urban fabric, confined spaces, limited escape options.
- **Potential hostile advantage**  
  – cover, concealment, or elevated positions nearby.

Higher scores (≥ 8) indicate locations that deserve priority security measures.

---

## 4. Main Outputs (What You Can Use in Your Paper)

The tool is built to generate material that can be directly integrated into the SA2 written assignment:

- **Route tables**  
  - For each airport: three route options with distance, approximate number of turns, and indicative risk scores.

- **Chokepoint overview**  
  - List of chokepoints with:
    - Type (bridge, junction, tunnel, etc.),
    - Vulnerability score,
    - Short justification.

- **POI overview**  
  - Grouped by category (ambush, firing, observation, surveillance),
  - Short motivation per point.

- **Team deployment overview**
  - Suggested positions and tasks for:
    - SDT1–SDT6,
    - CS1–CS3.
  - Can be converted into an operational concept and added to your maps.

- **Map material**
  - The underlying spatial data can be exported (e.g. GeoJSON/CSV) to be used in GIS tools or as figures in the report.

All of this is meant to **support** your own field reconnaissance and written argumentation, not to replace it.
