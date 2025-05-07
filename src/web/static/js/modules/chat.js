// Chat UI module
import { escapeHtml } from './utils.js';

export class ChatUI {
    constructor(chatBoxId = 'chat-box') {
        this.chatBoxId = chatBoxId;
        this.chatBox = null;
        this.messageQueue = [];
        this.initialized = false;
        
        // Try to find the element immediately
        this.chatBox = document.getElementById(this.chatBoxId);
        
        // If not found, we'll retry when adding messages
        if (!this.chatBox) {
            console.warn(`Chat box element with ID '${chatBoxId}' not found initially. Will retry later.`);
        } else {
            this.initialized = true;
        }
    }

    // Try to initialize if we haven't already
    ensureInitialized() {
        if (!this.initialized) {
            this.chatBox = document.getElementById(this.chatBoxId);
            if (this.chatBox) {
                this.initialized = true;
                // Process any queued messages
                this.processMessageQueue();
                return true;
            }
            return false;
        }
        return true;
    }

    // Process any messages that were queued while waiting for element
    processMessageQueue() {
        if (this.messageQueue.length > 0) {
            console.log(`Processing ${this.messageQueue.length} queued messages`);
            this.messageQueue.forEach(html => {
                this.chatBox.insertAdjacentHTML('beforeend', html);
            });
            this.messageQueue = [];
            this.scrollToBottom();
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

        if (this.chatBox) {
            // Remove previous thinking messages from this agent
            const oldMessages = this.chatBox.querySelectorAll(
                `.message.thinking[data-agent="${agent}"]:not([data-thinking-id="${messageId}"])`
            );
            oldMessages.forEach(msg => msg.remove());
        }
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
        // Try to find the element if we haven't already
        if (!this.ensureInitialized()) {
            // If still not found, queue the message for later
            this.messageQueue.push(html);
            console.warn(`Chat box element not found, queuing message`);
            return;
        }

        this.chatBox.insertAdjacentHTML('beforeend', html);
        this.scrollToBottom();
    }

    clearThinkingMessages() {
        if (!this.ensureInitialized()) return;
        
        const thinkingMessages = this.chatBox.querySelectorAll('.message.thinking');
        thinkingMessages.forEach(msg => msg.remove());
    }

    scrollToBottom() {
        if (this.chatBox) {
            this.chatBox.scrollTop = this.chatBox.scrollHeight;
        }
    }
}