// WebSocket connection
let ws = null;

// Initialize WebSocket connection
function initWebSocket() {
    ws = new WebSocket(`ws://${window.location.host}/ws`);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
        addSystemMessage('Connected to AI Project Management System');
        updateAgentStatuses();
    };

    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected');
        addSystemMessage('Disconnected from server. Attempting to reconnect...');
        setTimeout(initWebSocket, 2000);
    };
}

// Handle incoming WebSocket messages
function handleWebSocketMessage(message) {
    switch (message.type) {
        case 'response':
            handleAgentResponse(message.content);
            break;
        case 'agent_update':
            updateAgentCard(message.agent, message.status);
            break;
        default:
            console.log('Unknown message type:', message.type);
    }
}

// Send message to server
function sendMessage() {
    const input = document.getElementById('user-input');
    const message = input.value.trim();
    
    if (message && ws) {
        ws.send(JSON.stringify({
            type: 'request',
            content: message
        }));
        
        addUserMessage(message);
        input.value = '';
    }
}

// Handle agent response
function handleAgentResponse(response) {
    if (response.status === 'error') {
        addSystemMessage(`Error: ${response.error}`);
        return;
    }

    if (response.status === 'clarification_needed') {
        const questions = response.clarification_questions.join('\n');
        addAgentMessage('Chat Coordinator', `I need some clarification:\n${questions}`);
        return;
    }

    addAgentMessage(response.processed_by, response.response);
}

// Add message to chat
function addMessage(html) {
    const messages = document.getElementById('chat-messages');
    messages.innerHTML += html;
    messages.scrollTop = messages.scrollHeight;
}

// Add user message to chat
function addUserMessage(message) {
    const html = `
        <div class="message user-message">
            <div class="sender">You</div>
            <div class="content">${escapeHtml(message)}</div>
        </div>
    `;
    addMessage(html);
}

// Add agent message to chat
function addAgentMessage(agent, message) {
    const html = `
        <div class="message agent-message">
            <div class="sender">${escapeHtml(agent)}</div>
            <div class="content">${escapeHtml(message)}</div>
        </div>
    `;
    addMessage(html);
}

// Add system message to chat
function addSystemMessage(message) {
    const html = `
        <div class="message system-message">
            <div class="content">${escapeHtml(message)}</div>
        </div>
    `;
    addMessage(html);
}

// Create new project
async function createProject(event) {
    event.preventDefault();
    
    const projectData = {
        name: document.getElementById('project-name').value,
        type: document.getElementById('project-type').value,
        techStack: Array.from(document.getElementById('tech-stack').selectedOptions).map(opt => opt.value)
    };
    
    try {
        const response = await fetch('/api/project', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(projectData)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            addSystemMessage('Project created successfully');
            showSection('dashboard');
        } else {
            addSystemMessage(`Error creating project: ${result.error}`);
        }
    } catch (error) {
        addSystemMessage(`Error: ${error.message}`);
    }
}

// Update agent statuses
async function updateAgentStatuses() {
    try {
        const response = await fetch('/api/agents');
        const data = await response.json();
        
        const agentList = document.getElementById('agent-list');
        agentList.innerHTML = '';
        
        data.agents.forEach(agent => {
            agentList.innerHTML += `
                <div class="agent-card ${agent.status === 'active' ? 'active' : ''}">
                    <h3>${escapeHtml(agent.name)}</h3>
                    <span class="status ${agent.status}">${escapeHtml(agent.status)}</span>
                </div>
            `;
        });
    } catch (error) {
        console.error('Error updating agent statuses:', error);
    }
}

// Update single agent card
function updateAgentCard(agentName, status) {
    const cards = document.querySelectorAll('.agent-card');
    cards.forEach(card => {
        if (card.querySelector('h3').textContent === agentName) {
            card.className = `agent-card ${status === 'active' ? 'active' : ''}`;
            card.querySelector('.status').className = `status ${status}`;
            card.querySelector('.status').textContent = status;
        }
    });
}

// Show section
function showSection(sectionId) {
    document.querySelectorAll('.section').forEach(section => {
        section.classList.remove('active');
    });
    document.getElementById(sectionId).classList.add('active');
}

// Escape HTML to prevent XSS
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
    
    // Handle Enter key in chat input
    document.getElementById('user-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
});