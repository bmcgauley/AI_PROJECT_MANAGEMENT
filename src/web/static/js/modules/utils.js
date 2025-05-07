// Utility functions
export function escapeHtml(unsafe) {
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

// Toggle visibility of sections
export function showSection(sectionId) {
    document.querySelectorAll('.section').forEach(section => {
        section.classList.remove('active');
    });
    document.getElementById(sectionId)?.classList.add('active');
}

// Toggle activity panel
export function toggleActivityPanel() {
    const container = document.querySelector('.agent-activity-container');
    const button = document.getElementById('toggle-activity');
    const isCollapsed = container.classList.toggle('collapsed');
    button.textContent = isCollapsed ? 'Show' : 'Hide';
}

// Parse agent response content
export function parseAgentResponse(response) {
    if (!response) return { content: '', agentName: 'System' };

    let content = '';
    let agentName = 'Project Manager';

    // Try to extract agent name
    if (typeof response.agent_name === 'string') {
        agentName = response.agent_name;
    } else if (typeof response.processed_by === 'string') {
        agentName = response.processed_by;
    }

    // Extract content based on common patterns
    if (typeof response === 'string') {
        content = cleanAgentDialogue(response);
    } else if (typeof response.content === 'string') {
        content = cleanAgentDialogue(response.content);
    } else if (response.response && typeof response.response === 'string') {
        content = cleanAgentDialogue(response.response);
    } else if (response.content && typeof response.content === 'object') {
        content = cleanAgentDialogue(response.content.text || JSON.stringify(response.content));
    } else {
        try {
            content = cleanAgentDialogue(JSON.stringify(response));
        } catch (e) {
            content = "Received response in unknown format";
        }
    }

    return { content, agentName };
}

// Helper function to clean agent dialogue markers
function cleanAgentDialogue(text) {
    if (typeof text !== 'string') return '';
    
    const lines = text.split('\n');
    let finalResponse = [];
    let inAgentDialog = false;

    for (let line of lines) {
        line = line.trim();
        if (!line) continue;

        // Skip agent dialogue markers and metadata
        if (line.match(/^(Human|User|AI|Machine|System|Assistant):/)) {
            continue;
        }

        // Skip agent thinking/processing markers
        if (line.includes('Agent thinking:') || 
            line.includes('Processing request:') ||
            line.includes('Adding agent message from')) {
            continue;
        }

        // Add the line if it's not part of agent dialogue
        finalResponse.push(line);
    }

    return finalResponse.join('\n').trim();
}