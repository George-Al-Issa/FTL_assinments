import {api, appendRow, writeOptions} from "./common.js";
import {tr, today, eventLabel} from "./language.js";

const byId = id => document.getElementById(id);
const targets = byId("target-form");
const exposure = byId("exposure-form");
const publish = byId("exposure-publish");
const policy = byId("policy-form");
const targetStatus = byId("target-status");
const focusDay = today();
targets.elements.starts.value = focusDay;
exposure.elements.day.value = focusDay;
let catalog, limits = [], screening;

function renderCatalog() {
    for (const select of [targets.elements.region, exposure.elements.region]) {
        const previous = select.value;
        select.replaceChildren(...catalog.regions.map(region => new Option(tr(region.en, region.ar), region.id)));
        if (previous) select.value = previous;
    }
    const select = targets.elements.crop;
    const previous = select.value;
    select.replaceChildren(...Object.entries(catalog.crops).map(([id, crop]) => new Option(tr(crop.en, crop.ar), id)));
    if (previous) select.value = previous;
}

function renderTargets() {
    if (!catalog) return;
    const rows = byId("target-rows");
    rows.replaceChildren();
    for (const item of limits) {
        const actions = document.createElement("div");
        actions.className = "toolbar";
        const edit = document.createElement("button");
        edit.textContent = tr("Edit", "تعديل");
        edit.addEventListener("click", () => {
            for (const name of ["region", "crop", "starts", "ends", "tonnes"]) targets.elements[name].value = item[name];
            targets.elements.tonnes.focus();
        });
        const remove = document.createElement("button");
        remove.textContent = tr("Remove", "إزالة");
        remove.addEventListener("click", async () => {
            if (!window.confirm(tr("Remove this limit?", "إزالة هذا الحد؟"))) return;
            remove.disabled = true;
            const {region, crop, starts, ends, tonnes} = item;
            try {
                await api("/v1/planning/targets", writeOptions({region, crop, starts, ends, tonnes}, "DELETE"));
                await loadTargets();
                targetStatus.textContent = tr("Limit removed.", "تمت إزالة الحد.");
            } catch (error) {
                targetStatus.textContent = error.message;
            } finally {
                remove.disabled = false;
            }
        });
        actions.append(edit, remove);
        const region = catalog.regions.find(region => region.id === item.region);
        const crop = catalog.crops[item.crop];
        const remainder = (Number(item.tonnes) - Number(item.projected)).toFixed(3);
        appendRow(rows, [tr(region.en, region.ar), tr(crop.en, crop.ar),
            `${item.starts} – ${item.ends}`, item.tonnes, item.projected, remainder, actions]);
    }
}
async function loadTargets() {
    limits = await api("/v1/planning/targets");
    renderTargets();
}
targets.addEventListener("submit", async event => {
    event.preventDefault();
    const button = targets.querySelector("button");
    button.disabled = true;
    try {
        await api("/v1/planning/targets", writeOptions(Object.fromEntries(new FormData(targets)), "PUT"));
        await loadTargets();
        targetStatus.textContent = tr("Limit saved.", "تم حفظ الحد.");
    } catch (error) {
        targetStatus.textContent = error.message;
    } finally {
        button.disabled = false;
    }
});

function renderExposure() {
    if (!screening) return;
    const status = byId("exposure-status");
    const list = byId("exposure-events");
    list.replaceChildren();
    status.textContent = (screening.source === "synthetic" ? tr("Demo weather", "طقس تجريبي") : screening.source) +
        tr(` · ${screening.checked} fields checked · ${screening.failed} unavailable`,
            ` · الحقول المفحوصة: ${screening.checked} · تعذّر فحص: ${screening.failed}`) +
        (screening.partial ? tr(" · Partial coverage (20-field limit)", " · تغطية جزئية (حد ٢٠ حقلاً)") : "") +
        (screening.events.length ? "" : tr(" · No events found in completed checks", " · لم تُرصد أحداث في الفحوص المكتملة"));
    for (const item of screening.events) {
        const detail = document.createElement("details");
        detail.className = "panel";
        const summary = document.createElement("summary");
        summary.textContent = `${eventLabel(item.kind)} · ${item.start} – ${item.end} · ${item.hectares.toFixed(2)} ${tr("ha exposed", "هكتار معرّض")}` +
            (item.review ? tr(" · Regional review", " · مراجعة إقليمية") : "");
        detail.append(summary);
        const fields = document.createElement("ul");
        for (const field of item.fields) {
            const li = document.createElement("li");
            li.textContent = `${field.name} · ${field.latitude.toFixed(5)}, ${field.longitude.toFixed(5)} · ${field.area_ha} ${tr("ha", "هكتار")}`;
            fields.append(li);
        }
        detail.append(fields);
        list.append(detail);
    }
}
exposure.addEventListener("submit", async event => {
    event.preventDefault();
    const button = exposure.querySelector("button");
    const status = byId("exposure-status");
    button.disabled = true;
    screening = undefined;
    publish.hidden = true;
    byId("exposure-events").replaceChildren();
    status.textContent = tr("Checking forecast…", "جارٍ فحص التوقعات…");
    try {
        screening = await api("/v1/planning/exposure?" + new URLSearchParams(new FormData(exposure)));
        renderExposure();
        publish.hidden = screening.events.length === 0;
    } catch (error) {
        status.textContent = error.message;
    } finally {
        button.disabled = false;
    }
});
policy.addEventListener("submit", async event => {
    event.preventDefault();
    const button = policy.querySelector("button");
    button.disabled = true;
    try {
        const data = Object.fromEntries([...new FormData(policy)].map(([key, value]) => [key, Number(value)]));
        await api("/v1/planning/policy", writeOptions(data, "PUT"));
        byId("policy-status").textContent = tr("Thresholds saved.", "تم حفظ العتبات.");
    } catch (error) {
        byId("policy-status").textContent = error.message;
    } finally {
        button.disabled = false;
    }
});

async function initialize() {
    try {
        catalog = await api("/v1/planning/admin/catalog");
        renderCatalog();
        await loadTargets();
    } catch (error) {
        targetStatus.textContent = error.message;
    }
    try {
        for (const [key, value] of Object.entries(await api("/v1/planning/policy"))) policy.elements[key].value = value;
    } catch (error) {
        byId("policy-status").textContent = error.message;
    }
}
document.addEventListener("crosafe:language", () => {
    if (catalog) renderCatalog();
    renderTargets();
    renderExposure();
});
initialize();

exposure.addEventListener("change", () => {
    publish.hidden = true;
    screening = undefined;
    byId("exposure-events").replaceChildren();
    byId("exposure-status").textContent = "";
});
publish.addEventListener("click", async () => {
    if (!window.confirm(tr("Refresh forecast and send in-app warnings to affected farmers?",
        "تحديث التوقعات وإرسال تنبيهات للمزارعين المعنيين؟"))) return;
    publish.disabled = true;
    try {
        const params = new URLSearchParams(new FormData(exposure));
        const result = await api("/v1/planning/exposure/publish?" + params, writeOptions());
        byId("exposure-status").textContent = tr(`New notices: ${result.sent} · Unavailable checks: ${result.failed}`,
            `التنبيهات الجديدة: ${result.sent} · تعذّر الفحص: ${result.failed}`);
    } catch (error) {
        byId("exposure-status").textContent = error.message;
    } finally {
        publish.disabled = false;
    }
});
