const electron = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const { existsSync, mkdirSync } = require('fs');

if (!electron || typeof electron === 'string') {
    throw new Error(
        'Electron main process did not initialize correctly. Start the app with the Electron binary, not plain node.'
    );
}

const { app, BrowserWindow, ipcMain } = electron;

// Prefer the safest cross-platform startup path over custom GPU tuning.
app.disableHardwareAcceleration();

let mainWindow;
let pythonProcess;
const appRoot = path.join(__dirname, '..');
const cacheRoot = path.join(appRoot, '.cache');
const backendHost = process.env.EDITH_BACKEND_HOST || '127.0.0.1';
const backendPort = Number(process.env.EDITH_BACKEND_PORT || '8000');

function ensureCacheDirs() {
    mkdirSync(path.join(cacheRoot, 'matplotlib'), { recursive: true });
    mkdirSync(path.join(cacheRoot, 'fontconfig'), { recursive: true });
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1920,
        height: 1080,
        title: 'Edith',
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false, // For simple IPC/Socket.IO usage
        },
        backgroundColor: '#000000',
        frame: false, // Frameless for custom UI
        titleBarStyle: 'hidden',
        show: false, // Don't show until ready
    });

    // In dev, load Vite server. In prod, load index.html
    const isDev = process.env.NODE_ENV !== 'production';

    const loadFrontend = (retries = 3) => {
        const url = isDev ? 'http://localhost:5173' : null;
        const loadPromise = isDev
            ? mainWindow.loadURL(url)
            : mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));

        loadPromise
            .then(() => {
                console.log('Frontend loaded successfully!');
                windowWasShown = true;
                mainWindow.show();
                if (isDev) {
                    mainWindow.webContents.openDevTools();
                }
            })
            .catch((err) => {
                console.error(`Failed to load frontend: ${err.message}`);
                if (retries > 0) {
                    console.log(`Retrying in 1 second... (${retries} retries left)`);
                    setTimeout(() => loadFrontend(retries - 1), 1000);
                } else {
                    console.error('Failed to load frontend after all retries. Keeping window open.');
                    windowWasShown = true;
                    mainWindow.show(); // Show anyway so user sees something
                }
            });
    };

    loadFrontend();

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

function startPythonBackend() {
    const scriptPath = path.join(__dirname, '../backend/server.py');
    const venvPython = path.join(__dirname, '../.venv/bin/python3');
    const pythonBin = process.env.PYTHON_BIN || (existsSync(venvPython) ? venvPython : 'python3');
    console.log(`Starting Python backend: ${scriptPath}`);
    ensureCacheDirs();

    pythonProcess = spawn(pythonBin, [scriptPath], {
        cwd: path.join(__dirname, '../backend'),
        env: {
            ...process.env,
            PYTHON_BIN: pythonBin,
            MPLCONFIGDIR: process.env.MPLCONFIGDIR || path.join(cacheRoot, 'matplotlib'),
            XDG_CACHE_HOME: process.env.XDG_CACHE_HOME || cacheRoot,
        },
    });

    pythonProcess.stdout.on('data', (data) => {
        console.log(`[Python]: ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
        console.error(`[Python Error]: ${data}`);
    });
}

app.whenReady().then(() => {
    ensureCacheDirs();

    ipcMain.on('window-minimize', () => {
        if (mainWindow) mainWindow.minimize();
    });

    ipcMain.on('window-maximize', () => {
        if (mainWindow) {
            if (mainWindow.isMaximized()) {
                mainWindow.unmaximize();
            } else {
                mainWindow.maximize();
            }
        }
    });

    ipcMain.on('window-close', () => {
        if (mainWindow) mainWindow.close();
    });

    checkBackendPort(backendPort).then((isTaken) => {
        if (isTaken) {
            console.log(`Port ${backendPort} is taken. Assuming backend is already running manually.`);
            waitForBackend().then(createWindow);
        } else {
            startPythonBackend();
            // Give it a moment to start, then wait for health check
            setTimeout(() => {
                waitForBackend().then(createWindow);
            }, 1000);
        }
    });

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

function checkBackendPort(port) {
    return new Promise((resolve) => {
        const net = require('net');
        const server = net.createServer();
        server.once('error', (err) => {
            if (err.code === 'EADDRINUSE') {
                resolve(true);
            } else {
                resolve(false);
            }
        });
        server.once('listening', () => {
            server.close();
            resolve(false);
        });
        server.listen(port);
    });
}

function waitForBackend() {
    return new Promise((resolve) => {
        const check = () => {
            const http = require('http');
            http.get(`http://${backendHost}:${backendPort}/status`, (res) => {
                if (res.statusCode === 200) {
                    console.log('Backend is ready!');
                    resolve();
                } else {
                    console.log('Backend not ready, retrying...');
                    setTimeout(check, 1000);
                }
            }).on('error', (err) => {
                console.log('Waiting for backend...');
                setTimeout(check, 1000);
            });
        };
        check();
    });
}

let windowWasShown = false;

app.on('window-all-closed', () => {
    // Only quit if the window was actually shown at least once
    // This prevents quitting during startup if window creation fails
    if (process.platform !== 'darwin' && windowWasShown) {
        app.quit();
    } else if (!windowWasShown) {
        console.log('Window was never shown - keeping app alive to allow retries');
    }
});

app.on('will-quit', () => {
    console.log('App closing... Killing Python backend.');
    if (pythonProcess) {
        if (process.platform === 'win32') {
            // Windows: Force kill the process tree synchronously
            try {
                const { execSync } = require('child_process');
                execSync(`taskkill /pid ${pythonProcess.pid} /f /t`);
            } catch (e) {
                console.error('Failed to kill python process:', e.message);
            }
        } else {
            // Unix: SIGKILL
            pythonProcess.kill('SIGKILL');
        }
        pythonProcess = null;
    }
});
