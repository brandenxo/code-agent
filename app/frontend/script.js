const promptInput = document.getElementById("promptInput");
const sendButton = document.getElementById("sendButton");
const messages = document.getElementById("messages");


sendButton.addEventListener("click", sendMessage);


async function sendMessage() {
    const prompt = promptInput.value.trim();

    if (!prompt) {
        return;
    }

    addMessage(
        "You",
        prompt,
        "user-message"
    );

    promptInput.value = "";

    const response = await fetch(
        "http://localhost:8000/chat",
        {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                prompt: prompt
            })
        }
    );

    const data = await response.json();

    const stats =
        `${data.model} • ${data.latency}s • ${data.tokens} tokens • ${data.tool_calls} tool calls`;

    addMessage(
        "Code Agent",
        data.response,
        "agent-message",
        stats
    );
}


function addMessage(label, text, className, stats = "") {

    const message = document.createElement("div");

    message.className = `message ${className}`;

    message.innerHTML = `
        <div class="label">${label}</div>

        <div class="bubble">
            ${text}
        </div>

        ${stats ? `<div class="stats">${stats}</div>` : ""}
    `;

    messages.appendChild(message);

    messages.scrollTop = messages.scrollHeight;
}