const state = {
    cards: [],
    job: null,
    pollTimer: null,
    previewSide: "front",
    previewMode: "template",
    previewData: null,
    previewMedia: null,
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
const levelsByLanguage = {
    english: ["A1", "A2", "B1", "B2", "C1", "C2"],
    german: ["A1", "A2", "B1", "B2", "C1", "C2"],
    greek: ["A1", "A2"],
};
const defaultLevelByLanguage = {english: "C1", german: "C1", greek: "A1"};
const textModelPrices = {
    "gpt-5.6-luna": {name: "GPT-5.6 Luna", input: 0.20, cached: 0.02, output: 1.20},
    "gpt-5.6-terra": {name: "GPT-5.6 Terra", input: 2.00, cached: 0.20, output: 12.00},
    "gpt-5.6-sol": {name: "GPT-5.6 Sol", input: 4.00, cached: 0.40, output: 20.00, note: "Промоцена; вход / кэш / выход · за 1 млн токенов"},
    "gpt-5.4-nano": {name: "GPT-5.4 nano", input: 0.20, cached: 0.02, output: 1.25},
    "gpt-5.4-mini": {name: "GPT-5.4 mini", input: 0.75, cached: 0.075, output: 4.50},
    "gpt-4.1-mini": {name: "GPT-4.1 mini", input: 0.40, cached: 0.10, output: 1.60},
    "gpt-4.1": {name: "GPT-4.1", input: 2.00, cached: 0.50, output: 8.00},
    "gpt-4o-mini": {name: "GPT-4o mini", input: 0.15, cached: 0.075, output: 0.60},
    "gpt-4o": {name: "GPT-4o", input: 2.50, cached: 1.25, output: 10.00},
};
const cardCostAssumptions = {
    textInputTokens: 2500,
    textOutputTokens: 500,
    imagePromptTokens: 200,
    imageTextInputPerMillion: 5,
    imageOutputCost: 0.006,
    ttsTextInputPerMillion: 0.60,
    ttsAudioOutputPerMillion: 12,
    ttsInstructionTokensPerRequest: 50,
    ttsOutputTokensPerSpokenCharacter: 2.1,
    defaultWordCharacters: 12,
    greekContextCharacters: 75,
};
const greekCardTypes = [
    {id: "production", name: "ACTIVE RECALL · Production"},
    {id: "recognition", name: "RECOGNITION · Comprehension"},
    {id: "context", name: "CONTEXT RECALL · Usage"},
];
const previewTemplates = {
    classic: {
        name: "Классический",
        description: "Изображение, контекст с пропусками, словарь и аудио",
        cardTypes: [{id: "classic", name: "Классическая карточка"}],
        sample: {
            word: "free will",
            card_text: "Something that allows people to make choices independently is known as ____ ___. Philosophers debate whether ____ ___ truly exists or whether our decisions are predetermined.",
            image_url: "/static/classic-template-sample.svg",
            dictionary_url: "https://dictionary.cambridge.org/dictionary/english/free-will",
        },
    },
    "greek-vocabulary": {
        name: "Greek Vocabulary",
        description: "одна заметка · три независимые карточки",
        cardTypes: greekCardTypes,
        sample: {
            article: "η",
            greek_word: "πόρτα",
            transcription: "и пОрта",
            translation: "дверь",
            context_greek: "Άνοιξε την πόρτα, σε παρακαλώ.",
            context_transcription: "Аниксе тин пОрта, се паракалО.",
            context_russian: "Открой дверь, пожалуйста.",
            context_cloze: "Άνοιξε την _____, σε παρακαλώ.",
            context_cloze_transcription: "Аниксе тин _____, се паракалО.",
            context_answer: "πόρτα",
            has_context: true,
            image_url: "/static/classic-template-sample.svg",
        },
    },
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
        syncCardCostEstimate();
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

function selectedTextModel() {
    const selected = $("#text-model").value;
    if (selected !== "__custom__") return selected;
    const customModel = $("#custom-text-model").value.trim();
    if (!customModel) throw new Error("Укажите ID модели OpenAI");
    return customModel;
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
        text_model: selectedTextModel(),
        replicate_api_key: $("#replicate-key").value.trim(),
        replicate_model_url: $("#replicate-model").value.trim(),
        processing_directory: $("#processing-directory").value.trim(),
        anki_media_directory: $("#anki-media-directory").value.trim(),
        create_deck: $("#create-deck").checked,
        import_after_generation: $("#import-after").checked,
    };
}

function syncLanguageLevels() {
    const language = $("#language").value;
    const isGreek = language === "greek";
    const levelSelect = $("#level");
    const previousLevel = levelSelect.value;
    const availableLevels = levelsByLanguage[language] || levelsByLanguage.english;
    levelSelect.replaceChildren(
        ...availableLevels.map((level) => {
            const option = document.createElement("option");
            option.value = level;
            option.textContent = level;
            return option;
        }),
    );
    levelSelect.value = availableLevels.includes(previousLevel)
        ? previousLevel
        : defaultLevelByLanguage[language];

    $("#words-input-label").textContent = isGreek ? "Русские слова и контекст" : "Слова и контекст";
    $("#words-input").placeholder = isGreek
        ? "дверь;дом\nпокупка;магазин\nвстречаться;друзья"
        : "purchasing power;economics\nconsciousness;philosophy\nfree will";
    $("#words-input-help").textContent = isGreek
        ? "Введите по-русски. Модель создаст греческое слово, артикль, транскрипцию и пример."
        : "Одно слово на строку. Контекст можно добавить после точки с запятой.";
    $("#card-model").disabled = isGreek;
    $("#card-model-note").textContent = isGreek
        ? "Для греческого автоматически создаётся безопасная версия Greek Vocabulary v1."
        : "Используется для английских и немецких карточек.";
    $("#audio-price-note").textContent = isGreek
        ? "Голос Marin; вход $0.60, аудиовыход $12 за 1 млн токенов; озвучиваются слово с артиклем и полная фраза"
        : "Голос Marin; вход $0.60, аудиовыход $12 за 1 млн токенов; озвучивается только слово";
    $("#greek-audio-note").hidden = !isGreek;
    $("#preview-template").value = isGreek ? "greek-vocabulary" : "classic";
    syncCardCostEstimate();
}

function syncCustomTextModel() {
    const custom = $("#text-model").value === "__custom__";
    $("#custom-text-model-field").hidden = !custom;
    if (custom) $("#custom-text-model").focus();
    syncOpenAIPricing();
}

function syncOpenAIPricing() {
    const selected = $("#text-model").value;
    const pricing = textModelPrices[selected];
    if (pricing) {
        $("#text-price-model").textContent = pricing.name;
        $("#text-price-value").textContent = `${formatRate(pricing.input)} / ${formatRate(pricing.cached)} / ${formatRate(pricing.output)}`;
        $("#text-price-note").textContent = pricing.note || "Вход / кэш / выход · за 1 млн токенов";
    } else {
        const customName = $("#custom-text-model").value.trim();
        $("#text-price-model").textContent = customName || "другая модель";
        $("#text-price-value").textContent = "Цена не указана";
        $("#text-price-note").textContent = "Проверьте тариф для выбранного ID в документации OpenAI";
    }

    const usesOpenAIImages = $("#image-mode").value === "openai";
    $("#image-price-model").textContent = usesOpenAIImages ? "GPT Image 2" : "Replicate";
    $("#image-price-value").textContent = usesOpenAIImages
        ? "≈ $0.006 за изображение"
        : "Зависит от выбранной модели";
    $("#image-price-note").textContent = usesOpenAIImages
        ? "1024×1024 · low, плюс вход prompt. Текст: $5 / $1.25; изображение: $8 / $2 / $30 за 1 млн токенов."
        : "Проверьте стоимость версии модели на странице Replicate";
    syncCardCostEstimate();
}

function formatRate(value) {
    return `$${value.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 3})}`;
}

function formatEstimatedCost(value) {
    const fractionDigits = value < 0.001 ? 5 : 4;
    return `$${value.toFixed(fractionDigits)}`;
}

function wordsForCostEstimate() {
    if (state.cards.length) return state.cards.map((card) => card.word).filter(Boolean);
    return $("#words-input").value
        .split(/\r?\n/)
        .map((line) => line.split(";", 1)[0].trim())
        .filter((word, index) => word && !(index === 0 && word.toLowerCase() === "word"));
}

function estimatedAudioCharacters() {
    const words = wordsForCostEstimate();
    const averageWordCharacters = words.length
        ? words.reduce((total, word) => total + word.length, 0) / words.length
        : cardCostAssumptions.defaultWordCharacters;
    const greekContext = $("#language").value === "greek"
        ? cardCostAssumptions.greekContextCharacters
        : 0;
    return Math.round(averageWordCharacters + greekContext);
}

function calculateAudioCost(audioCharacters, requestCount) {
    const inputTokens = Math.ceil(audioCharacters / 4)
        + requestCount * cardCostAssumptions.ttsInstructionTokensPerRequest;
    const outputTokens = Math.ceil(
        audioCharacters * cardCostAssumptions.ttsOutputTokensPerSpokenCharacter,
    );
    const cost = (
        inputTokens * cardCostAssumptions.ttsTextInputPerMillion
        + outputTokens * cardCostAssumptions.ttsAudioOutputPerMillion
    ) / 1_000_000;
    return {cost, inputTokens, outputTokens};
}

function calculateCardCost(pricing, usesOpenAIImages, audioCharacters, audioRequestCount) {
    if (!pricing) return null;
    const text = (
        cardCostAssumptions.textInputTokens * pricing.input
        + cardCostAssumptions.textOutputTokens * pricing.output
    ) / 1_000_000;
    const image = usesOpenAIImages
        ? cardCostAssumptions.imageOutputCost
            + cardCostAssumptions.imagePromptTokens * cardCostAssumptions.imageTextInputPerMillion / 1_000_000
        : null;
    const audio = calculateAudioCost(audioCharacters, audioRequestCount).cost;
    return {text, image, audio, knownTotal: text + audio + (image || 0)};
}

function syncCardCostEstimate() {
    const pricing = textModelPrices[$("#text-model").value];
    const usesOpenAIImages = $("#image-mode").value === "openai";
    const isGreek = $("#language").value === "greek";
    const audioCharacters = estimatedAudioCharacters();
    const audioRequestCount = isGreek ? 2 : 1;
    const audioEstimate = calculateAudioCost(audioCharacters, audioRequestCount);
    const estimate = calculateCardCost(
        pricing,
        usesOpenAIImages,
        audioCharacters,
        audioRequestCount,
    );
    $("#card-cost-title").textContent = isGreek
        ? "Примерно за 1 заметку · до 3 карточек"
        : "Примерно за 1 новую карточку";

    if (!estimate) {
        $("#card-cost-total").textContent = "Нет полной оценки";
        $("#card-cost-text").textContent = "нет тарифа";
        $("#card-cost-image").textContent = usesOpenAIImages ? "≈ $0.0070" : "тариф Replicate";
        $("#card-cost-audio").textContent = `≈ ${formatEstimatedCost(audioEstimate.cost)}`;
        $("#card-cost-summary").textContent = "Для собственного ID модели нужна известная цена";
    } else {
        $("#card-cost-total").textContent = usesOpenAIImages
            ? `≈ ${formatEstimatedCost(estimate.knownTotal)}`
            : `≈ ${formatEstimatedCost(estimate.knownTotal)} + Replicate`;
        $("#card-cost-text").textContent = `≈ ${formatEstimatedCost(estimate.text)}`;
        $("#card-cost-image").textContent = estimate.image === null
            ? "тариф Replicate"
            : `≈ ${formatEstimatedCost(estimate.image)}`;
        $("#card-cost-audio").textContent = `≈ ${formatEstimatedCost(estimate.audio)}`;
        $("#card-cost-summary").textContent = usesOpenAIImages
            ? `${pricing.name} · изображение OpenAI · GPT-4o mini TTS${isGreek ? " · 2 аудио" : ""}`
            : `${pricing.name} · без цены Replicate · GPT-4o mini TTS${isGreek ? " · 2 аудио" : ""}`;
    }
    $("#card-cost-assumptions").textContent = `Оценка: 2 500 входных + 500 выходных/reasoning-токенов текста, 200 токенов image prompt, ≈ ${audioEstimate.inputTokens} входных + ${audioEstimate.outputTokens} аудиотокенов TTS${isGreek ? " для слова и фразы" : ""}. Без кэша.`;
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
        preview.textContent = "Предпросмотр";
        preview.disabled = !card.card_text;
        preview.addEventListener("click", () => openPreview(card));
        actionCell.append(preview);

        row.append(wordCell, contextCell, statusCell, actionCell);
        body.append(row);
    }
}

function renderBatchCost(cost) {
    const summary = $("#batch-cost-summary");
    if (!cost) {
        summary.hidden = true;
        return;
    }

    summary.hidden = false;
    const hasRequests = cost.request_count > 0;
    const totalPrefix = !cost.complete ? "≥ " : (hasRequests ? "≈ " : "");
    $("#batch-cost-total").textContent = `${totalPrefix}${formatEstimatedCost(cost.total_usd || 0)}`;

    const generated = cost.generated_items || 0;
    const cached = cost.cached_items || 0;
    const skipped = cost.skipped_items || 0;
    const averagePrefix = cost.complete ? "≈ " : "≥ ";
    $("#batch-cost-average").textContent = generated
        ? `${averagePrefix}${formatEstimatedCost(cost.average_usd || 0)} / слово`
        : "—";
    $("#batch-cost-counts").textContent = [
        `${generated} новых`,
        `${cached} из кэша`,
        ...(skipped ? [`${skipped} пропущено`] : []),
    ].join(" · ");

    if (cost.complete) {
        $("#batch-cost-note").textContent = hasRequests
            ? "По фактическому API usage и стандартным тарифам; сумма может отличаться от биллинга"
            : "Новых платных API-вызовов пока не было";
    } else {
        const unknown = (cost.unknown_components || []).join(", ");
        $("#batch-cost-note").textContent = `Не включено в TOTAL: ${unknown}`;
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
    renderBatchCost(state.job.cost);
    const running = state.job.status === "running";
    $("#cancel-button").hidden = !running;
    $("#start-button").hidden = running || terminalJobStatuses.has(state.job.status);
    $("#start-button").disabled = state.job.status !== "ready";
}

function setPreviewSide(side) {
    state.previewSide = side === "back" ? "back" : "front";
    const showBack = state.previewSide === "back";
    $("#anki-preview-card").classList.toggle("is-flipped", showBack);
    $("#preview-front").setAttribute("aria-hidden", String(showBack));
    $("#preview-back").setAttribute("aria-hidden", String(!showBack));
    $("#preview-front").inert = showBack;
    $("#preview-back").inert = !showBack;
    document.querySelectorAll("[data-preview-side]").forEach((button) => {
        const active = button.dataset.previewSide === state.previewSide;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-selected", String(active));
    });
    $("#flip-preview").textContent = showBack
        ? "Показать лицевую сторону"
        : "Показать оборотную сторону";
}

function setPreviewImage(source, side) {
    const wrap = $(`#preview-${side}-image-wrap`);
    const image = $(`#preview-${side}-image`);
    wrap.hidden = !source;
    image.removeAttribute("src");
    if (source) image.src = source;
}

function setPreviewLayout(templateKey) {
    const classic = templateKey === "classic";
    $("#preview-classic-front").hidden = !classic;
    $("#preview-classic-back").hidden = !classic;
    $("#preview-greek-front").hidden = classic;
    $("#preview-greek-back").hidden = classic;
}

function syncPreviewCardTypes(template, hasContext = true) {
    const select = $("#preview-card-type");
    const previous = select.value;
    select.replaceChildren(...template.cardTypes.map((cardType) => {
        const option = document.createElement("option");
        option.value = cardType.id;
        option.textContent = cardType.name;
        option.disabled = cardType.id === "context" && !hasContext;
        return option;
    }));
    const reusable = [...select.options].some((option) => option.value === previous && !option.disabled);
    if (reusable) select.value = previous;
    $("#preview-card-type-field").hidden = template.cardTypes.length <= 1;
}

function renderGreekCardType() {
    const selected = $("#preview-card-type").value || "production";
    document.querySelectorAll("[data-greek-card]").forEach((section) => {
        section.hidden = section.dataset.greekCard !== selected;
    });
}

function setGreekAudio(groupSelector, source, showPlaceholder) {
    document.querySelectorAll(groupSelector).forEach((wrap) => {
        const audio = wrap.querySelector("audio");
        const placeholder = wrap.querySelector(".audio-placeholder");
        audio.pause();
        audio.removeAttribute("src");
        audio.hidden = !source;
        if (source) audio.src = source;
        placeholder.hidden = !showPlaceholder;
        wrap.hidden = !source && !showPlaceholder;
    });
}

function populateGreekPreview(data, {
    imageSource = null,
    audioSource = null,
    contextAudioSource = null,
    showAudioPlaceholders = false,
    note = "",
} = {}) {
    state.previewData = data;
    state.previewMedia = {imageSource, audioSource, contextAudioSource};
    setPreviewLayout("greek-vocabulary");

    const fields = {
        ...data,
        full_word: [data.article, data.greek_word].filter(Boolean).join(" "),
    };
    document.querySelectorAll("[data-greek-field]").forEach((element) => {
        element.textContent = fields[element.dataset.greekField] || "";
    });
    document.querySelectorAll("[data-greek-image-wrap]").forEach((wrap) => {
        const image = wrap.querySelector("[data-greek-image]");
        wrap.hidden = !imageSource;
        image.removeAttribute("src");
        if (imageSource) image.src = imageSource;
    });

    const hasContext = Boolean(
        data.has_context
        || (data.context_greek && data.context_cloze && data.context_answer)
    );
    document.querySelectorAll("[data-greek-context]").forEach((section) => {
        section.hidden = !hasContext;
    });
    syncPreviewCardTypes(previewTemplates["greek-vocabulary"], hasContext);
    renderGreekCardType();
    setGreekAudio("[data-greek-word-audio-wrap]", audioSource, showAudioPlaceholders);
    setGreekAudio("[data-greek-context-audio-wrap]", contextAudioSource, showAudioPlaceholders && hasContext);
    $("#preview-model-note").textContent = note;
    setPreviewSide("front");
    if (!$("#preview-dialog").open) $("#preview-dialog").showModal();
}

function populatePreview(card, {imageSource = null, audioSource = null, showAudioPlaceholder = false, note = ""} = {}) {
    state.previewData = card;
    state.previewMedia = {imageSource, audioSource};
    setPreviewLayout("classic");
    syncPreviewCardTypes(previewTemplates.classic);
    const cardText = card.card_text || "Текст ещё не создан";
    $("#preview-front-text").textContent = cardText;
    $("#preview-back-text").textContent = cardText;
    $("#preview-back-word").textContent = card.word;
    setPreviewImage(imageSource, "front");
    setPreviewImage(imageSource, "back");

    const audio = $("#preview-audio");
    audio.pause();
    audio.removeAttribute("src");
    audio.hidden = !audioSource;
    if (audioSource) audio.src = audioSource;
    $("#preview-audio-placeholder").hidden = !showAudioPlaceholder;

    const dictionary = $("#preview-dictionary");
    const safeUrl = card.dictionary_url && /^https?:\/\//.test(card.dictionary_url);
    dictionary.hidden = !safeUrl;
    if (safeUrl) dictionary.href = card.dictionary_url;
    else dictionary.removeAttribute("href");

    $("#preview-model-note").textContent = note;
    setPreviewSide("front");
    if (!$("#preview-dialog").open) $("#preview-dialog").showModal();
}

function openTemplatePreview() {
    state.previewMode = "template";
    const templateKey = $("#preview-template").value;
    const template = previewTemplates[templateKey] || previewTemplates.classic;
    if (templateKey === "greek-vocabulary") {
        populateGreekPreview(template.sample, {
            imageSource: template.sample.image_url,
            showAudioPlaceholders: true,
            note: `Статичный пример · ${template.description}`,
        });
        return;
    }
    populatePreview(template.sample, {
        imageSource: template.sample.image_url,
        showAudioPlaceholder: true,
        note: `Статичный пример · ${template.description}`,
    });
}

function openPreview(card) {
    state.previewMode = "generated";
    const imageSource = card.has_image && state.job
        ? `/api/jobs/${state.job.id}/cards/${card.id}/media/image`
        : null;
    const audioSource = card.has_audio && state.job
        ? `/api/jobs/${state.job.id}/cards/${card.id}/media/audio`
        : null;

    if (card.preview_kind === "greek-vocabulary") {
        $("#preview-template").value = "greek-vocabulary";
        const contextAudioSource = card.has_context_audio && state.job
            ? `/api/jobs/${state.job.id}/cards/${card.id}/media/context-audio`
            : null;
        populateGreekPreview(card, {
            imageSource,
            audioSource,
            contextAudioSource,
            note: card.has_context
                ? "Greek Vocabulary · три независимые карточки"
                : "Greek Vocabulary · контекст недоступен, созданы две карточки",
        });
        return;
    }

    $("#preview-template").value = "classic";
    const modelName = state.job?.settings?.card_model || "Basic (type in the answer)";
    const note = modelName === "Basic (type in the answer)"
        ? "Приближённый вид стандартного Basic (type in the answer)"
        : `Поля карточки; итоговое оформление зависит от шаблона «${modelName}»`;
    populatePreview(card, {imageSource, audioSource, note});
}

function closePreview() {
    $("#preview-dialog").querySelectorAll("audio").forEach((audio) => audio.pause());
    $("#preview-dialog").close();
}

async function restoreJob() {
    const jobId = localStorage.getItem("anki-generator-job");
    if (!jobId) return;
    try {
        state.job = await api(`/api/jobs/${jobId}`);
        state.cards = state.job.cards;
        syncCardCostEstimate();
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
    syncOpenAIPricing();
});
$("#language").addEventListener("change", syncLanguageLevels);
$("#text-model").addEventListener("change", syncCustomTextModel);
$("#custom-text-model").addEventListener("input", syncOpenAIPricing);
$("#words-input").addEventListener("input", syncCardCostEstimate);
$("#example-button").addEventListener("click", () => {
    $("#file-input").value = "";
    $("#file-label").textContent = "До 10 МБ · колонки word и context";
    $("#words-input").value = $("#language").value === "greek"
        ? "дверь;дом\nпокупка;магазин\nвстречаться;друзья"
        : "purchasing power;economics\nconsciousness;philosophy\nfree will;decision making";
    syncCardCostEstimate();
});
$("#parse-button").addEventListener("click", parseInput);
$("#start-button").addEventListener("click", startJob);
$("#cancel-button").addEventListener("click", cancelJob);
$("#template-preview-button").addEventListener("click", openTemplatePreview);
$("#preview-template").addEventListener("change", openTemplatePreview);
$("#preview-card-type").addEventListener("change", renderGreekCardType);
document.querySelectorAll("[data-preview-side]").forEach((button) => {
    button.addEventListener("click", () => setPreviewSide(button.dataset.previewSide));
});
$("#flip-preview").addEventListener("click", () => {
    setPreviewSide(state.previewSide === "front" ? "back" : "front");
});
$("#close-preview").addEventListener("click", closePreview);
$("#preview-dialog").addEventListener("click", (event) => {
    if (event.target === $("#preview-dialog")) closePreview();
});

loadHealth();
syncLanguageLevels();
syncCustomTextModel();
restoreJob();
