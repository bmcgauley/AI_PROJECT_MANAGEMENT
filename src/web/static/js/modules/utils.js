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
        content = response;
    } else if (typeof response.content === 'string') {
        content = response.content;
    } else if (response.response && typeof response.response === 'string') {
        content = response.response;
    } else if (response.content && typeof response.content === 'object') {
        content = response.content.text || JSON.stringify(response.content);
    } else {
        try {
            content = JSON.stringify(response);
        } catch (e) {
            content = "Received response in unknown format";
        }
    }

    // Handle scripted conversation format
    if (typeof content === 'string' && 
        (content.includes('AI:') || content.includes('System:') || 
         content.includes('Human:') || content.includes('Project Manager:'))) {
        
        const lines = content.split('\n');
        let lastResponse = '';
        let currentSpeaker = '';
        let responseBuffer = '';

        for (let line of lines) {
            line = line.trim();
            if (line.startsWith('Project Manager:') || 
                line.startsWith('System:') || 
                line.startsWith('Human:')) {
                
                if (currentSpeaker === 'Project Manager' && responseBuffer) {
                    lastResponse = responseBuffer;
                }

                if (line.startsWith('Project Manager:')) {
                    currentSpeaker = 'Project Manager';
                    responseBuffer = line.substring('Project Manager:'.length).trim();
                } else {
                    currentSpeaker = line.startsWith('System:') ? 'System' : 'Human';
                    responseBuffer = '';
                }
            } else if (currentSpeaker === 'Project Manager') {
                responseBuffer += ' ' + line;
            }
        }

        if (currentSpeaker === 'Project Manager' && responseBuffer) {
            lastResponse = responseBuffer;
        }

        if (lastResponse) {
            content = lastResponse;
        }
    }

    return { content, agentName };
}