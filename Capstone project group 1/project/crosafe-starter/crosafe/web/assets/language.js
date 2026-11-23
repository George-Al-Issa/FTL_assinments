const english = new Map();
const labels = {
    heat: ["Heat", "حرارة مرتفعة"], frost: ["Frost", "صقيع"],
    heavy_rain: ["Heavy rain", "أمطار غزيرة"], dry_spell: ["Dry spell", "فترة جافة"],
};

export let arabic = localStorage.getItem("crosafe-language") !== "en";
export const tr = (en, ar) => arabic ? ar : en;
export const eventLabel = kind => tr(...labels[kind]);
export const today = () => new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Damascus", year: "numeric", month: "2-digit", day: "2-digit",
}).format(new Date());

const header = document.querySelector("header");
const switcher = document.createElement("button");
switcher.type = "button";
header.insertBefore(switcher, document.querySelector("#logout"));

function render() {
    document.documentElement.lang = arabic ? "ar" : "en";
    document.documentElement.dir = arabic ? "rtl" : "ltr";
    for (const node of document.querySelectorAll("[data-ar]")) {
        if (!english.has(node)) english.set(node, node.textContent);
        node.textContent = arabic ? node.dataset.ar : english.get(node);
    }
    switcher.textContent = tr("العربية", "English");
    document.querySelector("#logout").textContent = tr("Sign out", "تسجيل الخروج");
}
switcher.addEventListener("click", () => {
    arabic = !arabic;
    localStorage.setItem("crosafe-language", arabic ? "ar" : "en");
    render();
    document.dispatchEvent(new Event("crosafe:language"));
});
render();
