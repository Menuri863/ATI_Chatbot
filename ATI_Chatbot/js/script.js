document.addEventListener("DOMContentLoaded", () => {
    const sendBtn = document.querySelector(".send-icon-btn");
    const inputField = document.getElementById("userInput");
    const chatHistory = document.getElementById("chatHistory");

    function addMessage(text, sender) {
        const chatRow = document.createElement("div");
        const currentTime = new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit"
        });

        chatRow.className =
            sender === "user" ? "chat-row user-row" : "chat-row bot-row";

        const bubble = document.createElement("div");
        bubble.className =
            sender === "user" ? "bubble user-bubble" : "bubble bot-bubble";
        bubble.textContent = text;

        const time = document.createElement("span");
        time.className =
            sender === "user" ? "time-stamp" : "time-stamp-left";
        time.textContent =
            sender === "user" ? currentTime + " ✓✓" : currentTime;

        chatRow.appendChild(bubble);
        chatRow.appendChild(time);
        chatHistory.appendChild(chatRow);

        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    async function handleUserMessage() {
        if (!inputField || !chatHistory) return;

        const text = inputField.value.trim();

        if (text === "") return;

        addMessage(text, "user");
        inputField.value = "";

        if (sendBtn) sendBtn.disabled = true;

        try {
            const response = await fetch("/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    message: text
                })
            });

            if (!response.ok) {
                throw new Error("Server returned status " + response.status);
            }

            const data = await response.json();

            addMessage(
                data.reply || "Sorry, I could not find an answer.",
                "bot"
            );
        } catch (error) {
            console.error("Chatbot connection error:", error);
            addMessage(
                "Sorry, I could not connect to the chatbot server. Please check that Flask is running.",
                "bot"
            );
        } finally {
            if (sendBtn) sendBtn.disabled = false;
        }
    }

    if (sendBtn) {
        sendBtn.addEventListener("click", handleUserMessage);
    }

    if (inputField) {
        inputField.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                handleUserMessage();
            }
        });
    }

    document.querySelectorAll(".qq-btn").forEach((button) => {
        button.addEventListener("click", () => {
            if (!inputField) return;

            inputField.value = button.textContent
                .replace(/^[^\w\s]+/, "")
                .trim();

            handleUserMessage();
        });
    });
});