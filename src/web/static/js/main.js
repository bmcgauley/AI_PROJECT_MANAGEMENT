// WebSocket connection
let ws = null;
let activityPanelCollapsed = false;
let currentRequestId = null;
let agentActivities = {};

// Initialize WebSocket connection
function initWebSocket() {
    // Skip initialization on modern interface
    if (window.isModernInterface === true) {
        console.log('Modern interface detected, skipping main.js initialization');
        return;
    }

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
    console.log('Received response:', response);

    // Safety check for null or undefined response
    if (!response) {
        addSystemMessage('Received empty response from server');
        return;
    }

    // Handle error responses
    if (response.error || response.status === 'error') {
        addSystemMessage(`Error: ${response.error || 'Unknown error occurred'}`);
        return;
    }

    // Handle clarification requests
    if (response.status === 'clarification_needed' && Array.isArray(response.clarification_questions)) {
        const questions = response.clarification_questions.join('\n');
        addAgentMessage('Chat Coordinator', `I need some clarification:\n${questions}`);
        return;
    }

    // Extract content based on various possible response formats
    let content = '';
    let agentName = 'Project Manager';

    // Try to extract agent name
    if (typeof response.agent_name === 'string') {
        agentName = response.agent_name;
    } else if (typeof response.processed_by === 'string') {
        agentName = response.processed_by;
    }

    // Try to extract content based on common patterns
    if (typeof response === 'string') {
        // Direct string response
        content = response;
    } else if (typeof response.content === 'string') {
        // Object with content property as string
        content = response.content;
    } else if (response.response && typeof response.response === 'string') {
        // Object with response property
        content = response.response;
    } else if (response.content && typeof response.content === 'object') {
        // Content is an object, try to extract text property
        content = response.content.text || JSON.stringify(response.content);
    } else {
        // Fallback: stringify the whole response
        try {
            content = JSON.stringify(response);
        } catch (e) {
            content = "Received response in unknown format";
        }
    }

    // Handle case where content contains a conversation script
    if (typeof content === 'string' &&
        (content.includes('System:') || content.includes('Human:') || content.includes('Project Manager:'))) {

        console.log('Detected scripted conversation format, attempting to extract relevant response');

        // Extract only the Project Manager's last response
        const lines = content.split('\n');
        let lastResponse = '';
        let currentSpeaker = '';
        let responseBuffer = '';

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();

            // Check for speaker changes
            if (line.startsWith('Project Manager:') || line.startsWith('System:') || line.startsWith('Human:')) {
                // If we were collecting a Project Manager response, store it
                if (currentSpeaker === 'Project Manager' && responseBuffer) {
                    lastResponse = responseBuffer;
                }

                // Start a new speaker section
                if (line.startsWith('Project Manager:')) {
                    currentSpeaker = 'Project Manager';
                    responseBuffer = line.substring('Project Manager:'.length).trim();
                } else if (line.startsWith('System:')) {
                    currentSpeaker = 'System';
                    responseBuffer = '';
                } else if (line.startsWith('Human:')) {
                    currentSpeaker = 'Human';
                    responseBuffer = '';
                }
            } else if (currentSpeaker === 'Project Manager') {
                // Continue collecting Project Manager's response
                responseBuffer += ' ' + line;
            }
        }

        // If the last speaker was Project Manager, make sure we capture that response
        if (currentSpeaker === 'Project Manager' && responseBuffer) {
            lastResponse = responseBuffer;
        }

        // Use the extracted response if we found one
        if (lastResponse) {
            console.log('Extracted Project Manager response:', lastResponse);
            content = lastResponse;
        } else {
            console.log('Could not extract Project Manager response from scripted conversation');
        }
    }

    // Make sure content is a string to avoid errors with escapeHtml
    if (content === null || content === undefined) {
        content = "No response content available";
    } else if (typeof content !== 'string') {
        try {
            content = JSON.stringify(content);
        } catch (e) {
            content = "Non-string response cannot be displayed";
        }
    }

    // Add the message to the chat
    addAgentMessage(agentName, content);
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

// Add agent message to chat
function addAgentMessage(agent, message) {
    console.log(`Adding agent message from ${agent}:`, message);
    const html = `
        <div class="message agent-message">
            <div class="sender">${escapeHtml(agent)}</div>
            <div class="content">${escapeHtml(message)}</div>
        </div>
    `;
    addMessage(html);
}

// Add message to chat
function addMessage(html) {
    const chatBox = document.getElementById('chat-box');
    if (!chatBox) {
        console.error('Could not find chat-box element');
        return;
    }
    chatBox.innerHTML += html;
    chatBox.scrollTop = chatBox.scrollHeight;
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

        // Check if data.agents exists and is an array
        if (data.agents && Array.isArray(data.agents) && data.agents.length > 0) {
            data.agents.forEach(agent => {
                agentList.innerHTML += `
                    <div class="agent-card ${agent.status === 'active' ? 'active' : ''}">
                        <h3>${escapeHtml(agent.name)}</h3>
                        <span class="status ${agent.status}">${escapeHtml(agent.status)}</span>
                    </div>
                `;
            });
        } else {
            // No agents or invalid data structure, show a placeholder
            agentList.innerHTML = '<div class="system-message">No agents available or data format invalid</div>';
            console.log('Unexpected API response format:', data);
        }
    } catch (error) {
        console.error('Error updating agent statuses:', error);
        const agentList = document.getElementById('agent-list');
        agentList.innerHTML = '<div class="system-message">Error loading agents</div>';
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
    if (unsafe === null || unsafe === undefined) {
        return '';
    }
    return String(unsafe)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    // Skip initialization on modern interface
    if (window.isModernInterface === true) {
        console.log('Modern interface detected, skipping main.js initialization');
        return;
    }

    initWebSocket();

    // Handle Enter key in chat input
    const userInput = document.getElementById('user-input');
    if (userInput) {
        userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault(); // Prevent newline in textarea
                sendMessage();
            }
        });
    }

    // Add click handler to send button
    const sendButton = document.getElementById('send-button');
    if (sendButton) {
        sendButton.addEventListener('click', () => {
            sendMessage();
        });
    }
});
