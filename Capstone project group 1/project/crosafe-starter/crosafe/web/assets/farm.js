import {api, appendRow, writeOptions} from "./common.js";
import {tr, eventLabel, today} from "./language.js";

const byId = id => document.getElementById(id);
const fieldForm = byId("farm-field");
const report = byId("farm-report");
const options = byId("crop-options");
const status = byId("report-status");
const weatherStatus = byId("weather-status");
let catalog, savedFields = [], latest, pendingField, pendingPlanting;
let reportVersion = 0;
report.elements.day.value = today();

const map = window.L ? L.map("farm-map").setView([35, 38.25], 6) : null;
if (map) {
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    const pin = L.marker([35, 38.25]);
    map.on("click", event => {
        pin.setLatLng(event.latlng).addTo(map);
        fieldForm.elements.latitude.value = event.latlng.lat.toFixed(6);
        fieldForm.elements.longitude.value = event.latlng.lng.toFixed(6);
    });
    document.addEventListener("crosafe:view", event => {
        if (event.detail === "fields") requestAnimationFrame(() => map.invalidateSize());
    });
}

function renderFields(preferred = report.elements.field.value) {
    const select = report.elements.field;
    select.replaceChildren(new Option(tr("Select a field", "اختر حقلاً"), ""));
    for (const field of savedFields) {
        const region = catalog.regions.find(item => item.id === field.region);
        select.add(new Option(field.name + " · " + tr(region.en, region.ar), field.id));
    }
    select.value = savedFields.some(field => field.id === preferred) ? preferred : "";
}

async function initialize() {
    try {
        [catalog, savedFields] = await Promise.all([
            api("/v1/planning/catalog"), api("/v1/planning/fields"),
        ]);
        renderFields();
        if (savedFields.length === 1) report.elements.field.value = savedFields[0].id;
    } catch (error) {
        status.textContent = error.message;
    }
}

fieldForm.addEventListener("submit", async event => {
    event.preventDefault();
    const button = fieldForm.querySelector("button");
    button.disabled = true;
    const data = Object.fromEntries(new FormData(fieldForm));
    for (const key of ["longitude", "latitude", "area_ha"]) data[key] = Number(data[key]);
    const fingerprint = JSON.stringify(data);
    if (pendingField?.fingerprint !== fingerprint) pendingField = {fingerprint, id: crypto.randomUUID()};
    try {
        const saved = await api("/v1/planning/fields", writeOptions({...data, id: pendingField.id}));
        pendingField = undefined;
        if (!savedFields.some(field => field.id === saved.id)) savedFields.push(saved);
        if (!catalog) catalog = await api("/v1/planning/catalog");
        renderFields(saved.id);
        invalidate();
        fieldForm.reset();
        byId("farm-status").textContent = tr("Field saved.", "تم حفظ الحقل.");
    } catch (error) {
        byId("farm-status").textContent = error.message;
    } finally {
        button.disabled = false;
    }
});

function cropLabel(code) {
    const crop = catalog.crops[code];
    return crop ? tr(crop.en, crop.ar) : code;
}

function paragraph(parent, value) {
    const p = document.createElement("p");
    p.textContent = value;
    parent.append(p);
}

function renderReport() {
    if (!latest) return;
    options.replaceChildren();
    const {data, field, day} = latest;
    status.textContent = tr("Demo harvest estimates · ", "تقديرات تجريبية للحصاد · ") +
        (data.options.length ? `${data.options.length} ${tr("available", "متاحة")}`
            : tr("No eligible crops", "لا توجد محاصيل متاحة")) +
        (data.blocked.length ? " · " + tr("Blocked by regional limit: ", "محجوبة بسبب الحد الإقليمي: ") +
            data.blocked.map(cropLabel).join("، ") : "");
    status.textContent += data.soil
        ? tr(` · GAEZ soil source value: ${data.soil.value}`, ` · قيمة التربة من GAEZ: ${data.soil.value}`)
        : tr(" · Soil layer pending", " · طبقة التربة قيد الإعداد");
    for (const item of data.options) {
        const card = document.createElement("article");
        card.className = "panel";
        const title = document.createElement("h3");
        title.textContent = cropLabel(item.crop);
        card.append(title);
        paragraph(card, tr(`Estimated harvest: ${item.tonnes} tonnes (demo)`, `الحصاد المقدّر: ${item.tonnes} طن (تجريبي)`));
        paragraph(card, item.suitability
            ? tr(`GAEZ context: source value ${item.suitability.value}`, `قيمة الملاءمة الأصلية من GAEZ: ${item.suitability.value}`)
            : tr("No local GAEZ layer configured for this crop.", "لا تتوفر طبقة GAEZ محلية لهذا المحصول."));
        paragraph(card, item.check_days
            ? tr(`Check soil moisture about every ${item.check_days} days. Use the moisture reading and local advice to decide when to irrigate.`,
                `افحص رطوبة التربة تقريباً كل ${item.check_days} أيام. حدّد موعد الري وفق الرطوبة وتوصيات الإرشاد المحلي.`)
            : tr("Rain-fed field. Monitor soil moisture and rainfall.", "حقل بعلي. راقب رطوبة التربة والأمطار."));
        paragraph(card, tr(...item.info));
        paragraph(card, tr("Why this crop? It passed the regional limit check and is in the demo crop set.",
            "لماذا هذا المحصول؟ اجتاز فحص الحد الإقليمي وهو ضمن قائمة المحاصيل التجريبية."));
        paragraph(card, tr("Base fertilizer decisions on a soil test and local extension advice.",
            "استند إلى تحليل التربة وتوصيات الإرشاد الزراعي لاختيار التسميد."));
        const confirm = document.createElement("button");
        confirm.textContent = tr("Confirm planting", "أكّد الزراعة");
        confirm.addEventListener("click", async () => {
            if (!window.confirm(tr(`Confirm ${title.textContent} for ${day}?`, `تأكيد زراعة ${title.textContent} بتاريخ ${day}؟`))) return;
            const payload = {field_id: field, crop: item.crop, planted_on: day};
            const fingerprint = JSON.stringify(payload);
            if (pendingPlanting?.fingerprint !== fingerprint) pendingPlanting = {fingerprint, id: crypto.randomUUID()};
            for (const button of options.querySelectorAll("button")) button.disabled = true;
            try {
                await api("/v1/planning/confirm", writeOptions({...payload, id: pendingPlanting.id}));
                pendingPlanting = undefined;
                invalidate();
                status.textContent = tr("Planting confirmed. View it under Confirmed plantings.", "تم تأكيد الزراعة. راجع قائمة المحاصيل المؤكدة.");
                loadPlantings();
            } catch (error) {
                status.textContent = error.message;
                for (const button of options.querySelectorAll("button")) button.disabled = false;
            }
        });
        card.append(confirm);
        options.append(card);
    }
}

function invalidate() {
    reportVersion++;
    latest = undefined;
    options.replaceChildren();
    byId("weather-events").replaceChildren();
    status.textContent = "";
    weatherStatus.textContent = "";
}
report.addEventListener("change", invalidate);
report.addEventListener("submit", async event => {
    event.preventDefault();
    invalidate();
    const version = reportVersion;
    const {field, day} = Object.fromEntries(new FormData(report));
    status.textContent = tr("Loading recommendations…", "جارٍ تحميل التوصيات…");
    try {
        const data = await api(`/v1/planning/fields/${field}/recommendations?day=${day}`);
        if (version !== reportVersion) return;
        latest = {data, field, day};
        renderReport();
    } catch (error) {
        if (version === reportVersion) status.textContent = error.message;
    }
});

byId("field-weather").addEventListener("click", async () => {
    const field = report.elements.field.value;
    if (!field) {
        weatherStatus.textContent = tr("Select a field first.", "اختر حقلاً أولاً.");
        return;
    }
    const version = reportVersion;
    weatherStatus.textContent = tr("Checking forecast…", "جارٍ فحص التوقعات…");
    byId("weather-events").replaceChildren();
    try {
        const result = await api(`/v1/planning/fields/${field}/weather`);
        if (version !== reportVersion) return;
        weatherStatus.textContent = (result.source === "synthetic" ? tr("Demo weather", "طقس تجريبي") : result.source) +
            (result.events.length ? "" : tr(" · No alert thresholds met", " · لا تنبيهات حسب العتبات الحالية"));
        for (const item of result.events) {
            const row = document.createElement("li");
            row.textContent = `${item.start} – ${item.end} · ${eventLabel(item.kind)} · ${tr(...item.guidance)}`;
            byId("weather-events").append(row);
        }
    } catch (error) {
        if (version === reportVersion) weatherStatus.textContent = error.message;
    }
});

let offset = 0;
async function loadPlantings(more = false) {
    const button = byId("more");
    button.disabled = true;
    try {
        const page = await api(`/v1/customer/plantings?limit=100&offset=${more ? offset : 0}`);
        if (!more) {
            byId("rows").replaceChildren();
            offset = 0;
        }
        for (const item of page) appendRow(byId("rows"), [
            cropLabel(item.crop), item.planted_on, item.area_ha, `${item.latitude}, ${item.longitude}`,
        ]);
        offset += page.length;
        button.hidden = page.length < 100;
        byId("records-status").textContent = offset ? "" : tr("No confirmed plantings yet.", "لا توجد زراعات مؤكدة بعد.");
    } catch (error) {
        byId("records-status").textContent = error.message;
    } finally {
        button.disabled = false;
    }
}
byId("more").addEventListener("click", () => loadPlantings(true));
document.addEventListener("crosafe:view", event => {
    if (event.detail === "plantings" && catalog) loadPlantings();
});
document.addEventListener("crosafe:language", () => {
    if (catalog) renderFields();
    renderReport();
    if (location.hash === "#plantings" && catalog) loadPlantings();
});
initialize().then(() => {
    if (location.hash === "#plantings" && catalog) loadPlantings();
});
