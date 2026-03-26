import React, { useEffect, useRef, useState } from 'react';
import io from 'socket.io-client';
import { Clock, Minus, X } from 'lucide-react';

import Visualizer from './components/Visualizer';
import TopAudioBar from './components/TopAudioBar';
import ChatModule from './components/ChatModule';
import ToolsModule from './components/ToolsModule';
import SettingsWindow from './components/SettingsWindow';
import ConversationHistoryPanel from './components/ConversationHistoryPanel';
import CommunicationsPanel from './components/CommunicationsPanel';

const isBrowserRuntime = typeof window !== 'undefined';
const isElectronRuntime = isBrowserRuntime && typeof window.require === 'function';
const backendHost = typeof window !== 'undefined' && window.location?.hostname
    ? window.location.hostname
    : 'localhost';
const isLocalBrowserSession = isBrowserRuntime && ['localhost', '127.0.0.1'].includes(window.location?.hostname || '');
const backendUrl = import.meta.env.VITE_BACKEND_URL || (
    isElectronRuntime
        ? `http://${backendHost}:8000`
        : (isLocalBrowserSession ? `http://${backendHost}:8000` : (isBrowserRuntime ? window.location.origin : 'http://localhost:8000'))
);
const socket = io(backendUrl, { path: '/socket.io' });
const electronApi = isElectronRuntime ? window.require('electron') : null;
const ipcRenderer = electronApi?.ipcRenderer || { send: () => {} };
const shell = electronApi?.shell || {
    openPath: async (target) => {
        if (target) {
            window.open(`file://${target}`, '_blank', 'noopener,noreferrer');
        }
        return '';
    },
    openExternal: async (target) => {
        if (target) {
            window.open(target, '_blank', 'noopener,noreferrer');
        }
    },
};
const fs = isElectronRuntime ? window.require('fs') : null;
const path = isElectronRuntime ? window.require('path') : null;
const BufferCtor = isElectronRuntime ? window.require('buffer').Buffer : null;
const IST_TIME_FORMAT = { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata' };
const formatIstTime = () => new Date().toLocaleTimeString([], IST_TIME_FORMAT);

function App() {
    const [status, setStatus] = useState('Disconnected');
    const [socketConnected, setSocketConnected] = useState(socket.connected);
    const [accessGranted, setAccessGranted] = useState(false);
    const [accessCodeInput, setAccessCodeInput] = useState('');
    const [validatedAccessCode, setValidatedAccessCode] = useState('');
    const [accessError, setAccessError] = useState('');
    const [isVerifyingAccess, setIsVerifyingAccess] = useState(false);
    const [faceAuthState, setFaceAuthState] = useState({ available: false, enrolled: false });
    const [isFaceBusy, setIsFaceBusy] = useState(false);
    const [isConnected, setIsConnected] = useState(true);
    const [isMuted, setIsMuted] = useState(false);
    const [isVideoOn, setIsVideoOn] = useState(false);
    const [messages, setMessages] = useState([]);
    const [inputValue, setInputValue] = useState('');
    const [showSettings, setShowSettings] = useState(false);
    const [showHistory, setShowHistory] = useState(false);
    const [showCommunications, setShowCommunications] = useState(false);
    const [conversationArchive, setConversationArchive] = useState([]);
    const [communications, setCommunications] = useState([]);
    const [spotifyState, setSpotifyState] = useState({ configured: false, authenticated: false });
    const [currentProject, setCurrentProject] = useState('default');
    const [currentTime, setCurrentTime] = useState(new Date());
    const [aiAudioData, setAiAudioData] = useState(new Array(64).fill(0));
    const [micAudioData] = useState(new Array(32).fill(0));
    const [fps, setFps] = useState(0);
    const [micDevices, setMicDevices] = useState([]);
    const [speakerDevices, setSpeakerDevices] = useState([]);
    const [webcamDevices, setWebcamDevices] = useState([]);
    const [selectedMicId, setSelectedMicId] = useState(() => localStorage.getItem('selectedMicId') || '');
    const [selectedSpeakerId, setSelectedSpeakerId] = useState(() => localStorage.getItem('selectedSpeakerId') || '');
    const [selectedWebcamId, setSelectedWebcamId] = useState(() => localStorage.getItem('selectedWebcamId') || '');
    const [elementPositions, setElementPositions] = useState({
        visualizer: { x: window.innerWidth / 2, y: 220 },
        chat: { x: window.innerWidth / 2, y: 420 },
        tools: { x: window.innerWidth / 2, y: window.innerHeight - 100 },
    });
    const [elementSizes, setElementSizes] = useState({
        visualizer: { w: 550, h: 260 },
        chat: { w: 620, h: 250 },
        tools: { w: 420, h: 80 },
    });
    const [activeDragElement, setActiveDragElement] = useState(null);
    const [zIndexOrder, setZIndexOrder] = useState(['visualizer', 'chat', 'tools']);

    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const transmissionCanvasRef = useRef(null);
    const isVideoOnRef = useRef(false);
    const frameCountRef = useRef(0);
    const lastFrameTimeRef = useRef(0);
    const lastVideoUploadTimeRef = useRef(0);
    const isDraggingRef = useRef(false);
    const dragOffsetRef = useRef({ x: 0, y: 0 });
    const activeDragElementRef = useRef(null);
    const elementPositionsRef = useRef(elementPositions);
    const hasAutoConnectedRef = useRef(false);
    const spotifyAuthPollRef = useRef(null);
    const spotifyPlayerRef = useRef(null);
    const spotifyTokenRef = useRef(null);
    const lastSpotifySummaryRef = useRef('');
    const puterLoadRef = useRef(null);
    const selectedMicIdRef = useRef(selectedMicId);
    const selectedSpeakerIdRef = useRef(selectedSpeakerId);
    const selectedWebcamIdRef = useRef(selectedWebcamId);
    const isMutedRef = useRef(isMuted);
    const lastAudioUpdateRef = useRef(0);

    const emitDeviceInventory = (audioInputs, audioOutputs, videoInputs) => {
        socket.emit('update_device_inventory', {
            microphone: audioInputs.map(device => ({ id: device.deviceId, label: device.label || 'Unnamed microphone' })),
            speaker: audioOutputs.map(device => ({ id: device.deviceId, label: device.label || 'Unnamed speaker' })),
            webcam: videoInputs.map(device => ({ id: device.deviceId, label: device.label || 'Unnamed camera' })),
        });
    };

    const startAudioSession = (micId = selectedMicIdRef.current, speakerId = selectedSpeakerIdRef.current, muted = false) => {
        const queryDevice = micDevices.find(d => d.deviceId === micId);
        const speakerDevice = speakerDevices.find(d => d.deviceId === speakerId);
        const deviceName = queryDevice?.label?.trim() || null;
        const outputDeviceName = speakerDevice?.label?.trim() || null;
        const runtimeContext = {
            runtime: isElectronRuntime ? 'electron' : 'browser',
            platform: navigator.platform || '',
            userAgent: navigator.userAgent || '',
            hostname: window.location.hostname || '',
            origin: window.location.origin || '',
        };
        const captureMicOnBackend = isElectronRuntime || isLocalBrowserSession;
        socket.emit('start_audio', {
            device_name: deviceName,
            output_device_name: outputDeviceName,
            muted,
            capture_mic: captureMicOnBackend,
            access_code: validatedAccessCode,
            client_context: runtimeContext,
        });
    };

    const applyDeviceSwitch = async ({ kind, deviceId, label }) => {
        if (kind === 'microphone') {
            setSelectedMicId(deviceId);
            addMessage('System', `Microphone switched to ${label}.`);
            if (isConnected) {
                socket.emit('stop_audio');
                setTimeout(() => startAudioSession(deviceId, selectedSpeakerIdRef.current, isMutedRef.current), 250);
            }
            return;
        }

        if (kind === 'speaker') {
            setSelectedSpeakerId(deviceId);
            addMessage('System', `Speaker switched to ${label}.`);
            if (isConnected) {
                socket.emit('stop_audio');
                setTimeout(() => startAudioSession(selectedMicIdRef.current, deviceId, isMutedRef.current), 250);
            }
            return;
        }

        if (kind === 'webcam') {
            setSelectedWebcamId(deviceId);
            addMessage('System', `Webcam switched to ${label}.`);
            if (isVideoOnRef.current) {
                stopVideo();
                setTimeout(() => startVideo(deviceId), 250);
            }
        }
    };

    useEffect(() => {
        elementPositionsRef.current = elementPositions;
    }, [elementPositions]);

    useEffect(() => {
        selectedMicIdRef.current = selectedMicId;
    }, [selectedMicId]);

    useEffect(() => {
        selectedSpeakerIdRef.current = selectedSpeakerId;
    }, [selectedSpeakerId]);

    useEffect(() => {
        selectedWebcamIdRef.current = selectedWebcamId;
    }, [selectedWebcamId]);

    useEffect(() => {
        isMutedRef.current = isMuted;
    }, [isMuted]);

    useEffect(() => {
        const timer = setInterval(() => setCurrentTime(new Date()), 1000);
        return () => clearInterval(timer);
    }, []);

    useEffect(() => {
        const centerElements = () => {
            const width = window.innerWidth;
            const height = window.innerHeight;
            const vizHeight = Math.min(300, height * 0.26);
            const chatHeight = Math.min(380, height * 0.30);

            setElementSizes(prev => ({
                ...prev,
                visualizer: { w: Math.min(680, width * 0.56), h: vizHeight },
                chat: { w: Math.min(900, width * 0.72), h: chatHeight },
            }));

            setElementPositions(prev => ({
                ...prev,
                visualizer: { x: width / 2, y: Math.max(260, height * 0.34) },
                chat: { x: width / 2, y: Math.max(260, height * 0.34) + vizHeight + 10 },
                tools: { x: width / 2, y: height - 92 },
            }));
        };

        centerElements();
        window.addEventListener('resize', centerElements);
        return () => window.removeEventListener('resize', centerElements);
    }, []);

    useEffect(() => {
        const enumerateDevices = async () => {
            try {
                const devices = await navigator.mediaDevices.enumerateDevices();
                const audioInputs = devices.filter(d => d.kind === 'audioinput');
                const audioOutputs = devices.filter(d => d.kind === 'audiooutput');
                const videoInputs = devices.filter(d => d.kind === 'videoinput');

                setMicDevices(audioInputs);
                setSpeakerDevices(audioOutputs);
                setWebcamDevices(videoInputs);
                emitDeviceInventory(audioInputs, audioOutputs, videoInputs);

                if (!selectedMicId && audioInputs[0]) {
                    setSelectedMicId(audioInputs[0].deviceId);
                }
                if (!selectedSpeakerId && audioOutputs[0]) {
                    setSelectedSpeakerId(audioOutputs[0].deviceId);
                }
                if (!selectedWebcamId && videoInputs[0]) {
                    setSelectedWebcamId(videoInputs[0].deviceId);
                }
            } catch (error) {
                console.error('Failed to enumerate devices:', error);
            }
        };

        enumerateDevices();
        navigator.mediaDevices?.addEventListener?.('devicechange', enumerateDevices);
        return () => navigator.mediaDevices?.removeEventListener?.('devicechange', enumerateDevices);
    }, []);

    useEffect(() => {
        if (selectedMicId) localStorage.setItem('selectedMicId', selectedMicId);
    }, [selectedMicId]);

    useEffect(() => {
        if (selectedSpeakerId) localStorage.setItem('selectedSpeakerId', selectedSpeakerId);
    }, [selectedSpeakerId]);

    useEffect(() => {
        if (selectedWebcamId) localStorage.setItem('selectedWebcamId', selectedWebcamId);
    }, [selectedWebcamId]);

    const addMessage = (sender, text) => {
        setMessages(prev => [...prev, { sender, text, time: formatIstTime() }]);
    };

    const ensurePuterLoaded = async () => {
        if (window.puter?.ai?.txt2img) {
            return window.puter;
        }
        if (puterLoadRef.current) {
            return puterLoadRef.current;
        }

        puterLoadRef.current = new Promise((resolve, reject) => {
            const existing = document.querySelector('script[data-puter-sdk="true"]');
            if (existing) {
                existing.addEventListener('load', () => resolve(window.puter));
                existing.addEventListener('error', () => reject(new Error('Failed to load Puter.js')));
                return;
            }

            const script = document.createElement('script');
            script.src = 'https://js.puter.com/v2/';
            script.async = true;
            script.dataset.puterSdk = 'true';
            script.onload = () => resolve(window.puter);
            script.onerror = () => reject(new Error('Failed to load Puter.js'));
            document.body.appendChild(script);
        });

        return puterLoadRef.current;
    };

    const waitForImageElement = async (image) => {
        if (!(image instanceof HTMLImageElement)) {
            return image;
        }
        if (image.complete && image.src) {
            return image;
        }
        await new Promise((resolve, reject) => {
            const cleanup = () => {
                image.removeEventListener('load', onLoad);
                image.removeEventListener('error', onError);
            };
            const onLoad = () => {
                cleanup();
                resolve();
            };
            const onError = () => {
                cleanup();
                reject(new Error('The generated image failed to load.'));
            };
            image.addEventListener('load', onLoad, { once: true });
            image.addEventListener('error', onError, { once: true });
        });
        return image;
    };

    const extractImageSource = async (value) => {
        if (!value) return null;

        if (value instanceof HTMLImageElement) {
            const image = await waitForImageElement(value);
            return image.currentSrc || image.src || null;
        }

        if (value instanceof Blob) {
            return value;
        }

        if (value instanceof ArrayBuffer || ArrayBuffer.isView(value)) {
            return value;
        }

        if (value instanceof HTMLCanvasElement) {
            return value.toDataURL('image/png');
        }

        if (value instanceof HTMLElement) {
            const nestedImage = value.querySelector('img');
            if (nestedImage) {
                return extractImageSource(nestedImage);
            }
        }

        if (typeof value === 'string') {
            return value.trim() || null;
        }

        if (Array.isArray(value)) {
            for (const item of value) {
                const resolved = await extractImageSource(item);
                if (resolved) return resolved;
            }
            return null;
        }

        if (typeof value === 'object') {
            const directError = value.error || value.message || value.reason;
            if (typeof directError === 'string' && directError.trim()) {
                throw new Error(directError.trim());
            }
            const candidates = [
                value.src,
                value.currentSrc,
                value.url,
                value.dataUrl,
                value.data,
                value.image,
                value.imageElement,
                value.img,
                value.blob,
                value.file,
                value.response,
                value.result,
                value.output,
            ];
            for (const candidate of candidates) {
                const resolved = await extractImageSource(candidate);
                if (resolved) return resolved;
            }
        }

        return null;
    };

    const parseDataUrl = (src) => {
        const match = /^data:(image\/[a-zA-Z0-9.+-]+);base64,(.+)$/s.exec(src || '');
        if (!match) {
            return null;
        }
        return {
            mimeType: match[1],
            buffer: BufferCtor ? BufferCtor.from(match[2], 'base64') : null,
            dataUrl: src,
        };
    };

    const inferExtensionFromMime = (mimeType) => {
        if (mimeType === 'image/jpeg') return '.jpg';
        if (mimeType === 'image/webp') return '.webp';
        if (mimeType === 'image/gif') return '.gif';
        return '.png';
    };

    const inferFilename = (outputPath, fallbackExt = '.png') => {
        const raw = String(outputPath || 'edith_image').trim();
        const base = raw.split('/').pop()?.split('\\').pop() || 'edith_image';
        return /\.[A-Za-z0-9]+$/.test(base) ? base : `${base}${fallbackExt}`;
    };

    const triggerBrowserDownload = async (blob, outputPath, mimeType = 'application/octet-stream') => {
        const finalBlob = blob instanceof Blob ? blob : new Blob([blob], { type: mimeType });
        const filename = inferFilename(outputPath, inferExtensionFromMime(mimeType));
        const url = URL.createObjectURL(finalBlob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = filename;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        setTimeout(() => URL.revokeObjectURL(url), 2000);
        return { path: filename, mimeType, downloaded: true };
    };

    const saveImageFromSource = async (src, outputPath) => {
        if (src instanceof Blob) {
            const mimeType = src.type || 'image/png';
            if (!isElectronRuntime) {
                return triggerBrowserDownload(src, outputPath, mimeType);
            }
            let finalPath = outputPath;
            if (!path.extname(finalPath)) {
                finalPath += inferExtensionFromMime(mimeType);
            }
            const arrayBuffer = await src.arrayBuffer();
            fs.mkdirSync(path.dirname(finalPath), { recursive: true });
            fs.writeFileSync(finalPath, BufferCtor.from(arrayBuffer));
            return { path: finalPath, mimeType };
        }

        if (src instanceof ArrayBuffer || ArrayBuffer.isView(src)) {
            if (!isElectronRuntime) {
                const bytes = src instanceof ArrayBuffer ? new Uint8Array(src) : new Uint8Array(src.buffer, src.byteOffset, src.byteLength);
                return triggerBrowserDownload(bytes, outputPath, 'image/png');
            }
            let finalPath = outputPath;
            if (!path.extname(finalPath)) {
                finalPath += '.png';
            }
            const bytes = src instanceof ArrayBuffer ? new Uint8Array(src) : new Uint8Array(src.buffer, src.byteOffset, src.byteLength);
            fs.mkdirSync(path.dirname(finalPath), { recursive: true });
            fs.writeFileSync(finalPath, BufferCtor.from(bytes));
            return { path: finalPath, mimeType: 'image/png' };
        }

        const dataUrl = parseDataUrl(src);
        if (dataUrl) {
            if (!isElectronRuntime) {
                const response = await fetch(dataUrl.dataUrl);
                return triggerBrowserDownload(await response.blob(), outputPath, dataUrl.mimeType);
            }
            let finalPath = outputPath;
            const desiredExt = inferExtensionFromMime(dataUrl.mimeType);
            if (!path.extname(finalPath)) {
                finalPath += desiredExt;
            }
            fs.mkdirSync(path.dirname(finalPath), { recursive: true });
            fs.writeFileSync(finalPath, dataUrl.buffer);
            return { path: finalPath, mimeType: dataUrl.mimeType };
        }

        if (/^(blob:|https?:)/i.test(src || '')) {
            const response = await fetch(src);
            if (!response.ok) {
                throw new Error(`Image download failed with status ${response.status}.`);
            }
            const mimeType = response.headers.get('content-type') || 'image/png';
            if (!isElectronRuntime) {
                return triggerBrowserDownload(await response.blob(), outputPath, mimeType);
            }
            const arrayBuffer = await response.arrayBuffer();
            let finalPath = outputPath;
            if (!path.extname(finalPath)) {
                finalPath += inferExtensionFromMime(mimeType);
            }
            fs.mkdirSync(path.dirname(finalPath), { recursive: true });
            fs.writeFileSync(finalPath, BufferCtor.from(arrayBuffer));
            return { path: finalPath, mimeType };
        }

        throw new Error('The image data was not returned by the system.');
    };

    const handleImageGenerationRequest = async (payload) => {
        try {
            addMessage('System', 'Generating image...');
            const puter = await ensurePuterLoaded();
            const generated = await puter.ai.txt2img(payload.prompt, {
                model: payload.model || 'black-forest-labs/FLUX.1-schnell-Free',
            });
            const src = await extractImageSource(generated);
            if (!src) {
                console.error('Unexpected Puter image result:', generated);
                throw new Error('The image data was not returned by the system.');
            }

            const saved = await saveImageFromSource(src, payload.outputPath);
            await shell.openPath(saved.path);
            socket.emit('image_generation_result', {
                id: payload.id,
                success: true,
                path: saved.path,
                mimeType: saved.mimeType,
            });
        } catch (error) {
            console.error(error);
            socket.emit('image_generation_result', {
                id: payload?.id,
                success: false,
                error: error?.message || 'Image generation failed.',
            });
        }
    };

    const captureSingleVideoFrame = async () => {
        const constraints = {
            video: selectedWebcamId ? { deviceId: { exact: selectedWebcamId } } : true,
        };

        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        try {
            const tempVideo = document.createElement('video');
            tempVideo.srcObject = stream;
            tempVideo.muted = true;
            tempVideo.playsInline = true;
            await tempVideo.play();
            await new Promise(resolve => setTimeout(resolve, 300));

            const canvas = document.createElement('canvas');
            canvas.width = tempVideo.videoWidth || 640;
            canvas.height = tempVideo.videoHeight || 480;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(tempVideo, 0, 0, canvas.width, canvas.height);
            const dataUrl = canvas.toDataURL('image/jpeg', 0.82);
            return dataUrl.split(',')[1];
        } finally {
            stream.getTracks().forEach(track => track.stop());
        }
    };

    const handleFaceAction = async (mode) => {
        if (isFaceBusy) return;
        setIsFaceBusy(true);
        setAccessError('');
        try {
            const image = await captureSingleVideoFrame();
            socket.emit(mode, { image });
        } catch (error) {
            console.error(error);
            setAccessError('Camera access failed for Face ID.');
            setIsFaceBusy(false);
        }
    };

    useEffect(() => {
        const onConnect = () => {
            setSocketConnected(true);
            setStatus(accessGranted ? 'Connected' : 'Locked');
            socket.emit('get_settings');
            socket.emit('get_spotify_status');
            socket.emit('get_face_auth_status');
        };

        const onDisconnect = () => {
            setSocketConnected(false);
            setStatus('Disconnected');
        };

        const onStatus = (data) => {
            addMessage('System', data.msg);
            if (data.msg === 'Edith Started') setStatus('Model Connected');
            if (data.msg === 'Edith Stopped') setStatus('Connected');
        };

        const onBrowserFrame = (data) => {
            if (data?.log) {
                addMessage('System', data.log);
            }
        };

        const onTranscription = (data) => {
            setMessages(prev => {
                const last = prev[prev.length - 1];
                if (last && last.sender === data.sender) {
                    return [
                        ...prev.slice(0, -1),
                        { ...last, text: last.text + data.text },
                    ];
                }
                return [...prev, { sender: data.sender, text: data.text, time: formatIstTime() }];
            });
        };

        const onToolConfirmation = (data) => {
            socket.emit('confirm_tool', { id: data.id, confirmed: true });
        };
        const onProjectUpdate = (data) => setCurrentProject(data.project);
        const onAccessGranted = (data) => {
            setAccessGranted(true);
            setAccessError('');
            setStatus('Connected');
            setValidatedAccessCode((data?.code || '').trim());
            setIsVerifyingAccess(false);
            setIsFaceBusy(false);
        };
        const onForceShutdown = (payload) => {
            const farewell = payload?.farewell;
            const delayMs = Number(payload?.delay_ms) > 0 ? Number(payload.delay_ms) : 3000;
            if (farewell) {
                addMessage('Edith', farewell);
            }
            setStatus('Shutting Down');
            setTimeout(() => {
                if (isElectronRuntime) {
                    ipcRenderer.send('window-close');
                    return;
                }
                window.open('', '_self');
                window.close();
                setTimeout(() => {
                    if (!document.hidden) {
                        window.location.replace('about:blank');
                    }
                }, 150);
            }, delayMs);
        };
        const onError = (data) => {
            console.error(data);
            addMessage('System', `Error: ${data.msg}`);
            if (String(data.msg).toLowerCase().includes('access code')) {
                setAccessError(data.msg);
                setIsVerifyingAccess(false);
            }
            if (String(data.msg).toLowerCase().includes('face')) {
                setAccessError(data.msg);
                setIsFaceBusy(false);
            }
        };
        const onSettings = (settings) => {
            if (settings?.tool_permissions) {
                setStatus(prev => prev);
            }
        };
        const onSpotifyStatus = (data) => {
            setSpotifyState(data || { configured: false, authenticated: false });
            if (data?.authenticated && spotifyAuthPollRef.current) {
                clearInterval(spotifyAuthPollRef.current);
                spotifyAuthPollRef.current = null;
            }
            const summary = data?.authenticated
                ? `connected:${data?.preferred_device_name || 'no-device'}`
                : data?.auth_pending
                    ? 'pending'
                    : data?.configured
                        ? 'ready'
                        : 'not-configured';

            if (summary !== lastSpotifySummaryRef.current) {
                lastSpotifySummaryRef.current = summary;
                if (data?.authenticated) {
                    addMessage('System', `Spotify connected${data?.preferred_device_name ? ` on ${data.preferred_device_name}` : ''}.`);
                } else if (data?.auth_pending) {
                    addMessage('System', 'Waiting for Spotify authorization to complete...');
                }
            }
        };
        const onSpotifyAuth = async (data) => {
            if (!data?.url) return;
            await shell.openExternal(data.url);
            addMessage('System', 'Spotify authorization opened in your browser.');
            if (spotifyAuthPollRef.current) {
                clearInterval(spotifyAuthPollRef.current);
            }
            spotifyAuthPollRef.current = setInterval(() => {
                socket.emit('spotify_finish_auth');
            }, 1500);
        };
        const onCameraRequest = (data) => {
            const shouldEnable = data?.enabled !== false;
            if (shouldEnable) {
                if (!isVideoOnRef.current) {
                    startVideo();
                }
                return;
            }
            if (isVideoOnRef.current) {
                stopVideo();
            }
        };
        const onFaceAuthStatus = (data) => {
            setFaceAuthState(data || { available: false, enrolled: false });
            setIsFaceBusy(false);
        };
        const onConversationArchive = (sessions) => {
            setConversationArchive(Array.isArray(sessions) ? sessions : []);
        };
        const onCommunications = (items) => {
            setCommunications(Array.isArray(items) ? items : []);
        };
        const onImageGenerationRequest = (payload) => {
            handleImageGenerationRequest(payload);
        };
        const onDeviceSwitchRequest = (payload) => {
            if (!payload?.kind || !payload?.deviceId) {
                return;
            }
            applyDeviceSwitch(payload);
        };
        const onCommunicationNotification = (payload) => {
            if (!payload) return;
            const sender = payload.sender || 'Someone';
            const channel = (payload.channel || 'message').toUpperCase();
            const subject = payload.subject ? ` | ${payload.subject}` : '';
            addMessage('System', `${channel} from ${sender}${subject}: ${payload.body || ''}`);
        };
        const onAudioData = (data) => {
            const now = performance.now();
            if (now - lastAudioUpdateRef.current < 50) {
                return;
            }
            lastAudioUpdateRef.current = now;
            setAiAudioData(data.data);
        };

        socket.on('connect', onConnect);
        socket.on('disconnect', onDisconnect);
        socket.on('status', onStatus);
        socket.on('audio_data', onAudioData);
        socket.on('browser_frame', onBrowserFrame);
        socket.on('transcription', onTranscription);
        socket.on('tool_confirmation_request', onToolConfirmation);
        socket.on('project_update', onProjectUpdate);
        socket.on('access_granted', onAccessGranted);
        socket.on('force_shutdown', onForceShutdown);
        socket.on('error', onError);
        socket.on('settings', onSettings);
        socket.on('spotify_status', onSpotifyStatus);
        socket.on('spotify_auth', onSpotifyAuth);
        socket.on('camera_request', onCameraRequest);
        socket.on('face_auth_status', onFaceAuthStatus);
        socket.on('conversation_archive', onConversationArchive);
        socket.on('communications', onCommunications);
        socket.on('image_generation_request', onImageGenerationRequest);
        socket.on('device_switch_request', onDeviceSwitchRequest);
        socket.on('communication_notification', onCommunicationNotification);

        return () => {
            socket.off('connect', onConnect);
            socket.off('disconnect', onDisconnect);
            socket.off('status', onStatus);
            socket.off('browser_frame', onBrowserFrame);
            socket.off('transcription', onTranscription);
            socket.off('tool_confirmation_request', onToolConfirmation);
            socket.off('project_update', onProjectUpdate);
            socket.off('access_granted', onAccessGranted);
            socket.off('force_shutdown', onForceShutdown);
            socket.off('error', onError);
            socket.off('settings', onSettings);
            socket.off('spotify_status', onSpotifyStatus);
            socket.off('spotify_auth', onSpotifyAuth);
            socket.off('camera_request', onCameraRequest);
            socket.off('face_auth_status', onFaceAuthStatus);
            socket.off('conversation_archive', onConversationArchive);
            socket.off('communications', onCommunications);
            socket.off('image_generation_request', onImageGenerationRequest);
            socket.off('device_switch_request', onDeviceSwitchRequest);
            socket.off('communication_notification', onCommunicationNotification);
            socket.off('audio_data', onAudioData);
            if (spotifyAuthPollRef.current) {
                clearInterval(spotifyAuthPollRef.current);
                spotifyAuthPollRef.current = null;
            }
            stopVideo();
        };
    }, []);

    useEffect(() => {
        spotifyTokenRef.current = spotifyState?.web_playback_token || null;
    }, [spotifyState]);

    useEffect(() => {
        if (!spotifyState?.authenticated || !spotifyState?.web_playback_token || spotifyPlayerRef.current) {
            return;
        }

        let cancelled = false;

        const createPlayer = () => {
            if (cancelled || spotifyPlayerRef.current || !window.Spotify) {
                return;
            }

            const player = new window.Spotify.Player({
                name: 'Edith',
                getOAuthToken: (cb) => cb(spotifyTokenRef.current),
                volume: 0.75,
            });

            player.addListener('ready', ({ device_id }) => {
                socket.emit('spotify_player_ready', { device_id, device_name: 'Edith' });
            });

            player.addListener('not_ready', () => {
                socket.emit('get_spotify_status');
            });

            player.addListener('authentication_error', () => {
                socket.emit('get_spotify_status');
            });

            player.addListener('account_error', () => {
                addMessage('System', 'Spotify Premium is required for in-app playback.');
            });

            player.connect();
            spotifyPlayerRef.current = player;
        };

        const loadSdk = () => {
            if (window.Spotify) {
                createPlayer();
                return;
            }

            window.onSpotifyWebPlaybackSDKReady = createPlayer;
            const existing = document.querySelector('script[data-spotify-sdk="true"]');
            if (existing) {
                return;
            }

            const script = document.createElement('script');
            script.src = 'https://sdk.scdn.co/spotify-player.js';
            script.async = true;
            script.dataset.spotifySdk = 'true';
            document.body.appendChild(script);
        };

        loadSdk();

        return () => {
            cancelled = true;
        };
    }, [spotifyState?.authenticated, spotifyState?.web_playback_token]);

    useEffect(() => {
        if (socket.connected) {
            setSocketConnected(true);
            setStatus(accessGranted ? 'Connected' : 'Locked');
        }
    }, [accessGranted]);

    useEffect(() => {
        const hostedBrowserMode = !isElectronRuntime && !isLocalBrowserSession;
        if (!socketConnected || !accessGranted || !validatedAccessCode || !isConnected || hasAutoConnectedRef.current) {
            return;
        }
        if (!hostedBrowserMode && micDevices.length === 0) {
            return;
        }

        hasAutoConnectedRef.current = true;
        const timer = setTimeout(() => {
            setStatus('Connecting...');
            startAudioSession(selectedMicId, selectedSpeakerId, false);
        }, 300);

        return () => clearTimeout(timer);
    }, [socketConnected, accessGranted, validatedAccessCode, isConnected, micDevices, selectedMicId, selectedSpeakerId]);

    const startVideo = async (preferredWebcamId = selectedWebcamIdRef.current) => {
        if (isVideoOnRef.current) {
            return;
        }
        try {
            const constraints = {
                video: {
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                },
            };

            if (preferredWebcamId) {
                constraints.video.deviceId = { exact: preferredWebcamId };
            }

            const stream = await navigator.mediaDevices.getUserMedia(constraints);
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
                await videoRef.current.play();
            }

            if (!transmissionCanvasRef.current) {
                transmissionCanvasRef.current = document.createElement('canvas');
                transmissionCanvasRef.current.width = 640;
                transmissionCanvasRef.current.height = 360;
            }

            isVideoOnRef.current = true;
            setIsVideoOn(true);
            socket.emit('camera_status', { enabled: true });
            requestAnimationFrame(predictWebcam);
        } catch (error) {
            console.error('Error accessing camera:', error);
            addMessage('System', 'Error accessing camera');
        }
    };

    const stopVideo = () => {
        if (videoRef.current?.srcObject) {
            videoRef.current.srcObject.getTracks().forEach(track => track.stop());
            videoRef.current.srcObject = null;
        }
        isVideoOnRef.current = false;
        setIsVideoOn(false);
        setFps(0);
        socket.emit('camera_status', { enabled: false });
    };

    const predictWebcam = () => {
        if (!isVideoOnRef.current || !videoRef.current || !canvasRef.current) {
            return;
        }

        if (videoRef.current.readyState < 2 || videoRef.current.videoWidth === 0 || videoRef.current.videoHeight === 0) {
            requestAnimationFrame(predictWebcam);
            return;
        }

        const ctx = canvasRef.current.getContext('2d');
        if (canvasRef.current.width !== videoRef.current.videoWidth || canvasRef.current.height !== videoRef.current.videoHeight) {
            canvasRef.current.width = videoRef.current.videoWidth;
            canvasRef.current.height = videoRef.current.videoHeight;
        }

        ctx.drawImage(videoRef.current, 0, 0, canvasRef.current.width, canvasRef.current.height);

        const now = performance.now();

        if (isConnected && transmissionCanvasRef.current && now - lastVideoUploadTimeRef.current >= 450) {
            const transCtx = transmissionCanvasRef.current.getContext('2d');
            transCtx.drawImage(videoRef.current, 0, 0, transmissionCanvasRef.current.width, transmissionCanvasRef.current.height);
            const dataUrl = transmissionCanvasRef.current.toDataURL('image/jpeg', 0.65);
            const base64Image = dataUrl.split(',')[1];
            socket.emit('video_frame', { image: base64Image });
            lastVideoUploadTimeRef.current = now;
        }

        frameCountRef.current += 1;
        if (now - lastFrameTimeRef.current >= 1000) {
            setFps(frameCountRef.current);
            frameCountRef.current = 0;
            lastFrameTimeRef.current = now;
        }

        requestAnimationFrame(predictWebcam);
    };

    const toggleVideo = () => {
        if (isVideoOn) {
            stopVideo();
        } else {
            startVideo();
        }
    };

    const togglePower = () => {
        if (isConnected) {
            socket.emit('stop_audio');
            setIsConnected(false);
            setIsMuted(false);
            return;
        }

        startAudioSession(selectedMicId, selectedSpeakerId, false);
        setIsConnected(true);
        setIsMuted(false);
    };

    const submitAccessCode = (e) => {
        e.preventDefault();
        if (!accessCodeInput.trim() || !socketConnected || isVerifyingAccess) {
            return;
        }
        setIsVerifyingAccess(true);
        setAccessError('');
        socket.emit('verify_access_code', { code: accessCodeInput.trim() });
    };

    const toggleMute = () => {
        if (!isConnected) return;
        if (isMuted) {
            socket.emit('resume_audio');
            setIsMuted(false);
        } else {
            socket.emit('pause_audio');
            setIsMuted(true);
        }
    };

    const handleSend = (e) => {
        if (e.key === 'Enter' && inputValue.trim()) {
            socket.emit('user_input', { text: inputValue });
            addMessage('You', inputValue);
            setInputValue('');
        }
    };

    const handleFileUpload = (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (event) => {
            const textContent = event.target.result;
            if (typeof textContent === 'string' && textContent.length > 0) {
                socket.emit('upload_memory', { memory: textContent });
                addMessage('System', 'Uploading memory...');
            } else {
                addMessage('System', 'Empty or invalid memory file');
            }
        };
        reader.readAsText(file);
    };

    const handleRememberMemory = (text) => {
        const cleaned = text.trim();
        if (!cleaned) {
            addMessage('System', 'Memory note was empty');
            return;
        }
        socket.emit('remember_memory', { text: cleaned });
        addMessage('System', 'Memory note saved');
    };

    const handleSpotifyConnect = () => {
        socket.emit('spotify_begin_auth');
    };

    const handleSpotifyControl = (action, payload = {}) => {
        if (spotifyPlayerRef.current?.activateElement) {
            spotifyPlayerRef.current.activateElement().catch(() => {});
        }
        if (action === 'dj') {
            addMessage('System', 'Spotify DJ is picking something.');
        }
        socket.emit('spotify_control', { action, ...payload });
    };

    const toggleHistory = () => {
        if (!showHistory) {
            socket.emit('get_conversation_archive');
        }
        setShowHistory(prev => !prev);
    };

    const toggleCommunications = () => {
        if (!showCommunications) {
            socket.emit('get_communications');
        }
        setShowCommunications(prev => !prev);
    };

    const getZIndex = (id) => 30 + zIndexOrder.indexOf(id);
    const bringToFront = (id) => {
        setZIndexOrder(prev => [...prev.filter(item => item !== id), id]);
    };

    const handleMouseDown = (e, id) => {
        if (id !== 'browser') return;
        if (!e.target.closest('[data-drag-handle]')) return;

        bringToFront(id);
        const pos = elementPositionsRef.current[id];
        dragOffsetRef.current = { x: e.clientX - pos.x, y: e.clientY - pos.y };
        isDraggingRef.current = true;
        activeDragElementRef.current = id;
        setActiveDragElement(id);
        window.addEventListener('mousemove', handleMouseDrag);
        window.addEventListener('mouseup', handleMouseUp);
    };

    const handleMouseDrag = (e) => {
        if (!isDraggingRef.current || !activeDragElementRef.current) return;
        const id = activeDragElementRef.current;
        const size = elementSizes[id];
        const width = window.innerWidth;
        const height = window.innerHeight;
        const x = Math.max(size.w / 2, Math.min(width - size.w / 2, e.clientX - dragOffsetRef.current.x));
        const y = Math.max(size.h / 2 + 60, Math.min(height - size.h / 2, e.clientY - dragOffsetRef.current.y));
        setElementPositions(prev => ({ ...prev, [id]: { x, y } }));
    };

    const handleMouseUp = () => {
        isDraggingRef.current = false;
        activeDragElementRef.current = null;
        setActiveDragElement(null);
        window.removeEventListener('mousemove', handleMouseDrag);
        window.removeEventListener('mouseup', handleMouseUp);
    };

    const handleMinimize = () => ipcRenderer.send('window-minimize');
    const handleMaximize = () => ipcRenderer.send('window-maximize');
    const handleCloseRequest = () => {
        const closeWindow = () => {
            if (isElectronRuntime) {
                ipcRenderer.send('window-close');
            } else {
                window.close();
            }
        };
        if (socket.connected) {
            socket.emit('shutdown', {}, () => closeWindow());
            setTimeout(closeWindow, 500);
        } else {
            closeWindow();
        }
    };

    const audioAmp = aiAudioData.reduce((a, b) => a + b, 0) / aiAudioData.length / 255;

    return (
        <div className="relative flex h-screen w-screen flex-col overflow-hidden bg-black text-slate-200 selection:bg-cyan-300/14 selection:text-slate-100">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(82,142,164,0.18),_transparent_22%),linear-gradient(180deg,_#090d11_0%,_#05070a_58%,_#030405_100%)]" />
            <div className="pointer-events-none absolute inset-0 opacity-[0.04]" style={{ backgroundImage: 'linear-gradient(rgba(92,124,138,0.12) 1px, transparent 1px), linear-gradient(90deg, rgba(92,124,138,0.12) 1px, transparent 1px)', backgroundSize: '52px 52px' }} />

            {!accessGranted && (
                <div className="fixed inset-0 z-[250] flex items-center justify-center bg-black/88 backdrop-blur-md">
                    <form onSubmit={submitAccessCode} className="hud-panel w-full max-w-sm p-8">
                        <div className="mb-6">
                            <div className="text-xs uppercase tracking-[0.3em] text-cyan-200/70">Edith Interface</div>
                            <h2 className="mt-3 text-2xl font-semibold text-slate-100">Access Code</h2>
                            <p className="mt-2 text-sm text-slate-400">Use your code or Face ID to bring Edith online.</p>
                        </div>
                        <input
                            type="password"
                            value={accessCodeInput}
                            onChange={(e) => setAccessCodeInput(e.target.value)}
                            placeholder="••••"
                            autoFocus
                            className="appearance-none w-full border border-cyan-200/14 bg-[#091018]/88 px-4 py-3 text-center text-xl tracking-[0.45em] text-slate-100 outline-none focus:border-cyan-200/28"
                        />
                        {accessError && (
                            <div className="mt-3 text-sm text-red-300">{accessError}</div>
                        )}
                        <button
                            type="submit"
                            disabled={!socketConnected || isVerifyingAccess}
                            className="mt-5 w-full border border-cyan-200/14 bg-cyan-100/[0.03] px-4 py-3 text-sm font-semibold uppercase tracking-[0.2em] text-slate-100 transition hover:bg-cyan-100/[0.05] disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {isVerifyingAccess ? 'Verifying' : 'Unlock'}
                        </button>
                        <div className="mt-4 border-t border-cyan-200/10 pt-4">
                            <div className="mb-2 text-[11px] uppercase tracking-[0.24em] text-slate-500">Face ID</div>
                            <div className="text-xs text-slate-400">
                                {faceAuthState.enrolled ? 'Reference face is enrolled.' : 'No face enrolled yet.'}
                            </div>
                            <div className="mt-3 grid grid-cols-2 gap-2">
                                <button
                                    type="button"
                                    onClick={() => handleFaceAction('verify_face')}
                                    disabled={!socketConnected || !faceAuthState.enrolled || isFaceBusy}
                                    className="border border-cyan-200/14 bg-black/35 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
                                >
                                    {isFaceBusy ? 'Scanning' : 'Use Face ID'}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => handleFaceAction('enroll_face')}
                                    disabled={!socketConnected || isFaceBusy}
                                    className="border border-cyan-200/14 bg-black/35 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
                                >
                                    {faceAuthState.enrolled ? 'Update Face' : 'Enroll Face'}
                                </button>
                            </div>
                        </div>
                    </form>
                </div>
            )}

            <div className="hud-panel z-50 mx-7 mt-5 flex items-center justify-between px-6 py-3 backdrop-blur-md select-none" style={{ WebkitAppRegion: 'drag' }}>
                <div className="flex items-center gap-4 pl-2">
                    <h1 className="text-lg font-bold tracking-[0.34em] text-slate-100">EDITH</h1>
                    <div className="border border-cyan-200/12 px-2 py-0.5 text-[10px] uppercase tracking-[0.24em] text-slate-400">
                        {status}
                    </div>
                    <div className={`border px-2 py-0.5 text-[10px] uppercase tracking-[0.24em] ${
                        spotifyState?.authenticated
                            ? 'text-cyan-200 border-cyan-300/30'
                            : spotifyState?.auth_pending
                                ? 'text-cyan-300/80 border-cyan-300/18'
                                : 'text-slate-400 border-cyan-200/10'
                    }`}>
                        {spotifyState?.authenticated
                            ? `Spotify: ${spotifyState?.preferred_device_name || 'Connected'}`
                            : spotifyState?.auth_pending
                                ? 'Spotify: Waiting'
                                : spotifyState?.configured
                                    ? 'Spotify: Ready'
                                    : 'Spotify: Off'}
                    </div>
                    {isVideoOn && (
                        <div className="border border-cyan-200/14 px-2 py-0.5 text-[10px] uppercase tracking-[0.24em] text-slate-200">
                            FPS: {fps}
                        </div>
                    )}
                </div>

                <div className="flex-1 flex justify-center mx-4">
                    <TopAudioBar audioData={micAudioData} />
                </div>

                <div className="flex items-center gap-2 pr-2" style={{ WebkitAppRegion: 'no-drag' }}>
                    <div className="flex items-center gap-1.5 px-2 font-mono text-[11px] text-slate-200/80">
                        <Clock size={12} className="text-slate-500/70" />
                        <span>{currentTime.toLocaleTimeString([], IST_TIME_FORMAT)}</span>
                    </div>
                    <button onClick={handleMinimize} className="p-1 text-slate-300 transition-colors hover:bg-cyan-100/[0.04]">
                        <Minus size={18} />
                    </button>
                    <button onClick={handleMaximize} className="p-1 text-slate-300 transition-colors hover:bg-cyan-100/[0.04]">
                        <div className="w-[14px] h-[14px] border-2 border-current rounded-[2px]" />
                    </button>
                    <button onClick={handleCloseRequest} className="p-1 text-red-400 transition-colors hover:bg-red-900/30">
                        <X size={18} />
                    </button>
                </div>
            </div>

            <div className="pointer-events-none absolute left-1/2 top-[94px] z-40 -translate-x-1/2 border border-slate-200/10 bg-[#0d1116]/80 px-4 py-1 text-[10px] uppercase tracking-[0.36em] text-slate-300">
                Project {currentProject?.toUpperCase()}
            </div>

            <div className="flex-1 relative z-10 px-6 pb-6 pt-20">
                <div className="mx-auto flex h-full max-w-[980px] flex-col items-center justify-center gap-3">
                    <div
                        id="visualizer"
                        className="relative flex items-center justify-center overflow-visible"
                        style={{
                            width: Math.min(720, elementSizes.visualizer.w + 36),
                            height: Math.max(300, elementSizes.visualizer.h + 18),
                            marginTop: '96px',
                        }}
                    >
                        <Visualizer
                            audioData={aiAudioData}
                            isListening={isConnected && !isMuted}
                            intensity={audioAmp}
                            width={elementSizes.visualizer.w}
                            height={elementSizes.visualizer.h}
                        />
                    </div>

                    <div
                        id="video"
                        className={`hud-panel relative mx-auto backdrop-blur-md transition-all duration-300 ${isVideoOn ? 'opacity-100 translate-y-0' : 'pointer-events-none -translate-y-2 opacity-0 h-0 overflow-hidden border-transparent p-0'}`}
                        style={{ zIndex: 20 }}
                    >
                        <div className="relative aspect-video w-[min(28rem,78vw)] overflow-hidden bg-black/80">
                            <video ref={videoRef} autoPlay muted className="absolute inset-0 w-full h-full object-cover opacity-0" />
                            <div className="absolute left-2 top-2 z-10 border border-cyan-200/14 bg-[#061018]/75 px-2 py-0.5 text-[10px] font-bold tracking-wider text-slate-200">CAM_01</div>
                            <canvas ref={canvasRef} className="absolute inset-0 w-full h-full opacity-85" />
                        </div>
                    </div>

                    {showSettings && (
                        <SettingsWindow
                            socket={socket}
                            micDevices={micDevices}
                            speakerDevices={speakerDevices}
                            webcamDevices={webcamDevices}
                            selectedMicId={selectedMicId}
                            setSelectedMicId={setSelectedMicId}
                            selectedSpeakerId={selectedSpeakerId}
                            setSelectedSpeakerId={setSelectedSpeakerId}
                            selectedWebcamId={selectedWebcamId}
                            setSelectedWebcamId={setSelectedWebcamId}
                            handleFileUpload={handleFileUpload}
                            handleRememberMemory={handleRememberMemory}
                            spotifyState={spotifyState}
                            onSpotifyConnect={handleSpotifyConnect}
                            onSpotifyControl={handleSpotifyControl}
                            onClose={() => setShowSettings(false)}
                        />
                    )}

                    {showHistory && (
                        <ConversationHistoryPanel
                            sessions={conversationArchive}
                            onClose={() => setShowHistory(false)}
                        />
                    )}

                    {showCommunications && (
                        <CommunicationsPanel
                            items={communications}
                            onClose={() => setShowCommunications(false)}
                        />
                    )}

                    <ChatModule
                        messages={messages}
                        inputValue={inputValue}
                        setInputValue={setInputValue}
                        handleSend={handleSend}
                        isModularMode={false}
                        activeDragElement={null}
                        position={elementPositions.chat}
                        width={elementSizes.chat.w}
                        height={elementSizes.chat.h}
                        onMouseDown={() => {}}
                    />

                    <div className="z-20 flex justify-center pt-2">
                        <ToolsModule
                            isConnected={isConnected}
                            isMuted={isMuted}
                            isVideoOn={isVideoOn}
                            showSettings={showSettings}
                            showHistory={showHistory}
                            showCommunications={showCommunications}
                            onTogglePower={togglePower}
                            onToggleMute={toggleMute}
                            onToggleVideo={toggleVideo}
                            onToggleSettings={() => setShowSettings(!showSettings)}
                            onToggleHistory={toggleHistory}
                            onToggleCommunications={toggleCommunications}
                            position={null}
                            onMouseDown={() => {}}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}

export default App;
