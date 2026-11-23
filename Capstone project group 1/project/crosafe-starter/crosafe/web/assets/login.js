import {api, writeOptions} from "./common.js";

const form = document.querySelector("#login-form");
form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button");
    button.disabled = true;
    try {
        await api("/v1/session/login", writeOptions(Object.fromEntries(new FormData(form))));
        location.replace("/");
    } catch (error) {
        document.querySelector("#login-status").textContent = error.message;
        button.disabled = false;
    }
});
