const express = require('express');
const { spawn } = require('child_process');
const path = require('path');
const { createProxyMiddleware } = require('http-proxy-middleware');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;
const PYTHON_PORT = process.env.PYTHON_PORT || 8888;

let pythonCmd = process.env.PYTHON_PATH || 'python';
const defaultWinVenv = path.join(process.env.USERPROFILE || '', '.unsloth', 'studio', 'unsloth_studio', 'Scripts', 'python.exe');
if (!process.env.PYTHON_PATH && fs.existsSync(defaultWinVenv)) {
    pythonCmd = defaultWinVenv;
}

console.log('Starting Unsloth Python Engine with: ' + pythonCmd);
const backend = spawn(`"` + pythonCmd + `"`, ['studio/backend/run.py', '--port', PYTHON_PORT.toString(), '--enable-tools'], {
    stdio: 'inherit',
    shell: true
});

// Using app.all preserves the full req.url instead of stripping the prefix like app.use does
const apiProxy = createProxyMiddleware({ 
    target: `http://127.0.0.1:${PYTHON_PORT}`, 
    changeOrigin: true,
    ws: true
});

app.all('/api/*', apiProxy);
app.all('/v1/*', apiProxy);
app.all('/health', apiProxy);
app.all('/auth/*', apiProxy); // just in case

const frontendPath = path.join(__dirname, 'studio', 'frontend', 'dist');
app.use(express.static(frontendPath));

app.get('*', (req, res) => {
    res.sendFile(path.join(frontendPath, 'index.html'));
});

app.listen(PORT, () => {
    console.log(`[Unsloth Web Server] Unified environment running on http://localhost:${PORT}`);
});

process.on('SIGINT', () => {
    backend.kill();
    process.exit();
});
