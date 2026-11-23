import {api, appendRow} from "./common.js";

const crop = document.querySelector("#crop");
const layer = document.querySelector("#layer");
const status = document.querySelector("#status");
const details = document.querySelector("#details");
const sample = document.querySelector("#sample");
const rows = document.querySelector("#rows");
const more = document.querySelector("#more");
const pageSize = 100;
const records = new Map();
const map = window.L ? L.map("map").setView([35, 38.25], 6) : null;
const points = map ? L.geoJSON(null, {
    pointToLayer: (_, position) => L.circleMarker(position, {
        radius: 7, color: "#fff", weight: 2, fillColor: "#176646", fillOpacity: 0.95,
    }),
    onEachFeature: (feature, marker) => marker.on("click", () => selectRecord(feature)),
}).addTo(map) : null;

if (map) {
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
}
let selected;
let sampleRequest = 0;
let offset = 0;

async function sampleLayer() {
    const request = ++sampleRequest;
    if (!layer.value || !selected) {
        sample.textContent = layer.options.length === 1
            ? "No raster layers configured."
            : "Choose a layer and select a planting to inspect the model value.";
        return;
    }
    const [longitude, latitude] = selected.geometry.coordinates;
    sample.textContent = "Loading layer value…";
    try {
        const result = await api("/v1/admin/gaez/sample?" + new URLSearchParams({
            layer_id: layer.value, longitude, latitude,
        }));
        if (request !== sampleRequest) return;
        const value = result.value === null ? "No raster value at this point" : `${result.value} ${result.layer.units}`;
        sample.textContent = `${result.layer.title} · ${value} · ${result.layer.scenario}. ${result.layer.interpretation}`;
    } catch (error) {
        if (request === sampleRequest) sample.textContent = error.message;
    }
}

function selectRecord(feature, pan = false) {
    selected = feature;
    const [longitude, latitude] = feature.geometry.coordinates;
    const record = feature.properties;
    details.textContent = `${record.crop} · ${record.customer} · ${record.area_ha} ha · ${record.planted_on} · ${latitude}, ${longitude}`;
    if (pan && map) map.panTo([latitude, longitude]);
    document.dispatchEvent(new CustomEvent("crosafe:location", {detail: {latitude, longitude}}));
    sampleLayer();
}

function render() {
    rows.replaceChildren();
    points?.clearLayers();
    const visible = [...records.values()].filter(feature =>
        !crop.value || feature.properties.crop.toLowerCase() === crop.value);
    for (const feature of visible) {
        const record = feature.properties;
        const [longitude, latitude] = feature.geometry.coordinates;
        const button = document.createElement("button");
        button.textContent = `${latitude}, ${longitude}`;
        button.addEventListener("click", () => selectRecord(feature, true));
        appendRow(rows, [record.crop, record.customer, record.planted_on, record.area_ha, button]);
        points?.addData(feature);
    }
    if (points?.getBounds().isValid()) map.fitBounds(points.getBounds(), {padding: [25, 25], maxZoom: 11});
    if (selected && !visible.includes(selected)) {
        selected = undefined;
        details.textContent = "Select a record on the map or in the table.";
        sampleLayer();
    }
    status.textContent = `${visible.length} shown · ${records.size} loaded${map ? "" : " · Map library unavailable"}`;
}

async function loadRecords() {
    more.disabled = true;
    try {
        const page = await api(`/v1/admin/plantings.geojson?limit=${pageSize}&offset=${offset}`);
        for (const feature of page.features) {
            records.set(feature.id, feature);
            const name = feature.properties.crop;
            if (![...crop.options].some(option => option.value === name.toLowerCase())) {
                crop.add(new Option(name, name.toLowerCase()));
            }
        }
        offset += page.features.length;
        more.hidden = page.features.length < pageSize;
        render();
    } catch (error) {
        status.textContent = error.message;
    } finally {
        more.disabled = false;
    }
}

crop.addEventListener("change", render);
layer.addEventListener("change", sampleLayer);
more.addEventListener("click", loadRecords);
loadRecords();
api("/v1/admin/gaez/layers").then(layers => {
    for (const item of layers) layer.add(new Option(item.title, item.id));
    sampleLayer();
}).catch(error => { sample.textContent = error.message; });

document.addEventListener("crosafe:view", event => {
    if (event.detail === "plantings" && map) {
        requestAnimationFrame(() => {
            map.invalidateSize();
            if (points.getBounds().isValid()) {
                map.fitBounds(points.getBounds(), {padding: [25, 25], maxZoom: 11});
            }
        });
    }
});
