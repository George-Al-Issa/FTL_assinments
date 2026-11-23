import {api, appendRow, writeOptions} from "./common.js";

const byId = id => document.getElementById(id);
const number = new Intl.NumberFormat(undefined, {maximumFractionDigits: 2});
const analysis = byId("analysis-filter");
const provider = byId("provider-form");
const notice = byId("notice-form");
const catalog = byId("catalog-form");
const sample = byId("sample-form");
const prefix = byId("catalog-prefix");
const next = byId("catalog-next");
const root = "DATA/GAEZ-V5/";
let pageToken = "";
let openedPrefix = root;
let activeCatalogRequest = 0;

async function loadAnalysis() {
    const status = byId("analysis-status");
    const params = new URLSearchParams();
    for (const [key, value] of new FormData(analysis)) if (value) params.set(key, value);
    status.textContent = "Loading analysis…";
    const submit = analysis.querySelector("button");
    submit.disabled = true;
    byId("analysis-reset").disabled = true;
    try {
        const {totals, crops, months} = await api("/v1/admin/analysis?" + params);
        const metrics = byId("metrics");
        metrics.replaceChildren();
        for (const [key, label] of Object.entries({
            plantings: "Planting records", customers: "Reporting customers",
            crops: "Crops reported", area_ha: "Reported hectares",
        })) {
            const card = document.createElement("p");
            card.className = "metric";
            const value = document.createElement("strong");
            value.textContent = number.format(totals[key]);
            card.append(value, label);
            metrics.append(card);
        }
        const cropRows = byId("analysis-crops");
        cropRows.replaceChildren();
        for (const crop of crops) {
            const label = document.createElement("div");
            const meter = document.createElement("progress");
            meter.max = Math.max(crops[0].area_ha, 1);
            meter.value = crop.area_ha;
            meter.setAttribute("aria-label", `${crop.crop} area compared with the leading crop`);
            label.append(crop.crop, meter);
            appendRow(cropRows, [label, crop.plantings, number.format(crop.area_ha)]);
        }
        const monthRows = byId("analysis-months");
        monthRows.replaceChildren();
        for (const month of months) {
            appendRow(monthRows, [month.month.slice(0, 7), month.plantings, number.format(month.area_ha)]);
        }
        status.textContent = totals.plantings ? "Based on customer-reported records." : "No records match these dates.";
    } catch (error) {
        status.textContent = error.message;
    } finally {
        submit.disabled = false;
        byId("analysis-reset").disabled = false;
    }
}

analysis.addEventListener("submit", event => {
    event.preventDefault();
    loadAnalysis();
});
byId("analysis-reset").addEventListener("click", () => {
    analysis.reset();
    loadAnalysis();
});

async function loadProviders() {
    try {
        const data = await api("/v1/admin/providers");
        for (const [key, value] of Object.entries(data.settings)) {
            const input = provider.elements[key];
            if (input.type === "checkbox") input.checked = value;
            else input.value = value;
        }
        byId("provider-key").textContent = data.open_meteo_key_configured
            ? "Customer API key configured on the server." : "Public endpoint available. No customer API key configured.";
        byId("provider-status").textContent = "";
    } catch (error) {
        byId("provider-status").textContent = error.message;
    }
}

provider.addEventListener("submit", async event => {
    event.preventDefault();
    const status = byId("provider-status");
    const fields = provider.elements;
    try {
        await api("/v1/admin/providers", writeOptions({
            weather_mode: fields.weather_mode.value,
            forecast_days: Number(fields.forecast_days.value),
            gaez_online: fields.gaez_online.checked,
            weather_paid: fields.weather_paid.checked,
            world_bank_online: fields.world_bank_online.checked,
            world_bank_indicator: fields.world_bank_indicator.value,
        }, "PUT"));
        status.textContent = "Configuration saved.";
    } catch (error) {
        status.textContent = error.message;
    }
});

for (const button of document.querySelectorAll("[data-check]")) {
    button.addEventListener("click", async () => {
        button.disabled = true;
        const status = byId("provider-status");
        status.textContent = "Checking saved configuration…";
        try {
            const result = await api("/v1/admin/providers/check?provider=" + button.dataset.check, writeOptions());
            status.textContent = result.message;
        } catch (error) {
            status.textContent = error.message;
        } finally {
            button.disabled = false;
        }
    });
}

async function loadCatalog(folder = root, token = "") {
    const id = ++activeCatalogRequest;
    const status = byId("catalog-status");
    status.textContent = "Loading official catalog…";
    next.disabled = true;
    try {
        const page = await api("/v1/admin/gaez/catalog?" + new URLSearchParams({prefix: folder, token}));
        if (id !== activeCatalogRequest) return;
        prefix.value = folder;
        openedPrefix = folder;
        pageToken = page.next;
        next.hidden = !pageToken;
        byId("catalog-up").disabled = folder === root;
        const folders = byId("catalog-folders");
        const objects = byId("catalog-objects");
        folders.replaceChildren();
        objects.replaceChildren();
        for (const entry of page.prefixes) {
            const button = document.createElement("button");
            button.textContent = entry.split("/").at(-2);
            button.addEventListener("click", () => loadCatalog(entry));
            folders.append(button);
        }
        for (const item of page.objects) {
            const actions = document.createElement("div");
            const link = document.createElement("a");
            link.href = item.url;
            link.textContent = "Source file";
            link.target = "_blank";
            link.rel = "noreferrer";
            actions.append(link);
            if (/\.tiff?$/i.test(item.name)) {
                const button = document.createElement("button");
                button.textContent = "Inspect";
                button.addEventListener("click", () => {
                    const input = byId("catalog-object");
                    input.value = item.name;
                    input.focus();
                });
                actions.append(" ", button);
            }
            appendRow(objects, [item.name.split("/").at(-1), number.format(Number(item.size)) + " bytes", actions]);
        }
        status.textContent = `${page.prefixes.length} folders and ${page.objects.length} objects on this page.`;
    } catch (error) {
        if (id === activeCatalogRequest) status.textContent = error.message;
    } finally {
        if (id === activeCatalogRequest) next.disabled = false;
    }
}

catalog.addEventListener("submit", event => {
    event.preventDefault();
    loadCatalog(prefix.value.trim());
});
byId("catalog-up").addEventListener("click", () => {
    const parent = openedPrefix.replace(/\/$/, "").split("/").slice(0, -1).join("/") + "/";
    loadCatalog(parent.length >= root.length ? parent : root);
});
next.addEventListener("click", () => loadCatalog(openedPrefix, pageToken));

sample.addEventListener("submit", async event => {
    event.preventDefault();
    const status = byId("catalog-sample");
    const button = sample.querySelector("button");
    button.disabled = true;
    status.textContent = "Reading official raster…";
    try {
        const result = await api("/v1/admin/gaez/remote-sample?" + new URLSearchParams(new FormData(sample)));
        status.textContent = result.value === null ? "No data at this coordinate."
            : `Source value ${result.value} ${result.unit ?? ""} · ${result.crs} · pixel size ${result.pixel_size.join(" × ")} in CRS units`;
    } catch (error) {
        status.textContent = error.message;
    } finally {
        button.disabled = false;
    }
});

document.addEventListener("crosafe:location", event => {
    sample.elements.latitude.value = event.detail.latitude;
    sample.elements.longitude.value = event.detail.longitude;
});
notice.addEventListener("submit", async event => {
    event.preventDefault();
    const status = byId("send-status");
    const button = notice.querySelector("button");
    button.disabled = true;
    const payload = Object.fromEntries(new FormData(notice));
    payload.recipient ||= null;
    try {
        await api("/v1/admin/notifications", writeOptions(payload));
        notice.reset();
        status.textContent = "In-app notification sent.";
    } catch (error) {
        status.textContent = error.message;
    } finally {
        button.disabled = false;
    }
});

async function loadCustomers() {
    try {
        const names = await api("/v1/admin/customers");
        const select = byId("notice-recipient");
        select.replaceChildren(new Option("All customers", ""));
        for (const name of names) select.add(new Option(name, name));
    } catch (error) {
        byId("send-status").textContent = error.message;
    }
}

function loadView(view) {
    if (view === "analysis") loadAnalysis();
    if (view === "providers") loadProviders();
    if (view === "catalog") loadCatalog(openedPrefix);
    if (view === "notifications") loadCustomers();
}
document.addEventListener("crosafe:view", event => loadView(event.detail));
loadView(document.querySelector("[data-view]:not([hidden])")?.dataset.view);

byId("national-load").addEventListener("click", async event => {
    const button = event.currentTarget;
    const status = byId("national-status");
    const rows = byId("national-rows");
    button.disabled = true;
    rows.replaceChildren();
    status.textContent = "Loading Syria-level indicator…";
    try {
        const context = await api("/v1/admin/national-context");
        status.textContent = context.observations.length ? context.label : "No published values returned.";
        for (const row of context.observations) appendRow(rows, [row.year, number.format(row.value)]);
    } catch (error) {
        status.textContent = error.message;
    } finally {
        button.disabled = false;
    }
});
