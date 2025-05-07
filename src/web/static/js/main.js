// Main entry point
import { App } from './modules/app.js';

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    const app = new App();
    app.init();
});