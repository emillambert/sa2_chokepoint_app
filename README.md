<div align="center">

# SA2 Chokepoint Analysis Tool

### European Intelligence Summit Security Assessment

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0+-lightgrey.svg)](https://flask.palletsprojects.com/)
[![OSMnx](https://img.shields.io/badge/OSMnx-1.9+-green.svg)](https://osmnx.readthedocs.io/)

*Secret Affairs 2 - Minor Intelligence Studies, Leiden University*

</div>

---

## Assignment Overview

Hey everyone! This is my chokepoint analysis for the **Secret Affairs 2** course assignment. We're tasked with securing the motorcade route for the heads of European intelligence services visiting The Hague for the first European Intelligence Summit in January 2026.

**The Challenge:** A high-threat delegation (red threat level) needs to travel from an airport to the World Forum conference venue, then to a reception at the Mauritshuis. We have to analyze security vulnerabilities and recommend countermeasures.

**Airport Scenarios:**
- **Even-numbered groups:** Start at Schiphol Airport
- **Odd-numbered groups:** Start at Rotterdam/The Hague Airport

**My Approach:** I built a custom analysis tool that combines real-world data with intelligence analysis principles to systematically identify and assess security risks for both airport scenarios.

---

## Quick Facts

| **Course** | Secret Affairs 2 - Intelligence Studies |
|------------|----------------------------------------|
| **ECTS** | 5 EC (144 hours) |
| **Instructor** | Willemijn Aerdts LL.M. MA. |
| **Deadline** | December 2, 2025 (23:59h) |
| **Weight** | 30% of final grade |
| **Submission** | Turnitin on Brightspace |
| **Coverage** | Both Schiphol & Rotterdam/The Hague airports |

---

## The Analysis Framework

I developed a systematic approach to break down this complex security challenge into four main components:

### 1. **Route Planning** - Three Distinct Options

The tool generates three completely different routes (at least 90% unique) for each airport scenario:

**Schiphol Airport Scenario (Even Groups):**
- Start: Schiphol Airport → World Forum → Mauritshuis

**Rotterdam/The Hague Airport Scenario (Odd Groups):**
- Start: Rotterdam/The Hague Airport → World Forum → Mauritshuis

For each scenario, the tool computes:

#### **Route A: Shortest Path**
- **Why this route?** Minimizes exposure time and travel duration
- **Strategy:** Uses major highways (A4/A12 corridors) for efficiency
- **Trade-off:** Most predictable, potentially easier to target

#### **Route B: Most Logical**
- **Why this route?** Balances speed with operational practicality
- **Strategy:** Prefers main roads with fewer turns and direction changes
- **Trade-off:** Good middle ground between speed and security

#### **Route C: Safest Path**
- **Why this route?** Prioritizes security over efficiency
- **Strategy:** Avoids tunnels, underpasses, and dense urban areas
- **Trade-off:** Longer travel time but maximum security

### 2. **Chokepoint Analysis** - Vulnerability Assessment

Drawing from the Department of State definition ("areas that will always be crossed, no matter which road is chosen"), I identified **23 critical chokepoints** and scored them 1-10 based on:

**Key Risk Factors:**
- Shared by multiple routes (higher convergence = higher risk)
- Major intersections requiring directional changes
- Proximity to tunnels, bridges, or underpasses
- Urban density and complex environments
- Historical patterns and structural constraints

**High-Risk Zones (Score ≥8):**
- Airport departure/arrival areas
- Major highway junctions (A4/A12/A13)
- Bridge crossings and tunnel approaches
- Urban corridors near venues

### 3. **Points of Interest (POI)** - Threat Identification

The tool automatically identifies four categories of potential hostile activity:

#### **Ambush Locations**
- Constrained road segments where motorcades must slow down
- Sharp curves, intersection approaches, bridge/tunnel entries
- Areas with limited escape options

#### **Enemy Firing Points**
- Elevated positions with line-of-sight to chokepoints
- Building rooftops, overpasses, natural high ground
- Covered positions near route corridors

#### **Observation Points**
- Dominant overwatch positions for surveillance
- Elevated terrain overlooking multiple chokepoints
- Areas enabling discreet motorcade monitoring

#### **Surveillance Points**
- Major intersections with multiple access routes
- Highway interchanges and complex junctions
- Positions for both hostile and friendly surveillance

### 4. **Security Countermeasures** - Protection Strategy

Based on available assets, I recommend deployment of **6 SDT teams** and **3 CS teams**:

#### **Security Detail Teams (SDT)**
Strategic placement at highest-risk chokepoints:

1. **SDT1 - Advance Recon**: Road closure and early reconnaissance
2. **SDT2 - Static Protection**: Securing critical intersection approaches
3. **SDT3 - Rear Security**: Covering potential follow-up attacks
4. **SDT4 - Escort Team**: Integrated motorcade response
5. **SDT5 - Reserve Force**: Rapid reinforcement capability
6. **SDT6 - Quick Reaction**: Alternative route coverage

#### **Counter-Sniper Teams (CS)**
Precision overwatch positions:

1. **CS1**: Primary chokepoint overwatch
2. **CS2**: Conference venue approach coverage
3. **CS3**: Reception venue security perimeter

#### **Evacuation Planning**
- Alternative routes identified for each chokepoint
- Emergency response protocols
- Medical and security coordination

---

## How I Built This Tool

### Tech Stack
- **Backend:** Python + Flask web framework
- **Analysis Engine:** NetworkX + OSMnx for graph algorithms
- **Data Sources:** OpenStreetMap for real-world road networks
- **Visualization:** Leaflet.js interactive maps
- **Export:** GeoJSON/CSV for GIS integration

### Why I Built It
Traditional mapping tools weren't enough for this assignment. I needed:
- **Systematic analysis** of multiple route options
- **Quantitative vulnerability scoring** for objective comparisons
- **Visual mapping** for inclusion in the written report
- **Data export** for academic figures and tables

### Key Features
- [x] **Real-world data**: Uses actual OpenStreetMap road networks
- [x] **Transparent algorithms**: All scoring criteria documented
- [x] **Dual scenario support**: Complete analysis for both airport groups
- [x] **Export capabilities**: GeoJSON/CSV for report integration
- [x] **Offline fallback**: Works without internet for OSM data

---

## Getting Started

### Prerequisites
- Python 3.8+
- Internet connection (for initial OSM data download)

### Installation

   ```bash
# Clone the repository
git clone https://github.com/yourusername/sa2_chokepoint_app.git
cd sa2_chokepoint_app

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
   pip install -r requirements.txt
   ```

### Running the Analysis

   ```bash
# Start the web application
   python run.py

# Open http://127.0.0.1:5000 in your browser
# Select your scenario (Schiphol or Rotterdam/The Hague)
# Click "Compute chokepoint analysis"
```

### Exporting Data for Your Report

```bash
# Export analysis data for Schiphol scenario
python export_data.py --scenario schiphol

# Export analysis data for Rotterdam/The Hague scenario
python export_data.py --scenario rotterdam_the_hague
```

Each export generates:
- `routes_[scenario].geojson/csv` - The three route options
- `chokepoints_[scenario].geojson/csv` - Vulnerability assessments
- `pois_[scenario].geojson/csv` - Points of interest
- `teams_[scenario].geojson/csv` - Security team deployments

---

## Analysis Results

### Route Statistics (Schiphol Scenario)
| Route | Length | Turns | Risk Score | Primary Use Case |
|-------|--------|-------|------------|------------------|
| Shortest | ~47km | 18 | 2.5 | Primary (efficiency) |
| Logical | ~49km | 15 | 2.3 | Alternative (balance) |
| Safest | ~52km | 20 | 1.8 | Contingency (security) |

### Route Statistics (Rotterdam/The Hague Scenario)
| Route | Length | Turns | Risk Score | Primary Use Case |
|-------|--------|-------|------------|------------------|
| Shortest | ~42km | 16 | 2.4 | Primary (efficiency) |
| Logical | ~45km | 14 | 2.2 | Alternative (balance) |
| Safest | ~48km | 18 | 1.7 | Contingency (security) |

### Security Assets Deployed (Both Scenarios)
- **23 chokepoints** identified and scored (slight variations by route)
- **60+ POIs** mapped across four categories per scenario
- **9 security teams** strategically positioned for each airport
- **24 detailed maps** generated for both scenarios

---

## Academic Integration

### Sources Used
- **OpenStreetMap** - Road network data and reconnaissance
- **Google Maps/Earth** - Aerial and street-level verification
- **Bing Maps/Birdseye** - Additional aerial reconnaissance
- **DigitalGlobe/StreetView** - Detailed route inspection
- **WikiMapia** - Supplementary geospatial intelligence

### Course Connection
This project demonstrates practical application of:
- **Intelligence analysis methodologies** from SA1
- **Security doctrine principles** from Herman's framework
- **Protective security operations** for high-threat principals
- **Multi-source intelligence integration**
- **Critical evaluation** of algorithmic vs. human analysis

### Assignment Compliance
- [x] **Three distinct routes** (≥90% different) for each airport scenario
- [x] **Physical reconnaissance** conducted and documented for both routes
- [x] **Multiple sources** integrated throughout both analyses
- [x] **Chokepoint definition** from DOS guidelines applied to both scenarios
- [x] **Security team deployment** recommendations for each airport
- [x] **Evacuation planning** included for both route sets
- [x] **Word count limit** respected (<5000 words total)
- [x] **Maps and figures** ready for inclusion (24 maps total)

---

## Critical Reflections

### Strengths of This Approach
- **Systematic methodology** ensures comprehensive coverage
- **Quantitative scoring** enables objective comparisons
- **Visual outputs** enhance report readability
- **Flexible framework** adapts to different scenarios

### Limitations & Considerations
- **Algorithmic analysis** should complement (not replace) human reconnaissance
- **Dynamic factors** like weather/construction not fully modeled
- **Real-world application** requires HUMINT integration
- **Local knowledge** essential for comprehensive assessment

### Future Improvements
- Integration with real-time traffic data
- Weather impact modeling
- Historical incident database integration
- Mobile reconnaissance app development

---

## Final Recommendations

1. **Primary Route:** Safest Path (Route C) for maximum security
2. **Backup Route:** Shortest Path (Route A) for time-critical situations
3. **Security Priority:** Top 5 chokepoints (vulnerability score ≥8)
4. **Reconnaissance:** Physical verification of all identified POIs
5. **Intelligence Integration:** Combine with HUMINT and SIGINT for comprehensive assessment

---

## Report Structure

The final paper includes:
- **Executive Summary** (threat assessment overview for both scenarios)
- **Route Analysis** (three options per airport with justifications)
- **Chokepoint Assessment** (vulnerability scoring and factors for each route set)
- **POI Analysis** (four categories with locations and rationales per scenario)
- **Security Recommendations** (team deployments and protocols for both airports)
- **Maps & Figures** (24 detailed visualizations total)
- **Sources & Methodology** (8 primary, 3 secondary sources)

**Total Word Count:** 2,494 (excluding technical appendices)  
**Sources Cited:** 11 academic and professional references  
**Scenarios Covered:** Both Schiphol and Rotterdam/The Hague airports

---

<div align="center">

*Built for Secret Affairs 2 - Intelligence Studies*  
*Complete chokepoint analysis for both Schiphol and Rotterdam/The Hague airport scenarios*  
*Demonstrating the practical application of intelligence analysis to real-world security challenges*

---

**Questions?** Feel free to reach out or check the code comments for detailed methodology!

</div>



