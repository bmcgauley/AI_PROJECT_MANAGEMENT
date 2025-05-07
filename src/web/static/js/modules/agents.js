// Agents management module
import { escapeHtml } from './utils.js';

export class AgentManager {
    constructor() {
        this.agentList = document.getElementById('agent-list');
        this.agentActivities = {};
        this.currentRequestId = null;
    }

    async updateAgentStatuses() {
        try {
            const response = await fetch('/api/agents');
            const data = await response.json();

            this.agentList.innerHTML = '';

            if (data.agents?.length > 0) {
                data.agents.forEach(agent => {
                    this.agentList.innerHTML += `
                        <div class="agent-card ${agent.status === 'active' ? 'active' : ''}">
                            <h3>${escapeHtml(agent.name)}</h3>
                            <span class="status ${agent.status}">${escapeHtml(agent.status)}</span>
                        </div>
                    `;
                });
            } else {
                this.agentList.innerHTML = '<div class="system-message">No agents available</div>';
            }
        } catch (error) {
            console.error('Error updating agent statuses:', error);
            this.agentList.innerHTML = '<div class="system-message">Error loading agents</div>';
        }
    }

    updateAgentStatus(agentName, status) {
        const cards = document.querySelectorAll('.agent-card');
        cards.forEach(card => {
            if (card.querySelector('h3').textContent === agentName) {
                card.className = `agent-card ${status === 'active' ? 'active' : ''}`;
                card.querySelector('.status').className = `status ${status}`;
                card.querySelector('.status').textContent = status;
            }
        });
    }

    handleAgentActivity(message) {
        const { agent, activity_type, timestamp, request_id } = message;
        if (request_id !== this.currentRequestId) return;

        if (!this.agentActivities[agent]) {
            this.agentActivities[agent] = { activities: [] };
        }

        this.agentActivities[agent].activities.push({
            type: activity_type,
            time: timestamp,
            content: message.content || '',
            input: message.input || '',
            output: message.output || '',
            thinking: message.thinking || ''
        });

        this.updateActivityDisplay();
    }

    clearAgentActivities() {
        this.agentActivities = {};
        const activityFeed = document.getElementById('agent-activity-feed');
        const placeholder = document.querySelector('.activity-placeholder');
        activityFeed.innerHTML = '';
        activityFeed.appendChild(placeholder);
    }

    startNewRequest(requestId) {
        this.currentRequestId = requestId;
        this.agentActivities = {};
    }

    updateActivityDisplay() {
        const activityFeed = document.getElementById('agent-activity-feed');
        if (!activityFeed) return;

        const placeholder = activityFeed.querySelector('.activity-placeholder');
        if (placeholder) {
            placeholder.style.display = 'none';
        }
        
        activityFeed.innerHTML = '';

        const sortedAgents = Object.keys(this.agentActivities).sort((a, b) => {
            const aFirstTime = this.agentActivities[a].activities[0]?.time || '';
            const bFirstTime = this.agentActivities[b].activities[0]?.time || '';
            return aFirstTime.localeCompare(bFirstTime);
        });

        sortedAgents.forEach(agent => {
            const agentSection = this.createAgentActivitySection(agent);
            activityFeed.appendChild(agentSection);
        });
    }

    createAgentActivitySection(agent) {
        const agentData = this.agentActivities[agent];
        const section = document.createElement('div');
        section.className = 'agent-activity';

        const header = document.createElement('div');
        header.className = 'agent-activity-header collapsible';
        header.innerHTML = `
            <span class="agent-name">${escapeHtml(agent)}</span>
            <span class="agent-activity-time">${agentData.activities.length} activities</span>
        `;
        header.onclick = () => {
            const content = header.nextElementSibling;
            content.classList.toggle('active');
        };

        const content = document.createElement('div');
        content.className = 'collapsible-content active';
        agentData.activities.forEach((activity, index) => {
            content.appendChild(this.createActivityElement(agent, activity, index));
        });

        section.appendChild(header);
        section.appendChild(content);
        return section;
    }

    createActivityElement(agent, activity, index) {
        const el = document.createElement('div');
        el.className = 'agent-activity-content';

        const time = new Date(activity.time);
        const formattedTime = time.toLocaleTimeString();

        let content = '';
        switch (activity.type) {
            case 'handoff_in':
                content = this.createHandoffInContent(activity, formattedTime);
                break;
            case 'handoff_out':
                content = this.createHandoffOutContent(activity, formattedTime);
                break;
            case 'thinking':
                content = this.createThinkingContent(activity, formattedTime);
                break;
            case 'processing':
                content = this.createProcessingContent(activity, formattedTime);
                break;
            default:
                content = this.createDefaultContent(activity, formattedTime);
        }

        el.innerHTML = content;
        return el;
    }

    createHandoffInContent(activity, time) {
        return `
            <div class="agent-activity-time">${time}</div>
            <div>Received request from <strong>${escapeHtml(activity.from)}</strong></div>
            <div class="agent-activity-label">Input received:</div>
            <div class="agent-activity-input">${escapeHtml(activity.input)}</div>
        `;
    }

    createHandoffOutContent(activity, time) {
        return `
            <div class="agent-activity-time">${time}</div>
            <div>Sending request to <strong>${escapeHtml(activity.to)}</strong></div>
            ${activity.thinking ? `
                <div class="agent-activity-label">Reasoning:</div>
                <div class="agent-activity-input">${escapeHtml(activity.thinking)}</div>
            ` : ''}
            <div class="agent-activity-label">Output sent:</div>
            <div class="agent-activity-output">${escapeHtml(activity.input)}</div>
        `;
    }

    createThinkingContent(activity, time) {
        return `
            <div class="agent-activity-time">${time}</div>
            <div>Thinking process:</div>
            <div class="agent-activity-input">${escapeHtml(activity.thinking)}</div>
        `;
    }

    createProcessingContent(activity, time) {
        return `
            <div class="agent-activity-time">${time}</div>
            <div>Processing request:</div>
            ${activity.thinking ? `
                <div class="agent-activity-label">Reasoning:</div>
                <div class="agent-activity-input">${escapeHtml(activity.thinking)}</div>
            ` : ''}
            <div class="agent-activity-label">Input:</div>
            <div class="agent-activity-input">${escapeHtml(activity.input)}</div>
            <div class="agent-activity-label">Output:</div>
            <div class="agent-activity-output">${escapeHtml(activity.output)}</div>
        `;
    }

    createDefaultContent(activity, time) {
        return `
            <div class="agent-activity-time">${time}</div>
            <div>${escapeHtml(activity.content || 'Activity')}</div>
            ${activity.input ? `
                <div class="agent-activity-label">Input:</div>
                <div class="agent-activity-input">${escapeHtml(activity.input)}</div>
            ` : ''}
            ${activity.output ? `
                <div class="agent-activity-label">Output:</div>
                <div class="agent-activity-output">${escapeHtml(activity.output)}</div>
            ` : ''}
            ${activity.thinking ? `
                <div class="agent-activity-label">Reasoning:</div>
                <div class="agent-activity-input">${escapeHtml(activity.thinking)}</div>
            ` : ''}
        `;
    }
}