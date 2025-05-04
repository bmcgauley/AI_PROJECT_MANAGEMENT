/**
 * Agent Network Visualization
 * 
 * This script creates a dynamic visualization of agent interactions as a network graph.
 * It shows the flow of requests between agents, their current status, and any errors.
 * 
 * Dependencies: D3.js v7+
 */

// Visualization state
let networkGraph = {
    nodes: [],
    links: []
};
let agentStates = {};
let simulation;
let currentRequestId = null;
let userNode = { id: 'User', type: 'user' };

// Error tracking
let errorState = {
    hasError: false,
    message: '',
    agent: null,
    time: null
};

// D3 selections
let svg, linkElements, nodeElements, textElements;

// DOM selections
const tooltip = document.getElementById('visualization-tooltip');
const statusPanel = document.getElementById('status-panel');
const requestStatusEl = document.getElementById('request-status');

// Initialize the visualization
document.addEventListener('DOMContentLoaded', () => {
    initVisualization();
});

/**
 * Initialize the visualization with a basic network structure
 */
function initVisualization() {
    const vizContainer = document.getElementById('agent-visualization');
    const width = vizContainer.clientWidth;
    const height = vizContainer.clientHeight;

    // Create SVG element
    svg = d3.select('#agent-visualization')
        .append('svg')
        .attr('class', 'agent-flow-svg')
        .attr('width', width)
        .attr('height', height);

    // Initialize the graph with just the user node
    networkGraph.nodes.push(userNode);
    
    // Initialize the force simulation
    simulation = d3.forceSimulation(networkGraph.nodes)
        .force('link', d3.forceLink(networkGraph.links).id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(30))
        .on('tick', ticked);
    
    // Create the initial visualization elements
    updateVisualization();
    
    // Subscribe to WebSocket events for visualization updates
    document.addEventListener('agentNetworkUpdate', handleAgentNetworkUpdate);
    
    // Set a window resize handler
    window.addEventListener('resize', () => {
        const width = vizContainer.clientWidth;
        const height = vizContainer.clientHeight;
        
        svg.attr('width', width)
            .attr('height', height);
            
        simulation.force('center', d3.forceCenter(width / 2, height / 2));
        simulation.alpha(0.3).restart();
    });
}

/**
 * Update the visualization based on the current networkGraph state
 */
function updateVisualization() {
    // Get the SVG dimensions
    const width = parseInt(svg.attr('width'));
    const height = parseInt(svg.attr('height'));

    // Create links
    linkElements = svg.selectAll('.agent-link')
        .data(networkGraph.links)
        .join(
            enter => enter.append('line')
                .attr('class', d => `agent-link ${d.status || ''}`)
                .attr('marker-end', 'url(#arrowhead)'),
            update => update
                .attr('class', d => `agent-link ${d.status || ''}`)
                .attr('marker-end', 'url(#arrowhead)'),
            exit => exit.remove()
        );

    // Create nodes
    nodeElements = svg.selectAll('.agent-node')
        .data(networkGraph.nodes)
        .join(
            enter => {
                const nodes = enter.append('g')
                    .attr('class', d => `agent-node ${d.status || 'idle'}`)
                    .attr('data-id', d => d.id)
                    .on('mouseover', showTooltip)
                    .on('mouseout', hideTooltip);
                
                nodes.append('circle')
                    .attr('r', d => d.type === 'user' ? 18 : 12);
                    
                return nodes;
            },
            update => update
                .attr('class', d => `agent-node ${d.status || 'idle'}`),
            exit => exit.remove()
        );

    // Create node text labels
    textElements = svg.selectAll('.node-text')
        .data(networkGraph.nodes)
        .join(
            enter => enter.append('text')
                .attr('class', 'node-text')
                .attr('dy', d => d.type === 'user' ? 30 : 25)
                .attr('text-anchor', 'middle')
                .text(d => d.id),
            update => update.text(d => d.id),
            exit => exit.remove()
        );

    // Restart the simulation
    simulation.nodes(networkGraph.nodes);
    simulation.force('link').links(networkGraph.links);
    simulation.alpha(0.3).restart();
}

/**
 * Handle the simulation tick event to update element positions
 */
function ticked() {
    // Update link positions
    linkElements
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

    // Update node positions
    nodeElements
        .attr('transform', d => `translate(${d.x},${d.y})`);

    // Update text positions
    textElements
        .attr('x', d => d.x)
        .attr('y', d => d.y);
}

/**
 * Show tooltip with node information
 */
function showTooltip(event, d) {
    if (d.type === 'user') {
        tooltip.innerHTML = `<h4>User</h4><p>The source of all requests</p>`;
    } else {
        let content = `<h4>${d.id}</h4>`;
        content += `<p class="status">Status: ${d.status || 'idle'}</p>`;
        
        if (d.thinking) {
            content += `<p>Currently thinking:</p>`;
            content += `<div class="thinking">${d.thinking}</div>`;
        }
        
        if (d.error) {
            content += `<p class="status" style="color: #dc3545;">Error: ${d.error}</p>`;
        }
        
        tooltip.innerHTML = content;
    }
    
    const x = event.pageX;
    const y = event.pageY - 100;  // Position above the cursor
    
    tooltip.style.left = `${x}px`;
    tooltip.style.top = `${y}px`;
    tooltip.classList.add('visible');
}

/**
 * Hide the tooltip
 */
function hideTooltip() {
    tooltip.classList.remove('visible');
}

/**
 * Handle agent network updates from WebSocket events
 */
function handleAgentNetworkUpdate(event) {
    const message = event.detail;
    
    switch (message.type) {
        case 'request_start':
            startNewRequest(message.request_id);
            break;
        case 'agent_update':
            updateAgentStatus(message.agent, message.status);
            break;
        case 'agent_handoff':
            handleAgentHandoff(message);
            break;
        case 'agent_thinking':
            handleAgentThinking(message);
            break;
        case 'agent_error':
            handleAgentError(message);
            break;
        case 'workflow_step':
            updateWorkflowStatus(message);
            break;
        case 'request_complete':
            finalizeRequest(message.request_id);
            break;
        default:
            console.log('Unhandled network update:', message.type);
    }
}

/**
 * Start tracking a new request
 */
function startNewRequest(requestId) {
    currentRequestId = requestId;
    errorState = { hasError: false, message: '', agent: null, time: null };
    statusPanel.innerHTML = '';
    statusPanel.classList.remove('error');
    
    // Reset the network to just the user node
    networkGraph.nodes = [userNode];
    networkGraph.links = [];
    agentStates = {};
    
    // Update the request status
    requestStatusEl.textContent = `Active request: ${requestId}`;
    
    // Update visualization
    updateVisualization();
}

/**
 * Update an agent's status
 */
function updateAgentStatus(agentName, status) {
    // Skip if not related to current request
    if (!currentRequestId) return;
    
    // Find or create the node
    let agentNode = networkGraph.nodes.find(n => n.id === agentName);
    
    if (!agentNode) {
        agentNode = { id: agentName, status: status };
        networkGraph.nodes.push(agentNode);
        
        // Add a link from the user to this agent if it's the first connection
        const existingLink = networkGraph.links.find(l => l.target === agentName);
        
        if (!existingLink) {
            networkGraph.links.push({
                source: 'User',
                target: agentName,
                status: 'active'
            });
        }
    } else {
        agentNode.status = status;
    }
    
    // Store the state
    agentStates[agentName] = { status };
    
    // Apply a pulse animation to the node when becoming active
    if (status === 'active') {
        // First reset any active links
        networkGraph.links.forEach(link => {
            if (link.target === agentName) {
                link.status = 'active';
            } else {
                link.status = '';
            }
        });
        
        setTimeout(() => {
            const nodeElement = document.querySelector(`.agent-node[data-id="${agentName}"] circle`);
            if (nodeElement) {
                nodeElement.classList.add('handoff-animation');
                setTimeout(() => nodeElement.classList.remove('handoff-animation'), 1000);
            }
        }, 50);
    }
    
    // Update the visualization
    updateVisualization();
}

/**
 * Handle an agent handoff event
 */
function handleAgentHandoff(message) {
    const { from_agent, to_agent, request_id, thinking } = message;
    
    // Skip if not related to current request
    if (request_id !== currentRequestId) return;
    
    // Ensure both agents exist in the network
    let fromNode = networkGraph.nodes.find(n => n.id === from_agent);
    if (!fromNode) {
        fromNode = { id: from_agent, status: 'idle' };
        networkGraph.nodes.push(fromNode);
    }
    
    let toNode = networkGraph.nodes.find(n => n.id === to_agent);
    if (!toNode) {
        toNode = { id: to_agent, status: 'assigned' };
        networkGraph.nodes.push(toNode);
    }
    
    // Update states
    fromNode.status = 'idle';
    toNode.status = 'assigned';
    
    if (thinking) {
        fromNode.thinking = thinking;
    }
    
    // Create or update the link between agents
    let link = networkGraph.links.find(l => 
        l.source === from_agent && l.target === to_agent);
        
    if (!link) {
        link = {
            source: from_agent,
            target: to_agent,
            status: 'active'
        };
        networkGraph.links.push(link);
    } else {
        link.status = 'active';
    }
    
    // Update all other links to be inactive
    networkGraph.links.forEach(l => {
        if (l !== link) {
            l.status = '';
        }
    });
    
    // Update the visualization
    updateVisualization();
    
    // Apply a pulse animation to show handoff
    setTimeout(() => {
        const nodeElement = document.querySelector(`.agent-node[data-id="${to_agent}"] circle`);
        if (nodeElement) {
            nodeElement.classList.add('handoff-animation');
            setTimeout(() => nodeElement.classList.remove('handoff-animation'), 1000);
        }
    }, 50);
}

/**
 * Handle agent thinking updates
 */
function handleAgentThinking(message) {
    const { agent, thinking, request_id } = message;
    
    // Skip if not related to current request
    if (request_id !== currentRequestId) return;
    
    // Find or create the agent node
    let agentNode = networkGraph.nodes.find(n => n.id === agent);
    
    if (!agentNode) {
        agentNode = { id: agent, status: 'active', thinking: thinking };
        networkGraph.nodes.push(agentNode);
        
        // Connect to user if first connection
        const existingUserLink = networkGraph.links.find(l => l.target === agent);
        if (!existingUserLink) {
            networkGraph.links.push({
                source: 'User',
                target: agent,
                status: 'active'
            });
        }
    } else {
        agentNode.status = 'active';
        agentNode.thinking = thinking;
    }
    
    // Make sure any incoming links to this agent are active
    networkGraph.links.forEach(link => {
        if (link.target === agent) {
            link.status = 'active';
        }
    });
    
    // Store agent state
    agentStates[agent] = { 
        ...agentStates[agent] || {},
        status: 'active',
        thinking: thinking
    };
    
    // Update visualization
    updateVisualization();
}

/**
 * Handle agent errors
 */
function handleAgentError(message) {
    const { agent, error, request_id } = message;
    
    // Skip if not related to current request
    if (request_id !== currentRequestId) return;
    
    // Update error state
    errorState = {
        hasError: true,
        message: error,
        agent: agent,
        time: new Date()
    };
    
    // Find or create the agent node
    let agentNode = networkGraph.nodes.find(n => n.id === agent);
    
    if (!agentNode) {
        agentNode = { id: agent, status: 'error', error: error };
        networkGraph.nodes.push(agentNode);
    } else {
        agentNode.status = 'error';
        agentNode.error = error;
    }
    
    // Update any links to this agent
    networkGraph.links.forEach(link => {
        if (link.target === agent || link.source === agent) {
            link.status = 'error';
        }
    });
    
    // Update visualization
    updateVisualization();
    
    // Show error in status panel
    statusPanel.innerHTML = `Error in ${agent}: ${error}`;
    statusPanel.classList.add('error');
}

/**
 * Update workflow status display
 */
function updateWorkflowStatus(message) {
    // Update status display
    statusPanel.innerHTML = message.message;
    statusPanel.classList.remove('error');
}

/**
 * Finalize a request
 */
function finalizeRequest(requestId) {
    if (requestId === currentRequestId) {
        // Mark all nodes as idle
        networkGraph.nodes.forEach(node => {
            if (node.type !== 'user') {
                node.status = 'idle';
            }
        });
        
        // Reset all link statuses
        networkGraph.links.forEach(link => {
            link.status = '';
        });
        
        // Update request status
        requestStatusEl.textContent = `Request completed: ${requestId}`;
        
        // Update visualization
        updateVisualization();
    }
}

// Extend the WebSocket message handling to support visualization
const originalHandleWebSocketMessage = handleWebSocketMessage;
handleWebSocketMessage = function(message) {
    // Call the original handler first
    originalHandleWebSocketMessage(message);
    
    // Also dispatch an event for the visualization
    document.dispatchEvent(new CustomEvent('agentNetworkUpdate', { 
        detail: message 
    }));
};