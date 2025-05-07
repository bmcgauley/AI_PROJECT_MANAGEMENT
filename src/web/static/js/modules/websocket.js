// WebSocket handling
export let ws = null;

// Initialize WebSocket connection
export function initWebSocket(handlers) {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
        handlers.onConnect?.();
    };
    
    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handlers.onMessage?.(message);
    };
    
    ws.onclose = () => {
        console.log('WebSocket disconnected');
        handlers.onDisconnect?.();
        // Try to reconnect after delay
        setTimeout(() => initWebSocket(handlers), 2000);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        handlers.onError?.(error);
    };
}

// Send message through WebSocket
export function sendMessage(message) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(message));
        return true;
    }
    return false;
}