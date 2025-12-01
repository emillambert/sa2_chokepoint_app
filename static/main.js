let map;
let routeLayers = [];
let chokepointLayers = [];
let poiLayers = [];
let teamLayers = [];

// Cache management functions
function saveAnalysisToCache(scenario, data) {
  const cacheKey = `analysis_${scenario}`;
  const cacheData = {
    data: data,
    timestamp: Date.now(),
    scenario: scenario
  };
  try {
    localStorage.setItem(cacheKey, JSON.stringify(cacheData));
  } catch (e) {
    console.warn('Failed to save analysis to cache:', e);
  }
}

function loadAnalysisFromCache(scenario) {
  const cacheKey = `analysis_${scenario}`;
  const cached = localStorage.getItem(cacheKey);
  if (cached) {
    try {
      return JSON.parse(cached);
    } catch (e) {
      console.warn('Failed to parse cached analysis data:', e);
      return null;
    }
  }
  return null;
}

function getTimeAgo(timestamp) {
  const now = Date.now();
  const diff = now - timestamp;
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? '' : 's'} ago`;
}

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

  // Load cached data on startup
  const cachedData = loadAnalysisFromCache(scenarioSelect.value);
  if (cachedData) {
    renderAnalysis(cachedData.data, summary, cachedData.timestamp);
  }

  // Handle scenario changes - load cached data for new scenario
  scenarioSelect.addEventListener("change", () => {
    clearRoutes();
    clearMarkers();

    const newCachedData = loadAnalysisFromCache(scenarioSelect.value);
    if (newCachedData) {
      renderAnalysis(newCachedData.data, summary, newCachedData.timestamp);
    } else {
      summary.innerHTML = '<p>Select a scenario and click "Compute chokepoint analysis" to begin.</p>';
    }
  });

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

      // Save to cache
      saveAnalysisToCache(scenarioSelect.value, data);

      // Render fresh data
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

function renderAnalysis(data, summaryEl, cachedTimestamp = null) {
  clearRoutes();
  clearMarkers();

  const colours = {
    r_shortest: "#ef4444",
    r_logical: "#3b82f6",
    r_safest: "#10b981",
    r_safe_manual: "#8b5cf6",  // Purple for the manual safe route
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

  // Overlay chokepoints, POIs, security teams, and road work.
  renderChokepoints(data.chokepoints);
  renderPois(data.pois);
  renderTeams(data.teams);
  renderRoadWork(data.roadwork || []);

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

  const roadworkCount = Object.keys(data.roadwork || {}).length;
  const routeCount = Object.keys(data.routes || {}).length;
  const routeText = routeCount === 1 ? "route has" : "routes have";

  // Add cache info if applicable
  const cacheInfo = cachedTimestamp
    ? `<p style="font-size: 0.9em; color: #666; margin-top: 8px;">
        <em>Data loaded from cache (${getTimeAgo(cachedTimestamp)})</em>
        <button id="refresh-btn" style="margin-left: 8px; padding: 2px 8px; font-size: 0.8em;">Refresh</button>
      </p>`
    : '';

  // Create route legend
  const routeLegendItems = [];
  if (data.routes.r_shortest) {
    routeLegendItems.push(`<li><span class="legend-swatch legend-shortest"></span> Shortest route (red) - ${(data.routes.r_shortest.length_m / 1000).toFixed(1)}km</li>`);
  }
  if (data.routes.r_logical) {
    routeLegendItems.push(`<li><span class="legend-swatch legend-logical"></span> Most logical route (blue) - ${(data.routes.r_logical.length_m / 1000).toFixed(1)}km</li>`);
  }
  if (data.routes.r_safest) {
    routeLegendItems.push(`<li><span class="legend-swatch legend-safest"></span> Safest route (green) - ${(data.routes.r_safest.length_m / 1000).toFixed(1)}km</li>`);
  }
  if (data.routes.r_safe_manual) {
    routeLegendItems.push(`<li><span class="legend-swatch legend-safe-manual"></span> Safe route (manual, purple) - ${(data.routes.r_safe_manual.length_m / 1000).toFixed(1)}km</li>`);
  }

  summaryEl.innerHTML = `
    <p>Scenario: <strong>${data.scenario.name}</strong></p>
    <p>${routeCount} ${routeText} been computed between the airport, World Forum and Mauritshuis.</p>
    <ul>${lines.join("")}</ul>
    <h3>Route Legend</h3>
    <ul>
      ${routeLegendItems.join("")}
    </ul>
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
    ${roadworkCount > 0 ? `<h3>Road Work</h3><p>${roadworkCount} road work locations identified for January 2026.</p>` : ''}
    <p>Use this visualisation together with your manual reconnaissance to write up Parts 1–4 of the chokepoint analysis.</p>
    ${cacheInfo}
  `;

  // Add refresh button handler
  if (cachedTimestamp) {
    setTimeout(() => {
      const refreshBtn = document.getElementById("refresh-btn");
      if (refreshBtn) {
        refreshBtn.addEventListener("click", () => {
          const analyzeBtn = document.getElementById("analyze-btn");
          if (analyzeBtn) {
            analyzeBtn.click();
          }
        });
      }
    }, 0);
  }
}

function createStreetViewLink(lat, lon, title) {
  // Free Google Street View URL that actually opens Street View
  const streetViewUrl = `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lon}&heading=0&pitch=0&fov=80`;

  return `<br><a href="${streetViewUrl}" target="_blank" style="color: #2563eb;">Street View</a>`;
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
      )}/10<br />${cp.description}
      ${createStreetViewLink(lat, lon, `Chokepoint ${cp.id}`)}`
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
      `<strong>${poi.type.replace(/_/g, " ")}</strong><br />${poi.description}
      ${createStreetViewLink(lat, lon, poi.type)}`
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
      }<br />${team.role_description}
      ${createStreetViewLink(lat, lon, `${team.id} Team`)}`
    );
    teamLayers.push(marker);
  });
}

function renderRoadWork(roadwork) {
  Object.values(roadwork || {}).forEach((rw) => {
    const [lat, lon] = rw.location;
    const marker = L.circleMarker([lat, lon], {
      radius: 5,
      color: "#f59e0b",  // Amber color for road work
      weight: 2,
      fillColor: "#fbbf24",
      fillOpacity: 0.9,
    }).addTo(map);

    const dateInfo = [];
    if (rw.start_date) dateInfo.push(`Start: ${rw.start_date}`);
    if (rw.end_date) dateInfo.push(`End: ${rw.end_date}`);

    marker.bindPopup(
      `<strong>Road Work</strong><br />${rw.description}<br />${
        dateInfo.length > 0 ? dateInfo.join('<br />') + '<br />' : ''
      }Affected roads: ${rw.affected_roads.join(', ') || 'Unknown'}
      ${createStreetViewLink(lat, lon, 'Road Work')}`
    );
    teamLayers.push(marker);  // Reuse teamLayers array for road work markers
  });
}

