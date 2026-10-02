const promptInput = document.getElementById("promptInput");
const sendButton = document.getElementById("sendButton");
const messages = document.getElementById("messages");
const newChatButton = document.getElementById("newChatButton");
const chatList = document.getElementById("chatList");

let currentChatId = null;
let chats = {};

sendButton.addEventListener("click", sendMessage);
newChatButton.addEventListener("click", createChat);
promptInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        sendMessage();
    }
});

async function sendMessage() {
    const prompt = promptInput.value.trim();

    if (!prompt || !currentChatId) {
        return;
    }

    const requestChatId = currentChatId;
    const chat = chats[requestChatId];

    const userMessage = {
        label: "You",
        text: prompt,
        className: "user-message",
        stats: "",
        useMarkdown: false
    };

    chat.messages.push(userMessage);
    addMessage(userMessage);

    if (chat.messages.length === 1) {
        chat.title = createChatTitle(prompt);
        renderChatList();
    }

    promptInput.value = "";
    sendButton.disabled = true;
    promptInput.disabled = true;
    sendButton.textContent = "Working...";

    const loadingMessage = addMessage({
        label: "Code Agent",
        text: "Thinking...",
        className: "agent-message",
        stats: "",
        useMarkdown: false
    });

    try {
        const response = await fetch("http://localhost:8000/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                chat_id: requestChatId,
                prompt: prompt
            })
        });

        if (!response.ok) {
            throw new Error("Request failed");
        }

        const data = await response.json();

        loadingMessage.remove();

        const agentMessage = {
            label: "Code Agent",
            text: data.response,
            className: "agent-message",
            stats: `${data.model} \u2022 ${data.latency}s \u2022 ${data.tokens} tokens \u2022 ${data.tool_calls} tool calls`,
            useMarkdown: true
        };

        chats[requestChatId].messages.push(agentMessage);

        if (currentChatId === requestChatId) {
            addMessage(agentMessage);
        }
    } catch (error) {
        loadingMessage.remove();

        const errorMessage = {
            label: "Code Agent",
            text: "Something went wrong while processing the request.",
            className: "agent-message",
            stats: "",
            useMarkdown: false
        };

        chats[requestChatId].messages.push(errorMessage);

        if (currentChatId === requestChatId) {
            addMessage(errorMessage);
        }

        console.error(error);
    } finally {
        sendButton.disabled = false;
        promptInput.disabled = false;
        sendButton.textContent = "Send";
        promptInput.focus();
    }
}

async function createChat() {
    try {
        const response = await fetch("http://localhost:8000/chats", {
            method: "POST"
        });

        if (!response.ok) {
            throw new Error("Unable to create chat");
        }

        const data = await response.json();

        currentChatId = data.chat_id;
        chats[currentChatId] = {
            title: "New Chat",
            messages: []
        };

        clearMessages();
        renderChatList();
        promptInput.focus();
    } catch (error) {
        console.error(error);
    }
}

function createChatTitle(prompt) {
    const maximumLength = 25;

    if (prompt.length <= maximumLength) {
        return prompt;
    }

    return `${prompt.slice(0, maximumLength)}...`;
}

function renderChatList() {
    chatList.innerHTML = "";

    Object.entries(chats).forEach(([chatId, chat]) => {
        const chatButton = document.createElement("button");

        chatButton.type = "button";
        chatButton.className = "chat-item";
        chatButton.textContent = chat.title;

        if (chatId === currentChatId) {
            chatButton.classList.add("active");
        }

        chatButton.addEventListener("click", () => switchChat(chatId));
        chatList.appendChild(chatButton);
    });
}

function switchChat(chatId) {
    if (!chats[chatId]) {
        return;
    }

    currentChatId = chatId;
    clearMessages();

    chats[chatId].messages.forEach((message) => {
        addMessage(message);
    });

    renderChatList();
    promptInput.focus();
}

function clearMessages() {
    messages.innerHTML = "";

    addMessage({
        label: "Code Agent",
        text: "What would you like me to build, debug, or explain?",
        className: "agent-message",
        stats: "",
        useMarkdown: false
    });
}

function addMessage({
    label,
    text,
    className,
    stats = "",
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

    messages.appendChild(message);
    messages.scrollTop = messages.scrollHeight;

    return message;
}

createChat();
