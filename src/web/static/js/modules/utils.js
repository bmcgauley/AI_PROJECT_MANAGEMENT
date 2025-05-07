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

    // Filter out agent dialogue markers and internal communication
    if (typeof content === 'string') {
        content = extractFinalUserResponse(content);
    }

    return { content, agentName };
}

// Helper function to extract only the final user-directed response from agent dialogue
function extractFinalUserResponse(text) {
    if (typeof text !== 'string') return '';
    
    // Split into lines and process
    const lines = text.split('\n');
    let finalResponse = '';
    let inAgentDialog = false;
    let currentSpeaker = '';
    let lastAIResponse = '';
    
    // First pass: identify conversation structure and extract final AI response
    for (let i = 0; i < lines.length; i++) {
        let line = lines[i].trim();
        
        // Skip empty lines
        if (!line) continue;
        
        // Check for speaker identifiers
        const humanMatch = line.match(/^(Human|User):\s*(.*)/i);
        const aiMatch = line.match(/^(AI|Machine|System|Project Manager|Assistant):\s*(.*)/i);
        
        if (humanMatch) {
            currentSpeaker = 'Human';
            inAgentDialog = true;
            continue;
        } else if (aiMatch) {
            currentSpeaker = aiMatch[1];
            lastAIResponse = aiMatch[2] || '';
            inAgentDialog = true;
            continue;
        } else if (currentSpeaker === 'AI' || 
                  currentSpeaker === 'Machine' || 
                  currentSpeaker === 'System' || 
                  currentSpeaker === 'Project Manager' ||
                  currentSpeaker === 'Assistant') {
            // Continue capturing AI response
            lastAIResponse += ' ' + line;
        }
    }
    
    // If we found a structured conversation with AI response, use that
    if (lastAIResponse) {
        return lastAIResponse.trim();
    }
    
    // Second pass: if no structured dialogue found, clean up the text
    // and remove any obvious agent communication markers
    let cleanedLines = [];
    let skipLine = false;
    
    for (let line of lines) {
        line = line.trim();
        if (!line) continue;
        
        // Skip lines with obvious agent communication markers
        if (line.includes('Adding agent message from') || 
            line.includes('Agent thinking:') || 
            line.includes('Processing request:') ||
            line.match(/^(Human|User|AI|Machine|System|Assistant|Project Manager):/)) {
            skipLine = true;
            continue;
        }
        
        // Include this line if it's not part of agent dialogue
        if (!skipLine) {
            cleanedLines.push(line);
        }
        skipLine = false;
    }
    
    finalResponse = cleanedLines.join('\n');
    return finalResponse.trim();
}