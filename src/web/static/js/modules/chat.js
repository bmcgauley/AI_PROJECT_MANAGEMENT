// Chat UI module
import { escapeHtml } from './utils.js';

export class ChatUI {
    constructor(chatBoxId = 'chat-box') {
        this.chatBox = document.getElementById(chatBoxId);
        if (!this.chatBox) {
            throw new Error(`Chat box element with ID '${chatBoxId}' not found`);
        }
    }

    addUserMessage(message) {
        const html = `
            <div class="message user-message">
                <div class="sender">You</div>
                <div class="content">${escapeHtml(message)}</div>
            </div>
        `;
        this.addMessage(html);
    }

    addAgentMessage(agent, message) {
        console.log(`Adding agent message from ${agent}:`, message);
        const html = `
            <div class="message agent-message">
                <div class="sender">${escapeHtml(agent)}</div>
                <div class="content">${escapeHtml(message)}</div>
            </div>
        `;
        this.addMessage(html);
    }

    addSystemMessage(message) {
        const html = `
            <div class="message system-message">
                <div class="content">${escapeHtml(message)}</div>
            </div>
        `;
        this.addMessage(html);
    }

    addThinkingMessage(agent, thought) {
        const messageId = Date.now();
        const html = `
            <div class="message thinking" data-agent="${escapeHtml(agent)}" data-thinking-id="${messageId}">
                <div class="sender">${escapeHtml(agent)} thinking:</div>
                <div class="content">${escapeHtml(thought)}</div>
                <div class="thinking-indicator">
                    <span></span><span></span><span></span>
                </div>
            </div>
        `;
        this.addMessage(html);

        // Remove previous thinking messages from this agent
        const oldMessages = this.chatBox.querySelectorAll(
            `.message.thinking[data-agent="${agent}"]:not([data-thinking-id="${messageId}"])`
        );
        oldMessages.forEach(msg => msg.remove());
    }

    addErrorMessage(message) {
        const html = `
            <div class="message error-message">
                <div class="content">${escapeHtml(message)}</div>
            </div>
        `;
        this.addMessage(html);
    }

    addMessage(html) {
        if (!this.chatBox) {
            console.error('Chat box element not found');
            return;
        }
        this.chatBox.insertAdjacentHTML('beforeend', html);
        this.scrollToBottom();
    }

    clearThinkingMessages() {
        const thinkingMessages = this.chatBox.querySelectorAll('.message.thinking');
        thinkingMessages.forEach(msg => msg.remove());
    }

    scrollToBottom() {
        this.chatBox.scrollTop = this.chatBox.scrollHeight;
    }
}