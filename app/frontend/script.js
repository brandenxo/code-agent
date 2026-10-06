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
            ? `Auto selected: ${modelNames[data.selected_model] || data.selected_model}\nTask type: ${data.routing_category}\nReason: ${data.routing_reason}`
            : "";
        const agentMessage = {
            label: "Code Agent",
            text: data.response,
            className: "agent-message",
            stats: `${data.model} \u2022 ${data.latency}s \u2022 ${data.tokens} tokens \u2022 ${data.tool_calls} tool calls`,
            routingDetails: routingDetails,
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
        stats: !isUser && message.model_id ? message.model_id : "",
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

initializeChats();
