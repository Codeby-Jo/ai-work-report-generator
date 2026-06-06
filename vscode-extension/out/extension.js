"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = require("vscode");
const axios_1 = require("axios");
// The URL of our Python FastAPI Dashboard
const BACKEND_URL = 'http://127.0.0.1:8000/api/log';
function activate(context) {
    console.log('AI Work Tracker extension is now active!');
    // Register a manual command
    let disposable = vscode.commands.registerCommand('ai-work-tracker.start', () => {
        vscode.window.showInformationMessage('AI Work Tracker is monitoring your code!');
    });
    context.subscriptions.push(disposable);
    // Listen for file saves (Coding Activity)
    vscode.workspace.onDidSaveTextDocument(async (document) => {
        const filepath = document.fileName;
        // Ignore saving the database or extension files themselves to avoid infinite loops
        if (filepath.includes('.db') || filepath.includes('extension.ts')) {
            return;
        }
        const filename = filepath.split('/').pop() || 'Unknown';
        try {
            await axios_1.default.post(BACKEND_URL, {
                filename: filename,
                category: 'Coding',
                event_type: 'vscode_save',
                details: `Saved file in VS Code: ${filename}`
            });
            console.log(`Successfully logged save event for ${filename}`);
        }
        catch (error) {
            console.error('Failed to send log to backend dashboard.');
        }
    });
}
function deactivate() { }
//# sourceMappingURL=extension.js.map