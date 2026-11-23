import {api, writeOptions} from "./common.js";

const sections = [...document.querySelectorAll("[data-view]")];
const noticeView = document.querySelector('[data-view="notifications"]');
const panel = document.createElement("section");
panel.className = "panel";
panel.innerHTML = `
<h2>Inbox</h2>
<div class="toolbar"><button id="notice-refresh">Refresh</button><button id="notice-read">Mark all read</button></div>
<p id="notice-status" role="status"></p><ul id="notices" class="notices"></ul>
<button id="notice-more" hidden>Load older notifications</button>`;
noticeView.append(panel);
const list = panel.querySelector("#notices");
const status = panel.querySelector("#notice-status");
const more = panel.querySelector("#notice-more");
const readAll = panel.querySelector("#notice-read");
let inbox = [];
let loading = false;

function navigate() {
    const requested = location.hash.slice(1);
    const active = sections.find(section => section.dataset.view === requested) ?? sections[0];
    for (const section of sections) section.hidden = section !== active;
    for (const item of document.querySelectorAll(".navigation a")) {
        if (item.hash === "#" + active.dataset.view) item.setAttribute("aria-current", "page");
        else item.removeAttribute("aria-current");
    }
    document.dispatchEvent(new CustomEvent("crosafe:view", {detail: active.dataset.view}));
}
window.addEventListener("hashchange", navigate);
navigate();

api("/v1/session/me").then(account => {
    document.querySelector("#session-user").textContent = account.username;
});
document.querySelector("#logout").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
        await api("/v1/session/logout", writeOptions());
        location.replace("/login");
    } catch (error) {
        button.textContent = "Retry sign out";
        button.disabled = false;
    }
});

function render() {
    readAll.disabled = inbox.length === 0;
    list.replaceChildren();
    for (const item of inbox) {
        const li = document.createElement("li");
        const title = document.createElement("strong");
        const message = document.createElement("p");
        const time = document.createElement("small");
        title.textContent = item.title;
        message.textContent = item.message;
        time.textContent = new Date(item.created_at).toLocaleString();
        li.append(title, message, time);
        if (!item.read) {
            const button = document.createElement("button");
            button.textContent = "Mark read";
            button.addEventListener("click", async () => {
                try {
                    await api(`/v1/notifications/read?notification_id=${item.id}`, writeOptions());
                    item.read = true;
                    render();
                    await updateBadge();
                } catch (error) {
                    status.textContent = error.message;
                }
            });
            li.append(button);
        }
        list.append(li);
    }
}

async function load(older = false) {
    if (loading) return;
    loading = true;
    try {
        const query = older ? `?before=${inbox.at(-1).id}` : "";
        const page = await api("/v1/notifications" + query);
        inbox = older ? [...inbox, ...page] : page;
        more.hidden = page.length < 50;
        status.textContent = inbox.length ? "" : "No notifications yet.";
        render();
        await updateBadge();
    } catch (error) {
        status.textContent = error.message;
    } finally {
        loading = false;
    }
}

readAll.addEventListener("click", async () => {
    try {
        await api(`/v1/notifications/read?through=${inbox[0].id}`, writeOptions());
        await load();
    } catch (error) {
        status.textContent = error.message;
    }
});
panel.querySelector("#notice-refresh").addEventListener("click", () => load());
more.addEventListener("click", () => load(true));
document.addEventListener("crosafe:view", event => {
    if (event.detail === "notifications") load();
});
load();

async function updateBadge() {
    try {
        const {unread} = await api("/v1/notifications/unread");
        document.querySelector("#notice-count").textContent = unread ? `(${unread})` : "";
    } catch {
        // The inbox shows a full error message when explicitly opened.
    }
}
window.setInterval(() => {
    if (!document.hidden) updateBadge();
}, 45_000);
