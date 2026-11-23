export async function api(path, options) {
    const response = await fetch(path, {cache: "no-store", ...options});
    if (!response.ok) {
        if (response.status === 401 && location.pathname !== "/login") location.replace("/login");
        const body = await response.json().catch(() => ({}));
        throw new Error(typeof body.detail === "string" ? body.detail : `Request failed (${response.status})`);
    }
    return response.json();
}

export function appendRow(table, values) {
    const row = table.insertRow();
    for (const value of values) {
        const cell = row.insertCell();
        if (value instanceof HTMLElement) cell.append(value);
        else cell.textContent = value;
    }
}

export function writeOptions(payload = {}, method = "POST") {
    return {method, headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)};
}

export function showStatus(node, message) {
    node.textContent = message;
}
