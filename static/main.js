let map;
let routeLayers = [];
let chokepointLayers = [];
let poiLayers = [];
let teamLayers = [];

function initMap() {
  map = L.map("map").setView([52.08, 4.3], 11);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);
}

window.addEventListener("DOMContentLoaded", () => {
  initMap();

  const button = document.getElementById("analyze-btn");
  const summary = document.getElementById("summary");
  const scenarioSelect = document.getElementById("scenario");

  button.addEventListener("click", async () => {
    button.disabled = true;
    summary.textContent = "Running analysis...";

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: scenarioSelect.value }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      renderAnalysis(data, summary);
    } catch (err) {
      console.error(err);
      summary.textContent =
        "Analysis failed – check the server logs or your internet connection for map data.";
    } finally {
      button.disabled = false;
    }
  });
});

function clearRoutes() {
  routeLayers.forEach((layer) => map.removeLayer(layer));
  routeLayers = [];
}

function clearMarkers() {
  chokepointLayers.forEach((layer) => map.removeLayer(layer));
  poiLayers.forEach((layer) => map.removeLayer(layer));
  teamLayers.forEach((layer) => map.removeLayer(layer));
  chokepointLayers = [];
  poiLayers = [];
  teamLayers = [];
}

function renderAnalysis(data, summaryEl) {
  clearRoutes();
  clearMarkers();

  const colours = {
    r_shortest: "#ef4444",
    r_logical: "#3b82f6",
    r_safest: "#10b981",
  };

  const bounds = [];
  const lines = [];

  for (const [routeId, route] of Object.entries(data.routes)) {
    const latlngs = route.path.map((p) => L.latLng(p[0], p[1]));
    const line = L.polyline(latlngs, {
      color: colours[routeId] || "#4b5563",
      weight: 5,
      opacity: 0.9,
    }).addTo(map);
    routeLayers.push(line);
    bounds.push(...latlngs);

    lines.push(
      `<li><strong>${route.label}</strong>: ${(route.length_m / 1000).toFixed(
        1
      )} km, approx. ${route.turn_count} turns</li>`
    );
  }

  // Overlay chokepoints, POIs and security teams.
  renderChokepoints(data.chokepoints);
  renderPois(data.pois);
  renderTeams(data.teams);

  if (bounds.length) {
    map.fitBounds(L.latLngBounds(bounds), { padding: [20, 20] });
  }

  const chokepointCount = Object.keys(data.chokepoints || {}).length;
  const poiValues = Object.values(data.pois || {});
  const poiCounts = {
    ambush_location: 0,
    enemy_firing_point: 0,
    enemy_observation_point: 0,
    surveillance_point: 0,
  };
  poiValues.forEach((p) => {
    if (poiCounts[p.type] !== undefined) {
      poiCounts[p.type] += 1;
    }
  });

  const teamValues = Object.values(data.teams || {});
  const sdtCount = teamValues.filter((t) => t.type === "SDT").length;
  const csCount = teamValues.filter((t) => t.type === "CS").length;

  summaryEl.innerHTML = `
    <p>Scenario: <strong>${data.scenario.name}</strong></p>
    <p>Three routes have been computed between the airport, World Forum and Mauritshuis.</p>
    <ul>${lines.join("")}</ul>
    <h3>Chokepoints</h3>
    <p>${chokepointCount} chokepoints identified where multiple routes converge or are structurally constrained.</p>
    <h3>Points of Interest</h3>
    <ul>
      <li><span class="legend-swatch legend-ambush"></span> Ambush locations: ${poiCounts.ambush_location}</li>
      <li><span class="legend-swatch legend-fire"></span> Enemy firing points: ${poiCounts.enemy_firing_point}</li>
      <li><span class="legend-swatch legend-observation"></span> Observation points: ${poiCounts.enemy_observation_point}</li>
      <li><span class="legend-swatch legend-surveillance"></span> Surveillance points: ${poiCounts.surveillance_point}</li>
    </ul>
    <h3>Security teams</h3>
    <p><span class="legend-swatch legend-sdt"></span> SDT teams: ${sdtCount}, <span class="legend-swatch legend-cs"></span> CS teams: ${csCount}.</p>
    <p>Use this visualisation together with your manual reconnaissance to write up Parts 1–4 of the chokepoint analysis.</p>
  `;
}

function renderChokepoints(chokepoints) {
  Object.values(chokepoints || {}).forEach((cp) => {
    const [lat, lon] = cp.location;
    const marker = L.circleMarker([lat, lon], {
      radius: 6,
      color: "#b91c1c",
      weight: 2,
      fillColor: "#ef4444",
      fillOpacity: 0.9,
    }).addTo(map);
    marker.bindPopup(
      `<strong>Chokepoint ${cp.id}</strong><br />Vulnerability: ${cp.vulnerability_score.toFixed(
        1
      )}/10<br />${cp.description}`
    );
    chokepointLayers.push(marker);
  });
}

function renderPois(pois) {
  const colours = {
    ambush_location: "#f97316",
    enemy_firing_point: "#7f1d1d",
    enemy_observation_point: "#0ea5e9",
    surveillance_point: "#6366f1",
  };

  Object.values(pois || {}).forEach((poi) => {
    const [lat, lon] = poi.location;
    const marker = L.circleMarker([lat, lon], {
      radius: 4,
      color: colours[poi.type] || "#4b5563",
      weight: 1.5,
      fillColor: colours[poi.type] || "#4b5563",
      fillOpacity: 0.85,
    }).addTo(map);
    marker.bindPopup(
      `<strong>${poi.type.replace(/_/g, " ")}</strong><br />${poi.description}`
    );
    poiLayers.push(marker);
  });
}

function renderTeams(teams) {
  Object.values(teams || {}).forEach((team) => {
    const [lat, lon] = team.location;
    const isCS = team.type === "CS";
    const marker = L.circleMarker([lat, lon], {
      radius: isCS ? 6 : 5,
      color: isCS ? "#7c3aed" : "#15803d",
      weight: 2,
      fillColor: isCS ? "#a855f7" : "#22c55e",
      fillOpacity: 0.9,
    }).addTo(map);
    marker.bindPopup(
      `<strong>${team.id} (${team.type})</strong><br />Assigned to: ${
        team.assigned_to || "general coverage"
      }<br />${team.role_description}`
    );
    teamLayers.push(marker);
  });
}

