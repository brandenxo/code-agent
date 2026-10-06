const promptInput = document.getElementById("promptInput");
const sendButton = document.getElementById("sendButton");
const messages = document.getElementById("messages");
const newChatButton = document.getElementById("newChatButton");
const chatList = document.getElementById("chatList");
const modelSelect = document.getElementById("modelSelect");

const modelNames = {
    "nvidia/nemotron-3-ultra-550b-a55b:free": "Nemotron 3 Ultra",
    "poolside/laguna-s-2.1:free": "Laguna S 2.1",
    "cohere/north-mini-code:free": "North Mini Code"
};

const categoryNames = {
    code_understanding: "Code understanding",
    debugging: "Debugging",
    feature_implementation: "Feature implementation",
    refactoring: "Refactoring",
    testing: "Testing",
    multi_step_tool_use: "Multi-step tool use"
};

function conciseRoutingReason(reason) {
    if (reason.includes("No usable benchmark data")) {
        return "Category fallback; benchmark data unavailable";
    }
    if (reason.includes("strongest normalized score")) {
        return "Highest combined benchmark score for this task type";
    }
    return reason;
}

let currentChatId = null;
let chats = [];
const messageCache = {};

sendButton.addEventListener("click", sendMessage);
newChatButton.addEventListener("click", createChat);
promptInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        sendMessage();
    }
});

async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Request failed");
    }
    return response.json();
}

async function initializeChats() {
    try {
        chats = await requestJson("/chats");
        if (chats.length === 0) {
            await createChat();
            return;
        }
        renderChatList();
        await switchChat(chats[0].id);
    } catch (error) {
        showPageError(error);
    }
}

async function sendMessage() {
    const prompt = promptInput.value.trim();
    if (!prompt || !currentChatId) {
        return;
    }

    const requestChatId = currentChatId;
    const requestedModel = modelSelect.value;
    const existingMessages = messageCache[requestChatId] || [];
    const isFirstMessage = existingMessages.length === 0;
    existingMessages.push({role: "user", content: prompt});
    messageCache[requestChatId] = existingMessages;
    addMessage(storedMessageToDisplay({role: "user", content: prompt}));
    promptInput.value = "";
    setWorkingState(true);

    if (isFirstMessage) {
        try {
            await saveChatTitle(requestChatId, createChatTitle(prompt));
        } catch (error) {
            console.error(error);
        }
    }

    const loadingMessage = addMessage({
        label: "Code Agent",
        text: "Thinking...",
        className: "agent-message"
    });

    try {
        const data = await requestJson("/chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                chat_id: requestChatId,
                prompt: prompt,
                model: requestedModel
            })
        });

        loadingMessage.remove();
        const routingDetails = data.requested_model === "auto"
            ? `Auto selected: ${modelNames[data.selected_model] || data.selected_model}\nTask: ${categoryNames[data.routing_category] || data.routing_category}\nWhy: ${conciseRoutingReason(data.routing_reason)}`
            : "";
        const agentMessage = {
            label: "Code Agent",
            text: data.response,
            className: "agent-message",
            stats: `${modelNames[data.model] || data.model} \u2022 ${data.latency}s \u2022 ${data.tokens} tokens \u2022 ${data.tool_calls} tools`,
            routingDetails: routingDetails,
            routingReason: data.routing_reason,
            useMarkdown: true
        };

        messageCache[requestChatId].push({
            role: "assistant",
            content: data.response,
            model_id: data.model
        });
        if (currentChatId === requestChatId) {
            addMessage(agentMessage);
        }
        refreshChats().catch((error) => console.error(error));
    } catch (error) {
        loadingMessage.remove();
        if (currentChatId === requestChatId) {
            addMessage({
                label: "Code Agent",
                text: error.message || "Something went wrong while processing the request.",
                className: "agent-message"
            });
        }
        console.error(error);
    } finally {
        setWorkingState(false);
    }
}

async function createChat() {
    try {
        const data = await requestJson("/chats", {method: "POST"});
        currentChatId = data.chat_id;
        messageCache[currentChatId] = [];
        await refreshChats();
        clearMessages();
        promptInput.focus();
    } catch (error) {
        showPageError(error);
    }
}

async function refreshChats() {
    chats = await requestJson("/chats");
    renderChatList();
}

async function saveChatTitle(chatId, title) {
    await requestJson(`/chats/${encodeURIComponent(chatId)}`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({title: title})
    });
    await refreshChats();
}

function createChatTitle(prompt) {
    const maximumLength = 25;
    return prompt.length <= maximumLength
        ? prompt
        : `${prompt.slice(0, maximumLength)}...`;
}

function renderChatList() {
    chatList.innerHTML = "";
    chats.forEach((chat) => {
        const chatButton = document.createElement("button");
        chatButton.type = "button";
        chatButton.className = "chat-item";
        chatButton.textContent = chat.title || "New Chat";
        if (chat.id === currentChatId) {
            chatButton.classList.add("active");
        }
        chatButton.addEventListener("click", () => switchChat(chat.id));
        chatList.appendChild(chatButton);
    });
}

async function switchChat(chatId) {
    if (!chats.some((chat) => chat.id === chatId)) {
        return;
    }

    currentChatId = chatId;
    clearMessages();
    renderChatList();
    try {
        const storedMessages = await requestJson(
            `/chats/${encodeURIComponent(chatId)}/messages`
        );
        messageCache[chatId] = storedMessages;
        if (currentChatId !== chatId) {
            return;
        }
        clearMessages();
        storedMessages.forEach((message) => {
            addMessage(storedMessageToDisplay(message));
        });
    } catch (error) {
        if (currentChatId === chatId) {
            showPageError(error);
        }
    }
    promptInput.focus();
}

function storedMessageToDisplay(message) {
    const isUser = message.role === "user";
    return {
        label: isUser ? "You" : "Code Agent",
        text: message.content,
        className: isUser ? "user-message" : "agent-message",
        stats: !isUser && message.model_id ? (modelNames[message.model_id] || message.model_id) : "",
        useMarkdown: !isUser
    };
}

function clearMessages() {
    messages.innerHTML = "";
    addMessage({
        label: "Code Agent",
        text: "What would you like me to build, debug, or explain?",
        className: "agent-message"
    });
}

function addMessage({
    label,
    text,
    className,
    stats = "",
    routingDetails = "",
    routingReason = "",
    useMarkdown = false
}) {
    const message = document.createElement("div");
    const labelElement = document.createElement("div");
    const bubble = document.createElement("div");

    message.className = `message ${className}`;
    labelElement.className = "label";
    labelElement.textContent = label;
    bubble.className = "bubble";
    if (useMarkdown) {
        bubble.innerHTML = marked.parse(text);
    } else {
        bubble.textContent = text;
    }
    message.appendChild(labelElement);
    message.appendChild(bubble);

    if (stats) {
        const statsElement = document.createElement("div");
        statsElement.className = "stats";
        statsElement.textContent = stats;
        message.appendChild(statsElement);
    }
    if (routingDetails) {
        const routingElement = document.createElement("div");
        routingElement.className = "routing-details";
        routingElement.textContent = routingDetails;
        routingElement.title = routingReason;
        message.appendChild(routingElement);
    }

    messages.appendChild(message);
    messages.scrollTop = messages.scrollHeight;
    return message;
}

function setWorkingState(working) {
    sendButton.disabled = working;
    promptInput.disabled = working;
    sendButton.textContent = working ? "Working..." : "Send";
    if (!working) {
        promptInput.focus();
    }
}

function showPageError(error) {
    console.error(error);
    clearMessages();
    addMessage({
        label: "Code Agent",
        text: error.message || "Unable to load chats.",
        className: "agent-message"
    });
}

const chatView = document.getElementById("chatView");
const benchmarksView = document.getElementById("benchmarksView");
const chatTab = document.getElementById("chatTab");
const benchmarksTab = document.getElementById("benchmarksTab");
let benchmarkRequest = 0;

function updateView() {
    const showBenchmarks = location.hash === "#benchmarks";
    chatView.hidden = showBenchmarks;
    benchmarksView.hidden = !showBenchmarks;
    document.getElementById("modelBox").hidden = showBenchmarks;
    document.querySelector(".sidebar").hidden = showBenchmarks;
    chatTab.setAttribute("aria-pressed", String(!showBenchmarks));
    benchmarksTab.setAttribute("aria-pressed", String(showBenchmarks));
    if (showBenchmarks) loadBenchmarks();
}

chatTab.addEventListener("click", () => { location.hash = "chat"; });
benchmarksTab.addEventListener("click", () => { location.hash = "benchmarks"; });
window.addEventListener("hashchange", updateView);
document.getElementById("refreshBenchmarks").addEventListener("click", loadBenchmarks);

function element(tag, text = "", className = "") {
    const node = document.createElement(tag);
    node.textContent = text;
    if (className) node.className = className;
    return node;
}

function number(value, digits = 1, suffix = "") {
    return value == null ? "N/A" : `${value.toLocaleString(undefined, {
        maximumFractionDigits: digits
    })}${suffix}`;
}

function percent(value) {
    return value == null ? "N/A" : number(value * 100, 1, "%");
}

function evidenceBadge(selection) {
    return element("span", selection.evidence_type === "benchmark"
        ? "Benchmark-driven" : "Fallback", `routing-badge ${selection.evidence_type}`);
}

function benchmarkTable(parent, title, headers, description = "") {
    const section = element("section", "", "benchmark-section");
    section.append(element("h3", title));
    if (description) section.append(element("p", description, "section-description"));
    const wrapper = element("div", "", "table-scroll");
    wrapper.tabIndex = 0;
    wrapper.setAttribute("aria-label", `${title}, horizontally scrollable table`);
    const table = element("table");
    const head = element("thead");
    const row = element("tr");
    headers.forEach((label) => {
        const cell = element("th", label);
        cell.scope = "col";
        row.append(cell);
    });
    head.append(row);
    const body = element("tbody");
    table.append(head, body);
    wrapper.append(table);
    section.append(wrapper);
    parent.append(section);
    return body;
}

async function loadBenchmarks() {
    const request = ++benchmarkRequest;
    const status = document.getElementById("benchmarkStatus");
    const content = document.getElementById("benchmarkContent");
    status.textContent = "Loading benchmark data...";
    try {
        const data = await requestJson("/benchmarks/summary");
        if (request !== benchmarkRequest) return;
        content.replaceChildren();
        renderBenchmarks(data, content);
        status.textContent = data.models.length ? "" : "No active models available.";
    } catch (error) {
        if (request !== benchmarkRequest) return;
        content.replaceChildren();
        status.textContent = `Unable to load benchmarks: ${error.message}. Use Refresh to retry.`;
    }
}

function renderBenchmarks(data, content) {
    const cards = element("div", "", "model-cards");
    data.models.forEach((model) => {
        const summary = model.internal;
        const card = element("article", "", "model-card");
        card.append(element("h3", model.display_name), element("p", model.provider, "provider"));
        const metrics = element("dl");
        [
            ["Internal runs", number(summary.runs, 0)],
            ["Success", percent(summary.success_rate)],
            ["Avg latency", number(summary.avg_latency, 2, "s")],
            ["Avg tokens", number(summary.avg_tokens, 0)],
            ["Avg tool calls", number(summary.avg_tool_calls)]
        ].forEach(([label, value]) => {
            metrics.append(element("dt", label), element("dd", value));
        });
        card.append(metrics);
        cards.append(card);
    });
    content.append(cards);

    const categories = benchmarkTable(content, "Internal category comparison",
        ["Category", ...data.models.map((model) => model.display_name), "Auto Pick"]);
    Object.entries(categoryNames).forEach(([category, label]) => {
        const row = element("tr");
        row.append(element("th", label));
        data.models.forEach((model) => {
            const summary = model.categories[category];
            const cell = element("td");
            cell.append(element("strong", `${percent(summary.success_rate)} success`),
                element("span", `${number(summary.avg_latency, 2, "s")} / ${number(summary.avg_tokens, 0)} tokens`, "cell-secondary"));
            row.append(cell);
        });
        const pick = element("td");
        const selection = data.routing[category];
        pick.append(element("div", selection.display_name), evidenceBadge(selection));
        row.append(pick);
        categories.append(row);
    });

    const external = benchmarkTable(content, "Published External Benchmarks",
        ["Model", "Benchmark", "Score", "Source", "Published"],
        "External results are published benchmark data and were not measured by this project.");
    let externalCount = 0;
    data.models.forEach((model) => model.external.forEach((record) => {
        externalCount++;
        const row = element("tr");
        row.append(element("td", model.display_name), element("td", record.benchmark_name),
            element("td", number(record.score, 2)));
        const source = element("td");
        // Only web URLs should become clickable source links.
        if (record.source_url && /^https?:\/\//i.test(record.source_url)) {
            const link = element("a", record.source);
            link.href = record.source_url;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            source.append(link);
        } else {
            source.textContent = record.source;
        }
        row.append(source, element("td", record.published_date || "N/A"));
        external.append(row);
    }));
    if (!externalCount) {
        const row = element("tr");
        const cell = element("td", "No published external benchmarks stored.");
        cell.colSpan = 5;
        row.append(cell);
        external.append(row);
    }

    const routing = benchmarkTable(content, "Current Auto Routing",
        ["Task Type", "Preferred Model", "Evidence", "Reason"]);
    Object.entries(categoryNames).forEach(([category, label]) => {
        const selection = data.routing[category];
        const row = element("tr");
        const evidence = element("td");
        evidence.append(evidenceBadge(selection));
        const reason = element("td", conciseRoutingReason(selection.reason));
        const details = element("details");
        details.append(element("summary", "Full reason"), element("p", selection.reason));
        reason.append(details);
        row.append(element("th", label), element("td", selection.display_name), evidence, reason);
        routing.append(row);
    });
}

initializeChats();
updateView();
