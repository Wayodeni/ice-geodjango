function roiManager() {
  return {
    map: null,
    drawnItems: null,
    previewLayers: {},
    selectedLayer: null,
    visiblePreviewJobIds: [],
    refreshTimer: null,

    statusText: "Draw polygon or rectangle to create ROI.",
    selectedRoiText: "No ROI selected.",
    roiName: "",
    jobs: [],

    jobForm: {
      target_date: "2024-08-01",
      time_window_days: 7,
      use_sentinel2: true,
      use_sentinel1: false,
      target_crs: "EPSG:32643",
      resolution: 10,
      max_cloud_cover: 40,
    },

    init() {
      this.initMap();
      this.loadRois();
      this.loadJobs();

      this.refreshTimer = setInterval(() => {
        this.loadJobs();
      }, 5000);
    },

    initMap() {
      this.map = L.map("map").setView([43.15, 76.95], 8);

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "OpenStreetMap contributors",
      }).addTo(this.map);

      this.drawnItems = new L.FeatureGroup();
      this.map.addLayer(this.drawnItems);

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
          featureGroup: this.drawnItems,
          edit: true,
          remove: false,
        },
      });

      this.map.addControl(drawControl);

      this.map.on(L.Draw.Event.CREATED, (event) => {
        const layer = event.layer;
        this.drawnItems.addLayer(layer);
        this.selectLayer(layer);
        this.setStatus("New ROI drawn. Enter name and save.");
      });

      this.map.on(L.Draw.Event.EDITED, () => {
        if (this.selectedLayer) {
          this.setStatus("ROI geometry changed. Save ROI to persist changes.");
        }
      });
    },

    setStatus(text) {
      this.statusText = text;
    },

    getCookie(name) {
      const value = `; ${document.cookie}`;
      const parts = value.split(`; ${name}=`);

      if (parts.length === 2) {
        return parts.pop().split(";").shift();
      }

      return "";
    },

    async apiFetch(url, options = {}) {
      const headers = options.headers || {};
      headers["Content-Type"] = "application/json";
      headers["X-CSRFToken"] = this.getCookie("csrftoken");

      return fetch(url, {
        ...options,
        headers,
      });
    },

    getLayerGeometry(layer) {
      return layer.toGeoJSON().geometry;
    },

    resetLayerStyles() {
      this.drawnItems.eachLayer((layer) => {
        if (layer.setStyle) {
          layer.setStyle({
            color: "#2f6fed",
            weight: 2,
            fillOpacity: 0.15,
          });
        }
      });
    },

    clearPreviews() {
      Object.values(this.previewLayers).forEach((layer) => {
        this.map.removeLayer(layer);
      });

      this.previewLayers = {};
      this.visiblePreviewJobIds = [];
    },

    selectLayer(layer) {
      this.selectedLayer = layer;
      this.resetLayerStyles();

      if (this.selectedLayer.setStyle) {
        this.selectedLayer.setStyle({
          color: "#e74c3c",
          weight: 3,
          fillOpacity: 0.18,
        });
      }

      this.roiName = layer.roiName || "ROI";
      this.selectedRoiText = layer.roiId
        ? `Selected ROI ID: ${layer.roiId}`
        : "Selected unsaved ROI.";

      this.setStatus("ROI selected.");
    },

    addRoiLayer(feature) {
      const layerGroup = L.geoJSON(feature, {
        style: {
          color: "#2f6fed",
          weight: 2,
          fillOpacity: 0.15,
        },
      });

      layerGroup.eachLayer((layer) => {
        layer.roiId = feature.properties.id;
        layer.roiName = feature.properties.name;

        layer.on("click", () => {
          this.selectLayer(layer);
        });

        layer.bindPopup(
          `ROI #${feature.properties.id}<br>${feature.properties.name}`,
        );
        this.drawnItems.addLayer(layer);
      });
    },

    async loadRois() {
      this.drawnItems.clearLayers();
      this.selectedLayer = null;
      this.roiName = "";
      this.selectedRoiText = "No ROI selected.";

      const response = await fetch("/geo/api/rois/");

      if (!response.ok) {
        this.setStatus("Failed to load ROIs.");
        return;
      }

      const data = await response.json();
      const features = data.features || [];

      features.forEach((feature) => {
        this.addRoiLayer(feature);
      });

      if (this.drawnItems.getLayers().length > 0) {
        this.map.fitBounds(this.drawnItems.getBounds(), {
          padding: [20, 20],
        });
      }

      this.setStatus(`Loaded ROIs: ${features.length}`);
    },

    async saveSelectedRoi() {
      if (!this.selectedLayer) {
        this.setStatus("No ROI selected.");
        return;
      }

      const geometry = this.getLayerGeometry(this.selectedLayer);
      const name = this.roiName || "ROI";

      if (this.selectedLayer.roiId) {
        const response = await this.apiFetch(
          `/geo/api/rois/${this.selectedLayer.roiId}/`,
          {
            method: "PATCH",
            body: JSON.stringify({
              name,
              geometry,
            }),
          },
        );

        if (!response.ok) {
          this.setStatus("Failed to update ROI.");
          return;
        }

        this.setStatus("ROI updated.");
      } else {
        const response = await this.apiFetch("/geo/api/rois/", {
          method: "POST",
          body: JSON.stringify({
            name,
            geometry,
          }),
        });

        if (!response.ok) {
          this.setStatus("Failed to create ROI.");
          return;
        }

        const feature = await response.json();
        this.selectedLayer.roiId = feature.properties.id;
        this.selectedLayer.roiName = feature.properties.name;
        this.setStatus("ROI created.");
      }

      await this.loadRois();
    },

    async deleteSelectedRoi() {
      if (!this.selectedLayer) {
        this.setStatus("No ROI selected.");
        return;
      }

      if (!this.selectedLayer.roiId) {
        this.drawnItems.removeLayer(this.selectedLayer);
        this.clearSelection();
        this.setStatus("Unsaved ROI removed.");
        return;
      }

      const response = await this.apiFetch(
        `/geo/api/rois/${this.selectedLayer.roiId}/`,
        {
          method: "DELETE",
        },
      );

      if (!response.ok) {
        this.setStatus("Failed to delete ROI.");
        return;
      }

      await this.loadRois();
      this.setStatus("ROI deleted.");
    },

    clearSelection() {
      this.selectedLayer = null;
      this.roiName = "";
      this.selectedRoiText = "No ROI selected.";
      this.resetLayerStyles();
      this.setStatus("Selection cleared.");
    },

    isPreviewVisible(jobId) {
      return this.visiblePreviewJobIds.includes(jobId);
    },

    removePreview(jobId) {
      const layer = this.previewLayers[jobId];

      if (layer) {
        this.map.removeLayer(layer);
      }

      delete this.previewLayers[jobId];
      this.visiblePreviewJobIds = this.visiblePreviewJobIds.filter((id) => id !== jobId);
    },

    showPreview(job) {
      if (!job.preview_image || !job.preview_bounds) {
        this.setStatus(`Job #${job.id} has no map preview yet.`);
        return;
      }

      if (this.isPreviewVisible(job.id)) {
        return;
      }

      const previewLayer = L.imageOverlay(job.preview_image, job.preview_bounds, {
        opacity: 0.75,
        interactive: true,
        alt: `Mosaic preview for job ${job.id}`,
      }).addTo(this.map);

      this.previewLayers[job.id] = previewLayer;
      this.visiblePreviewJobIds = [...this.visiblePreviewJobIds, job.id];
      previewLayer.bringToFront();
      this.drawnItems.bringToFront();
      this.map.fitBounds(job.preview_bounds, {
        padding: [20, 20],
      });
      this.setStatus(`Showing preview for job #${job.id}.`);
    },

    togglePreview(job) {
      if (this.isPreviewVisible(job.id)) {
        this.removePreview(job.id);
        this.setStatus(`Hidden preview for job #${job.id}.`);
        return;
      }

      this.showPreview(job);
    },

    selectedSensors() {
      const sensors = [];

      if (this.jobForm.use_sentinel2) {
        sensors.push("sentinel-2-l2a");
      }

      if (this.jobForm.use_sentinel1) {
        sensors.push("sentinel-1-rtc");
      }

      return sensors;
    },

    async createJob(runImmediately = false) {
      if (!this.selectedLayer || !this.selectedLayer.roiId) {
        this.setStatus("Select and save ROI before creating job.");
        return;
      }

      const sensors = this.selectedSensors();

      if (sensors.length === 0) {
        this.setStatus("Select at least one sensor.");
        return;
      }

      const payload = {
        roi_id: this.selectedLayer.roiId,
        target_date: this.jobForm.target_date,
        time_window_days: Number(this.jobForm.time_window_days),
        selected_sensors: sensors,
        target_crs: this.jobForm.target_crs,
        resolution: Number(this.jobForm.resolution),
        max_cloud_cover: Number(this.jobForm.max_cloud_cover),
      };

      const response = await this.apiFetch("/geo/api/jobs/", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        this.setStatus("Failed to create job.");
        return;
      }

      const job = await response.json();
      this.setStatus(`Job #${job.id} created.`);

      if (runImmediately) {
        await this.runJob(job.id);
      }

      await this.loadJobs();
    },

    async runJob(jobId) {
      const response = await this.apiFetch(`/geo/api/jobs/${jobId}/run/`, {
        method: "POST",
        body: JSON.stringify({}),
      });

      if (!response.ok && response.status !== 409) {
        this.setStatus(`Failed to run job #${jobId}.`);
        return;
      }

      this.setStatus(`Job #${jobId} started.`);
      await this.loadJobs();
    },

    async loadJobs() {
      const response = await fetch("/geo/api/jobs/");

      if (!response.ok) {
        this.setStatus("Failed to load jobs.");
        return;
      }

      const data = await response.json();
      this.jobs = data.results || [];
    },

    fitRois() {
      if (this.drawnItems.getLayers().length > 0) {
        this.map.fitBounds(this.drawnItems.getBounds(), {
          padding: [20, 20],
        });
      }
    },

    jobStatusClass(status) {
      return `status-${status}`;
    },

    formatSensors(sensors) {
      return Array.isArray(sensors) ? sensors.join(", ") : "";
    },
  };
}
