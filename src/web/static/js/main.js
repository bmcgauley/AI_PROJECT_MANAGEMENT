// WebSocket connection
let ws = null;
let activityPanelCollapsed = false;
let currentRequestId = null;
let agentActivities = {};

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
        case 'agent_activity':
            handleAgentActivity(message);
            break;
        case 'agent_handoff':
            handleAgentHandoff(message);
            break;
        case 'agent_thinking':
            handleAgentThinking(message);
            addThinkingMessageToChat(message.agent, message.thinking);
            break;
        case 'request_start':
            startNewRequest(message.request_id);
            break;
        case 'request_complete':
            finalizeRequest(message.request_id);
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
        
        // Clear previous agent activities when sending a new message
        clearAgentActivities();
        document.querySelector('.activity-placeholder').style.display = 'none';
    }
}

// Clear agent activities display
function clearAgentActivities() {
    agentActivities = {};
    const activityFeed = document.getElementById('agent-activity-feed');
    
    // Keep only the placeholder and remove all other children
    const placeholder = document.querySelector('.activity-placeholder');
    activityFeed.innerHTML = '';
    activityFeed.appendChild(placeholder);
}

// Start tracking a new request
function startNewRequest(requestId) {
    currentRequestId = requestId;
    
    // Reset agent activities for this new request
    agentActivities = {};
}

// Finalize a request
function finalizeRequest(requestId) {
    // Mark this request as complete
    if (requestId === currentRequestId) {
        // Don't add "Request processing complete" message
        // The agent's response should already be displayed
        console.log(`Request ${requestId} completed`);
        
        // Reset any thinking indicators or temporary UI elements if needed
        clearThinkingMessages();
    }
}

// Clear any thinking messages
function clearThinkingMessages() {
    const thinkingMessages = document.querySelectorAll('.message.thinking');
    thinkingMessages.forEach(msg => msg.remove());
}

// Handle agent activity updates
function handleAgentActivity(message) {
    const { agent, activity_type, timestamp, request_id } = message;
    
    if (request_id !== currentRequestId) return;
    
    if (!agentActivities[agent]) {
        agentActivities[agent] = {
            activities: []
        };
    }
    
    // Add new activity
    agentActivities[agent].activities.push({
        type: activity_type,
        time: timestamp,
        content: message.content || '',
        input: message.input || '',
        output: message.output || '',
        thinking: message.thinking || ''
    });
    
    // Update the display
    updateAgentActivityDisplay();
}

// Handle agent handoff event
function handleAgentHandoff(message) {
    const { from_agent, to_agent, request_id, input, thinking } = message;
    
    if (request_id !== currentRequestId) return;
    
    // Record handoff in both agents
    if (!agentActivities[from_agent]) {
        agentActivities[from_agent] = {
            activities: []
        };
    }
    
    if (!agentActivities[to_agent]) {
        agentActivities[to_agent] = {
            activities: []
        };
    }
    
    // Add handoff activity to sending agent
    agentActivities[from_agent].activities.push({
        type: 'handoff_out',
        time: new Date().toISOString(),
        to: to_agent,
        input: input,
        thinking: thinking || ''
    });
    
    // Add handoff activity to receiving agent
    agentActivities[to_agent].activities.push({
        type: 'handoff_in',
        time: new Date().toISOString(),
        from: from_agent,
        input: input
    });
    
    // Update the display
    updateAgentActivityDisplay();
}

// Handle agent thinking process
function handleAgentThinking(message) {
    const { agent, thinking, request_id } = message;
    
    if (request_id !== currentRequestId) return;
    
    if (!agentActivities[agent]) {
        agentActivities[agent] = {
            activities: []
        };
    }
    
    // Add thinking activity
    agentActivities[agent].activities.push({
        type: 'thinking',
        time: new Date().toISOString(),
        thinking: thinking
    });
    
    // Update the display
    updateAgentActivityDisplay();
}

// Add new function to handle agent thinking in chat
function addThinkingMessageToChat(agent, thinking) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message thinking';
    messageDiv.setAttribute('data-agent', agent);
    messageDiv.setAttribute('data-thinking-id', Date.now());
    
    const agentName = document.createElement('strong');
    agentName.textContent = agent + ' thinking: ';
    
    const thinkingContent = document.createElement('span');
    thinkingContent.className = 'thinking-content';
    thinkingContent.textContent = thinking;
    
    const thinkingIndicator = document.createElement('div');
    thinkingIndicator.className = 'thinking-indicator';
    for (let i = 0; i < 3; i++) {
        const dot = document.createElement('span');
        thinkingIndicator.appendChild(dot);
    }
    
    messageDiv.appendChild(agentName);
    messageDiv.appendChild(thinkingContent);
    messageDiv.appendChild(thinkingIndicator);
    
    const chatMessages = document.getElementById('chat-messages');
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    // Remove any previous thinking messages from this agent
    const oldThinkingMessages = document.querySelectorAll(`.message.thinking[data-agent="${agent}"]:not([data-thinking-id="${messageDiv.getAttribute('data-thinking-id')}"])`);
    oldThinkingMessages.forEach(msg => msg.remove());
}

// Update the agent activity display
function updateAgentActivityDisplay() {
    const activityFeed = document.getElementById('agent-activity-feed');
    
    // Clear existing content except for the placeholder
    const placeholder = document.querySelector('.activity-placeholder');
    placeholder.style.display = 'none';
    activityFeed.innerHTML = '';
    
    // Sort agents by their first activity time
    const sortedAgents = Object.keys(agentActivities).sort((a, b) => {
        const aFirstTime = agentActivities[a].activities[0]?.time || '';
        const bFirstTime = agentActivities[b].activities[0]?.time || '';
        return aFirstTime.localeCompare(bFirstTime);
    });
    
    // Display each agent's activities
    sortedAgents.forEach(agent => {
        const agentData = agentActivities[agent];
        
        // Create agent section
        const agentSection = document.createElement('div');
        agentSection.className = 'agent-activity';
        
        // Agent header
        const agentHeader = document.createElement('div');
        agentHeader.className = 'agent-activity-header collapsible';
        agentHeader.innerHTML = `
            <span class="agent-name">${escapeHtml(agent)}</span>
            <span class="agent-activity-time">${agentData.activities.length} activities</span>
        `;
        agentHeader.onclick = () => {
            const content = agentHeader.nextElementSibling;
            content.classList.toggle('active');
        };
        agentSection.appendChild(agentHeader);
        
        // Agent content container
        const contentContainer = document.createElement('div');
        contentContainer.className = 'collapsible-content active';
        
        // Add each activity
        agentData.activities.forEach((activity, index) => {
            const activityEl = createActivityElement(agent, activity, index);
            contentContainer.appendChild(activityEl);
        });
        
        agentSection.appendChild(contentContainer);
        activityFeed.appendChild(agentSection);
    });
}

// Create an element for a single activity
function createActivityElement(agent, activity, index) {
    const activityEl = document.createElement('div');
    activityEl.className = 'agent-activity-content';
    
    // Format timestamp
    const time = new Date(activity.time);
    const formattedTime = time.toLocaleTimeString();
    
    let content = '';
    
    switch (activity.type) {
        case 'handoff_in':
            content = `
                <div class="agent-activity-time">${formattedTime}</div>
                <div>Received request from <strong>${escapeHtml(activity.from)}</strong></div>
                
                <div class="agent-activity-label">Input received:</div>
                <div class="agent-activity-input">${escapeHtml(activity.input)}</div>
            `;
            break;
            
        case 'handoff_out':
            content = `
                <div class="agent-activity-time">${formattedTime}</div>
                <div>Sending request to <strong>${escapeHtml(activity.to)}</strong></div>
                
                ${activity.thinking ? 
                    `<div class="agent-activity-label">Reasoning:</div>
                    <div class="agent-activity-input">${escapeHtml(activity.thinking)}</div>` : ''}
                
                <div class="agent-activity-label">Output sent:</div>
                <div class="agent-activity-output">${escapeHtml(activity.input)}</div>
            `;
            break;
            
        case 'thinking':
            content = `
                <div class="agent-activity-time">${formattedTime}</div>
                <div>Thinking process:</div>
                <div class="agent-activity-input">${escapeHtml(activity.thinking)}</div>
            `;
            break;
            
        case 'processing':
            content = `
                <div class="agent-activity-time">${formattedTime}</div>
                <div>Processing request:</div>
                
                ${activity.thinking ? 
                    `<div class="agent-activity-label">Reasoning:</div>
                    <div class="agent-activity-input">${escapeHtml(activity.thinking)}</div>` : ''}
                
                <div class="agent-activity-label">Input:</div>
                <div class="agent-activity-input">${escapeHtml(activity.input)}</div>
                
                <div class="agent-activity-label">Output:</div>
                <div class="agent-activity-output">${escapeHtml(activity.output)}</div>
            `;
            break;
            
        default:
            content = `
                <div class="agent-activity-time">${formattedTime}</div>
                <div>${escapeHtml(activity.content || 'Activity')}</div>
                
                ${activity.input ? 
                    `<div class="agent-activity-label">Input:</div>
                    <div class="agent-activity-input">${escapeHtml(activity.input)}</div>` : ''}
                
                ${activity.output ? 
                    `<div class="agent-activity-label">Output:</div>
                    <div class="agent-activity-output">${escapeHtml(activity.output)}</div>` : ''}
                
                ${activity.thinking ? 
                    `<div class="agent-activity-label">Reasoning:</div>
                    <div class="agent-activity-input">${escapeHtml(activity.thinking)}</div>` : ''}
            `;
    }
    
    activityEl.innerHTML = content;
    return activityEl;
}

// Toggle the agent activity panel visibility
function toggleActivityPanel() {
    const container = document.querySelector('.agent-activity-container');
    const button = document.getElementById('toggle-activity');
    
    activityPanelCollapsed = !activityPanelCollapsed;
    
    if (activityPanelCollapsed) {
        container.classList.add('collapsed');
        button.textContent = 'Show';
    } else {
        container.classList.remove('collapsed');
        button.textContent = 'Hide';
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

// Add agent message to chat with markdown support
function addAgentMessage(agent, message) {
    try {
        // Use marked.js to parse markdown
        const parsedContent = marked.parse(message);
        
        const html = `
            <div class="message agent-message">
                <div class="sender">${escapeHtml(agent)}</div>
                <div class="content markdown-content">${parsedContent}</div>
            </div>
        `;
        addMessage(html);
    } catch (e) {
        // Fallback to plain text if markdown parsing fails
        const html = `
            <div class="message agent-message">
                <div class="sender">${escapeHtml(agent)}</div>
                <div class="content">${escapeHtml(message)}</div>
            </div>
        `;
        addMessage(html);
        console.error('Error parsing markdown:', e);
    }
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
} )
    });