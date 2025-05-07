// Main application module
import { ChatUI } from './chat.js';
import { AgentManager } from './agents.js';
import { ResponseHandler } from './response-handler.js';
import { initWebSocket, sendMessage } from './websocket.js';

export class App {
    constructor() {
        // Initialize core components
        this.chatUI = new ChatUI('chat-box');
        this.agentManager = new AgentManager();
        this.responseHandler = new ResponseHandler(this.chatUI, this.agentManager);
        
        // Bind methods
        this.handleSendMessage = this.handleSendMessage.bind(this);
        this.setupEventListeners = this.setupEventListeners.bind(this);
    }

    init() {
        // Skip initialization on modern interface
        if (window.isModernInterface === true) {
            console.log('Modern interface detected, skipping app initialization');
            return;
        }

        // Initialize WebSocket with handlers
        initWebSocket({
            onConnect: () => {
                this.chatUI.addSystemMessage('Connected to AI Project Management System');
                this.agentManager.updateAgentStatuses();
            },
            onMessage: (message) => this.responseHandler.handleWebSocketMessage(message),
            onDisconnect: () => {
                this.chatUI.addSystemMessage('Disconnected from server. Attempting to reconnect...');
            },
            onError: (error) => {
                console.error('WebSocket error:', error);
                this.chatUI.addErrorMessage('Connection error occurred');
            }
        });

        this.setupEventListeners();
    }

    setupEventListeners() {
        // Handle Enter key in chat input
        const userInput = document.getElementById('user-input');
        if (userInput) {
            userInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault(); // Prevent newline in textarea
                    this.handleSendMessage();
                }
            });
        }

        // Add click handler to send button
        const sendButton = document.getElementById('send-button');
        if (sendButton) {
            sendButton.addEventListener('click', this.handleSendMessage);
        }
    }

    handleSendMessage() {
        const userInput = document.getElementById('user-input');
        const message = userInput.value.trim();

        if (message) {
            const success = sendMessage({
                type: 'request',
                content: message
            });

            if (success) {
                this.chatUI.addUserMessage(message);
                userInput.value = '';
                this.agentManager.clearAgentActivities();
                document.querySelector('.activity-placeholder').style.display = 'none';
            }
        }
    }
}