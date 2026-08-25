const $ = (id) => document.getElementById(id);

const ui = {
  status: $("status"),
  alert: $("alert"),
  networks: $("networks"),
  rescan: $("rescan"),
  form: $("form"),
  ssid: $("ssid"),
  password: $("password"),
  passwordWrap: $("password-wrap"),
  connect: $("connect"),
};

let selected = "";
let selectedOpen = false;

function signalClass(n) {
  return n >= 45 ? "signal ok" : "signal";
}

function renderNetworks(list) {
  ui.networks.innerHTML = "";
  if (!list.length) {
    const p = document.createElement("p");
    p.className = "empty";
    p.textContent = "No se vieron redes. Escribí el SSID a mano.";
    ui.networks.appendChild(p);
    return;
  }
  for (const net of list) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    if (net.ssid === selected) btn.classList.add("selected");
    btn.innerHTML = `
      <span class="${signalClass(net.signal)}"><i></i><i></i><i></i><i></i></span>
      <span class="ssid"></span>
      <span class="meta"></span>
    `;
    btn.querySelector(".ssid").textContent = net.ssid;
    btn.querySelector(".meta").textContent = net.open ? "Abierta" : net.security;
    btn.addEventListener("click", () => select(net));
    li.appendChild(btn);
    ui.networks.appendChild(li);
  }
}

function select(net) {
  selected = net.ssid;
  selectedOpen = Boolean(net.open);
  ui.ssid.value = net.ssid;
  ui.passwordWrap.classList.toggle("hidden", selectedOpen);
  if (selectedOpen) ui.password.value = "";
  for (const btn of ui.networks.querySelectorAll("button")) {
    btn.classList.toggle(
      "selected",
      btn.querySelector(".ssid")?.textContent === net.ssid
    );
  }
}

function showAlert(text, ok = false) {
  ui.alert.hidden = !text;
  ui.alert.textContent = text;
  ui.alert.classList.toggle("ok", ok);
}

function setBusy(busy) {
  ui.connect.disabled = busy;
  ui.rescan.disabled = busy;
  ui.connect.textContent = busy ? "Conectando…" : "Conectar";
}

async function getJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("HTTP " + res.status);
  return res.json();
}

async function loadNetworks(rescan = false) {
  const data = await getJson("/api/networks" + (rescan ? "?rescan=1" : ""));
  renderNetworks(data.networks || []);
}

function statusLabel(state) {
  if (state === "online") return "Conectada a internet.";
  if (state === "connecting") return "Conectando a la red…";
  if (state === "ap") return "Modo setup. Elegí una red.";
  if (state === "offline") return "Sin internet. Levantando el AP…";
  return state;
}

async function pollStatus() {
  try {
    const data = await getJson("/api/status");
    ui.status.textContent = statusLabel(data.state);
    if (data.error && data.state !== "online") showAlert(data.error);
    if (data.state === "connecting") {
      setBusy(true);
    } else if (data.state === "online") {
      setBusy(true);
      showAlert("Listo. Ya podés volver a tu WiFi habitual.", true);
      ui.connect.textContent = "Conectada";
    } else {
      setBusy(false);
    }
  } catch {
    ui.status.textContent = "El portal se está reiniciando…";
  }
}

ui.ssid.addEventListener("input", () => {
  selectedOpen = false;
  ui.passwordWrap.classList.remove("hidden");
});

ui.rescan.addEventListener("click", async () => {
  ui.rescan.disabled = true;
  try {
    await loadNetworks(true);
    await new Promise((r) => setTimeout(r, 2500));
    await loadNetworks(false);
  } catch {
    showAlert("No se pudo actualizar la lista.");
  } finally {
    ui.rescan.disabled = false;
  }
});

ui.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const ssid = ui.ssid.value.trim();
  if (!ssid) return;
  setBusy(true);
  showAlert("");
  try {
    const res = await fetch("/api/connect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ssid,
        password: ui.passwordWrap.classList.contains("hidden")
          ? ""
          : ui.password.value,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "No se pudo conectar");
    ui.status.textContent = statusLabel("connecting");
  } catch (err) {
    setBusy(false);
    showAlert(err.message || "No se pudo conectar");
  }
});

async function init() {
  await Promise.all([loadNetworks(false), pollStatus()]);
  setInterval(pollStatus, 2000);
}

init();
