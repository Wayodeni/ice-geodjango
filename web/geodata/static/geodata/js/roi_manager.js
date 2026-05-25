const map = L.map("map").setView([43.15, 76.95], 8);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "OpenStreetMap contributors",
}).addTo(map);

const drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

const drawControl = new L.Control.Draw({
  draw: {
    marker: false,
    circle: false,
    circlemarker: false,
    polyline: false,
    polygon: {
      allowIntersection: false,
      showArea: true,
    },
    rectangle: {
      showArea: true,
    },
  },
  edit: {
    featureGroup: drawnItems,
    edit: true,
    remove: false,
  },
});

map.addControl(drawControl);

let selectedLayer = null;

const statusLine = document.getElementById("statusLine");
const roiNameInput = document.getElementById("roiNameInput");
const selectedRoiInfo = document.getElementById("selectedRoiInfo");
const jobsList = document.getElementById("jobsList");

function setStatus(text) {
  statusLine.textContent = text;
}

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    return parts.pop().split(";").shift();
  }
  return "";
}

function apiFetch(url, options = {}) {
  const headers = options.headers || {};
  headers["Content-Type"] = "application/json";
  headers["X-CSRFToken"] = getCookie("csrftoken");

  return fetch(url, {
    ...options,
    headers,
  });
}

function getLayerGeometry(layer) {
  const feature = layer.toGeoJSON();
  return feature.geometry;
}

function selectLayer(layer) {
  selectedLayer = layer;

  drawnItems.eachLayer((item) => {
    item.setStyle({
      color: "#2f6fed",
      weight: 2,
      fillOpacity: 0.15,
    });
  });

  selectedLayer.setStyle({
    color: "#e74c3c",
    weight: 3,
    fillOpacity: 0.18,
  });

  roiNameInput.value = layer.roiName || "ROI";

  if (layer.roiId) {
    selectedRoiInfo.textContent = `Selected ROI ID: ${layer.roiId}`;
  } else {
    selectedRoiInfo.textContent = "Selected unsaved ROI.";
  }

  setStatus("ROI selected.");
}

function addRoiLayer(feature) {
  const layer = L.geoJSON(feature, {
    style: {
      color: "#2f6fed",
      weight: 2,
      fillOpacity: 0.15,
    },
  });

  layer.eachLayer((subLayer) => {
    subLayer.roiId = feature.properties.id;
    subLayer.roiName = feature.properties.name;

    subLayer.on("click", () => {
      selectLayer(subLayer);
    });

    subLayer.bindPopup(
      `ROI #${feature.properties.id}<br>${feature.properties.name}`,
    );
    drawnItems.addLayer(subLayer);
  });
}

async function loadRois() {
  drawnItems.clearLayers();
  selectedLayer = null;

  const response = await fetch("/geo/api/rois/");
  const data = await response.json();

  data.features.forEach((feature) => {
    addRoiLayer(feature);
  });

  if (drawnItems.getLayers().length > 0) {
    map.fitBounds(drawnItems.getBounds(), {
      padding: [20, 20],
    });
  }

  setStatus(`Loaded ROIs: ${data.features.length}`);
}

async function saveSelectedRoi() {
  if (!selectedLayer) {
    setStatus("No ROI selected.");
    return;
  }

  const geometry = getLayerGeometry(selectedLayer);
  const name = roiNameInput.value || "ROI";

  if (selectedLayer.roiId) {
    const response = await apiFetch(`/geo/api/rois/${selectedLayer.roiId}/`, {
      method: "PATCH",
      body: JSON.stringify({
        name,
        geometry,
      }),
    });

    if (!response.ok) {
      setStatus("Failed to update ROI.");
      return;
    }

    setStatus("ROI updated.");
  } else {
    const response = await apiFetch("/geo/api/rois/", {
      method: "POST",
      body: JSON.stringify({
        name,
        geometry,
      }),
    });

    if (!response.ok) {
      setStatus("Failed to create ROI.");
      return;
    }

    const feature = await response.json();
    selectedLayer.roiId = feature.properties.id;
    selectedLayer.roiName = feature.properties.name;
    setStatus("ROI created.");
  }

  await loadRois();
}

async function deleteSelectedRoi() {
  if (!selectedLayer) {
    setStatus("No ROI selected.");
    return;
  }

  if (!selectedLayer.roiId) {
    drawnItems.removeLayer(selectedLayer);
    selectedLayer = null;
    setStatus("Unsaved ROI removed.");
    return;
  }

  const response = await apiFetch(`/geo/api/rois/${selectedLayer.roiId}/`, {
    method: "DELETE",
  });

  if (!response.ok) {
    setStatus("Failed to delete ROI.");
    return;
  }

  selectedLayer = null;
  await loadRois();
  setStatus("ROI deleted.");
}

function clearSelection() {
  selectedLayer = null;
  roiNameInput.value = "";
  selectedRoiInfo.textContent = "No ROI selected.";

  drawnItems.eachLayer((item) => {
    item.setStyle({
      color: "#2f6fed",
      weight: 2,
      fillOpacity: 0.15,
    });
  });

  setStatus("Selection cleared.");
}

function selectedSensors() {
  const sensors = [];

  if (document.getElementById("sentinel2Input").checked) {
    sensors.push("sentinel-2-l2a");
  }

  if (document.getElementById("sentinel1Input").checked) {
    sensors.push("sentinel-1-rtc");
  }

  return sensors;
}

async function createJob(runImmediately = false) {
  if (!selectedLayer || !selectedLayer.roiId) {
    setStatus("Select and save ROI before creating job.");
    return;
  }

  const payload = {
    roi_id: selectedLayer.roiId,
    target_date: document.getElementById("targetDateInput").value,
    time_window_days: Number(document.getElementById("timeWindowInput").value),
    selected_sensors: selectedSensors(),
    target_crs: document.getElementById("targetCrsInput").value,
    resolution: Number(document.getElementById("resolutionInput").value),
    max_cloud_cover: Number(document.getElementById("cloudCoverInput").value),
  };

  const response = await apiFetch("/geo/api/jobs/", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    setStatus("Failed to create job.");
    return;
  }

  const job = await response.json();
  setStatus(`Job #${job.id} created.`);

  if (runImmediately) {
    await runJob(job.id);
  }

  await loadJobs();
}

async function runJob(jobId) {
  const response = await apiFetch(`/geo/api/jobs/${jobId}/run/`, {
    method: "POST",
    body: JSON.stringify({}),
  });

  if (!response.ok && response.status !== 409) {
    setStatus(`Failed to run job #${jobId}.`);
    return;
  }

  setStatus(`Job #${jobId} started.`);
  await loadJobs();
}

function jobStatusClass(status) {
  return `status-${status}`;
}

function renderJob(job) {
  const previewLink = job.preview_html
    ? `<a href="${job.preview_html}" target="_blank">Preview</a>`
    : "";

  const cogLink = job.output_cog
    ? `<a href="${job.output_cog}" target="_blank">COG</a>`
    : "";

  const error = job.error_message
    ? `<div class="job-meta status-failed">Error: ${job.error_message}</div>`
    : "";

  return `
        <div class="job-card">
            <div class="job-title">
                Job #${job.id}
                <span class="${jobStatusClass(job.status)}">[${job.status}]</span>
            </div>
            <div class="job-meta">
                ROI: ${job.roi_name || job.roi_id}<br>
                Date: ${job.target_date}, window: ±${job.time_window_days} days<br>
                Sensors: ${job.selected_sensors.join(", ")}<br>
                CRS: ${job.target_crs}, resolution: ${job.resolution} m
            </div>
            ${error}
            <div class="job-actions">
                <button onclick="runJob(${job.id})">Run / rerun</button>
                ${previewLink}
                ${cogLink}
            </div>
        </div>
    `;
}

async function loadJobs() {
  const response = await fetch("/geo/api/jobs/");
  const data = await response.json();

  jobsList.innerHTML = data.results.map(renderJob).join("");

  if (data.results.length === 0) {
    jobsList.innerHTML = "<div class='small-info'>No jobs yet.</div>";
  }
}

map.on(L.Draw.Event.CREATED, (event) => {
  const layer = event.layer;
  drawnItems.addLayer(layer);
  selectLayer(layer);
  setStatus("New ROI drawn. Enter name and save.");
});

map.on(L.Draw.Event.EDITED, () => {
  if (selectedLayer) {
    setStatus("ROI geometry changed. Save ROI to persist changes.");
  }
});

document
  .getElementById("saveRoiButton")
  .addEventListener("click", saveSelectedRoi);
document
  .getElementById("deleteRoiButton")
  .addEventListener("click", deleteSelectedRoi);
document
  .getElementById("clearSelectionButton")
  .addEventListener("click", clearSelection);

document
  .getElementById("createJobButton")
  .addEventListener("click", () => createJob(false));
document
  .getElementById("createAndRunJobButton")
  .addEventListener("click", () => createJob(true));
document
  .getElementById("refreshJobsButton")
  .addEventListener("click", loadJobs);

document.getElementById("fitRoisButton").addEventListener("click", () => {
  if (drawnItems.getLayers().length > 0) {
    map.fitBounds(drawnItems.getBounds(), {
      padding: [20, 20],
    });
  }
});

loadRois();
loadJobs();

setInterval(loadJobs, 5000);
