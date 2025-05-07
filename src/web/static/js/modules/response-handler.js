// Response handler module
import { parseAgentResponse } from './utils.js';

export class ResponseHandler {
    constructor(chatUI, agentManager) {
        this.chatUI = chatUI;
        this.agentManager = agentManager;
    }

    handleResponse(response) {
        console.log('Received response:', response);

        // Handle error responses
        if (response.error || response.status === 'error') {
            this.chatUI.addSystemMessage(`Error: ${response.error || 'Unknown error occurred'}`);
            return;
        }

        // Handle clarification requests
        if (response.status === 'clarification_needed' && Array.isArray(response.clarification_questions)) {
            const questions = response.clarification_questions.join('\n');
            this.chatUI.addAgentMessage('Chat Coordinator', `I need some clarification:\n${questions}`);
            return;
        }

        // Parse and add the response
        const { content, agentName } = parseAgentResponse(response);
        if (content) {
            this.chatUI.addAgentMessage(agentName, content);
        }
    }

    handleWebSocketMessage(message) {
        switch (message.type) {
            case 'response':
                this.handleResponse(message.content);
                break;
                
            case 'agent_update':
                this.agentManager.updateAgentStatus(message.agent, message.status);
                break;
                
            case 'agent_activity':
                this.agentManager.handleAgentActivity(message);
                break;
                
            case 'agent_thinking':
                this.chatUI.addThinkingMessage(message.agent, message.thinking);
                break;
                
            case 'request_start':
                this.agentManager.startNewRequest(message.request_id);
                break;
                
            case 'request_complete':
                this.chatUI.clearThinkingMessages();
                break;
                
            case 'error':
                this.chatUI.addErrorMessage(message.message);
                break;
                
            default:
                console.log('Unknown message type:', message.type);
        }
    }
}