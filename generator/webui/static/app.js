const state = {
    cards: [],
    job: null,
    pollTimer: null,
};

const terminalJobStatuses = new Set(["completed", "completed_with_errors", "cancelled", "error"]);
const statusLabels = {
    queued: "Ожидает",
    generating: "Генерация",
    importing: "Импорт",
    generated: "Готова",
    imported: "В Anki",
    skipped: "Пропущена",
    error: "Ошибка",
};

const $ = (selector) => document.querySelector(selector);

async function api(path, options = {}) {
    const response = await fetch(path, {
        headers: {"Content-Type": "application/json", ...(options.headers || {})},
        ...options,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload.error || `Ошибка HTTP ${response.status}`);
    }
    return payload;
}

function showError(message) {
    const alert = $("#global-error");
    alert.textContent = message;
    alert.hidden = !message;
    if (message) alert.scrollIntoView({behavior: "smooth", block: "center"});
}

function setHealth(element, result) {
    element.textContent = result.message;
    element.className = `status-pill ${result.ok ? "status-ok" : "status-warning"}`;
}

async function loadHealth() {
    try {
        const health = await api("/api/health");
        setHealth($("#anki-status"), health.anki);
        setHealth($("#dependency-status"), health.dependencies);
        $("#processing-directory").value ||= health.defaults.processing_directory;
        $("#anki-media-directory").value ||= health.defaults.anki_media_directory;
    } catch (error) {
        setHealth($("#anki-status"), {ok: false, message: "Сервер недоступен"});
        showError(error.message);
    }
}

function bufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    const chunkSize = 0x8000;
    for (let offset = 0; offset < bytes.length; offset += chunkSize) {
        binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
    }
    return btoa(binary);
}

async function parseInput() {
    showError("");
    const button = $("#parse-button");
    button.disabled = true;
    button.textContent = "Читаю данные…";
    try {
        const file = $("#file-input").files[0];
        let payload;
        if (file) {
            payload = {
                filename: file.name,
                file_content: bufferToBase64(await file.arrayBuffer()),
            };
        } else {
            payload = {content: $("#words-input").value};
        }
        const result = await api("/api/parse", {method: "POST", body: JSON.stringify(payload)});
        state.cards = result.cards.map((card, index) => ({...card, id: String(index + 1), status: "queued", message: "Ожидает запуска"}));
        state.job = null;
        localStorage.removeItem("anki-generator-job");
        renderQueue();
        $("#queue-section").hidden = false;
        $("#queue-section").scrollIntoView({behavior: "smooth", block: "start"});
    } catch (error) {
        showError(error.message);
    } finally {
        button.disabled = false;
        button.textContent = "Подготовить карточки";
    }
}

function settingsPayload() {
    return {
        language: $("#language").value,
        level: $("#level").value,
        deck_name: $("#deck-name").value.trim(),
        card_model: $("#card-model").value.trim(),
        image_generation_mode: $("#image-mode").value,
        duplicate_policy: $("#duplicate-policy").value,
        openai_api_key: $("#openai-key").value.trim(),
        replicate_api_key: $("#replicate-key").value.trim(),
        replicate_model_url: $("#replicate-model").value.trim(),
        processing_directory: $("#processing-directory").value.trim(),
        anki_media_directory: $("#anki-media-directory").value.trim(),
        create_deck: $("#create-deck").checked,
        import_after_generation: $("#import-after").checked,
    };
}

async function startJob() {
    showError("");
    const startButton = $("#start-button");
    startButton.disabled = true;
    try {
        const created = await api("/api/jobs", {
            method: "POST",
            body: JSON.stringify({cards: state.cards, settings: settingsPayload()}),
        });
        state.job = created;
        localStorage.setItem("anki-generator-job", created.id);
        renderJob();
        state.job = await api(`/api/jobs/${created.id}/start`, {method: "POST", body: "{}"});
        renderJob();
        startPolling();
    } catch (error) {
        startButton.disabled = false;
        showError(error.message);
    }
}

async function cancelJob() {
    if (!state.job) return;
    try {
        state.job = await api(`/api/jobs/${state.job.id}/cancel`, {method: "POST", body: "{}"});
        renderJob();
    } catch (error) {
        showError(error.message);
    }
}

function startPolling() {
    clearInterval(state.pollTimer);
    state.pollTimer = setInterval(refreshJob, 1000);
    refreshJob();
}

async function refreshJob() {
    if (!state.job) return;
    try {
        state.job = await api(`/api/jobs/${state.job.id}`);
        state.cards = state.job.cards;
        renderJob();
        if (terminalJobStatuses.has(state.job.status)) {
            clearInterval(state.pollTimer);
            state.pollTimer = null;
        }
    } catch (error) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
        localStorage.removeItem("anki-generator-job");
        showError(error.message);
    }
}

function renderQueue() {
    $("#card-count").textContent = state.cards.length;
    const body = $("#cards-body");
    body.replaceChildren();
    for (const card of state.cards) {
        const row = document.createElement("tr");

        const wordCell = document.createElement("td");
        const word = document.createElement("strong");
        word.textContent = card.word;
        wordCell.append(word);

        const contextCell = document.createElement("td");
        contextCell.textContent = card.context || "—";
        contextCell.className = card.context ? "" : "muted";

        const statusCell = document.createElement("td");
        const badge = document.createElement("span");
        badge.className = `card-status card-status-${card.status}`;
        badge.textContent = statusLabels[card.status] || card.status;
        const message = document.createElement("small");
        message.className = "status-message";
        message.textContent = card.message || "";
        statusCell.append(badge, message);

        const actionCell = document.createElement("td");
        actionCell.className = "action-cell";
        const preview = document.createElement("button");
        preview.type = "button";
        preview.className = "button button-quiet button-small";
        preview.textContent = "Открыть";
        preview.disabled = !card.card_text;
        preview.addEventListener("click", () => openPreview(card));
        actionCell.append(preview);

        row.append(wordCell, contextCell, statusCell, actionCell);
        body.append(row);
    }
}

function renderJob() {
    if (!state.job) {
        $("#progress-area").hidden = true;
        $("#cancel-button").hidden = true;
        $("#start-button").hidden = false;
        $("#start-button").disabled = false;
        renderQueue();
        return;
    }

    state.cards = state.job.cards;
    renderQueue();
    $("#progress-area").hidden = false;
    $("#job-message").textContent = state.job.message;
    $("#progress-label").textContent = `${state.job.progress.finished} из ${state.job.progress.total}`;
    $("#job-progress").value = state.job.progress.percent;
    const running = state.job.status === "running";
    $("#cancel-button").hidden = !running;
    $("#start-button").hidden = running || terminalJobStatuses.has(state.job.status);
    $("#start-button").disabled = state.job.status !== "ready";
}

function openPreview(card) {
    $("#preview-word").textContent = card.word;
    $("#preview-text").textContent = card.card_text || "Текст ещё не создан";

    const imageWrap = $("#preview-image-wrap");
    imageWrap.hidden = !card.has_image;
    if (card.has_image && state.job) {
        $("#preview-image").src = `/api/jobs/${state.job.id}/cards/${card.id}/media/image`;
    }

    const audio = $("#preview-audio");
    audio.hidden = !card.has_audio;
    if (card.has_audio && state.job) {
        audio.src = `/api/jobs/${state.job.id}/cards/${card.id}/media/audio`;
    }

    const dictionary = $("#preview-dictionary");
    const safeUrl = card.dictionary_url && /^https?:\/\//.test(card.dictionary_url);
    dictionary.hidden = !safeUrl;
    if (safeUrl) dictionary.href = card.dictionary_url;
    $("#preview-dialog").showModal();
}

async function restoreJob() {
    const jobId = localStorage.getItem("anki-generator-job");
    if (!jobId) return;
    try {
        state.job = await api(`/api/jobs/${jobId}`);
        state.cards = state.job.cards;
        $("#queue-section").hidden = false;
        renderJob();
        if (!terminalJobStatuses.has(state.job.status)) startPolling();
    } catch (_error) {
        localStorage.removeItem("anki-generator-job");
    }
}

$("#file-input").addEventListener("change", (event) => {
    const file = event.target.files[0];
    $("#file-label").textContent = file ? `${file.name} · ${(file.size / 1024).toFixed(0)} КБ` : "До 10 МБ · колонки word и context";
});
$("#image-mode").addEventListener("change", (event) => {
    $("#replicate-settings").hidden = event.target.value !== "replicate";
});
$("#example-button").addEventListener("click", () => {
    $("#file-input").value = "";
    $("#file-label").textContent = "До 10 МБ · колонки word и context";
    $("#words-input").value = "purchasing power;economics\nconsciousness;philosophy\nfree will;decision making";
});
$("#parse-button").addEventListener("click", parseInput);
$("#start-button").addEventListener("click", startJob);
$("#cancel-button").addEventListener("click", cancelJob);
$("#close-preview").addEventListener("click", () => $("#preview-dialog").close());
$("#preview-dialog").addEventListener("click", (event) => {
    if (event.target === $("#preview-dialog")) $("#preview-dialog").close();
});

loadHealth();
restoreJob();
