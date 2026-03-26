import React, { useEffect, useState } from 'react';
import { X } from 'lucide-react';

const TOOLS = [
    { id: 'run_web_agent', label: 'Web Agent' },
    { id: 'create_directory', label: 'Create Folder' },
    { id: 'create_finder_file', label: 'Create Finder File' },
    { id: 'open_mac_app', label: 'Open Mac App' },
    { id: 'close_mac_app', label: 'Close Mac App' },
    { id: 'shutdown_edith', label: 'Shutdown Edith' },
    { id: 'generate_formatted_document', label: 'Generate Document' },
    { id: 'generate_document_bundle', label: 'Generate Bundle' },
    { id: 'generate_image', label: 'Generate Image' },
    { id: 'send_email', label: 'Send Email' },
    { id: 'send_text_message', label: 'Send Text Message' },
    { id: 'create_task', label: 'Create Task' },
    { id: 'list_tasks', label: 'List Tasks' },
    { id: 'complete_task', label: 'Complete Task' },
    { id: 'schedule_reminder', label: 'Schedule Reminder' },
    { id: 'list_reminders', label: 'List Reminders' },
    { id: 'create_calendar_event', label: 'Create Calendar Event' },
    { id: 'list_calendar_events', label: 'List Calendar Events' },
    { id: 'set_voice_mode', label: 'Set Voice Mode' },
    { id: 'run_browser_workflow', label: 'Browser Workflow' },
    { id: 'read_clipboard', label: 'Read Clipboard' },
    { id: 'copy_to_clipboard', label: 'Copy Clipboard' },
    { id: 'list_mac_printers', label: 'List Printers' },
    { id: 'print_file', label: 'Print File' },
    { id: 'write_file', label: 'Write File' },
    { id: 'read_directory', label: 'Read Directory' },
    { id: 'read_file', label: 'Read File' },
    { id: 'create_project', label: 'Create Project' },
    { id: 'switch_project', label: 'Switch Project' },
    { id: 'list_projects', label: 'List Projects' },
    { id: 'spotify_playback', label: 'Spotify Playback' },
    { id: 'spotify_get_status', label: 'Spotify Status' },
    { id: 'spotify_dj', label: 'Spotify DJ' },
    { id: 'browser_list_tabs', label: 'Browser Tabs' },
    { id: 'browser_navigate', label: 'Browser Navigate' },
    { id: 'browser_click', label: 'Browser Click' },
    { id: 'browser_fill', label: 'Browser Fill' },
    { id: 'browser_keypress', label: 'Browser Keypress' },
    { id: 'browser_screenshot', label: 'Browser Screenshot' },
    { id: 'browser_dom', label: 'Browser DOM' },
    { id: 'recall_memory', label: 'Recall Memory' },
    { id: 'get_current_time', label: 'Current Time' },
    { id: 'list_devices', label: 'List Devices' },
    { id: 'switch_device', label: 'Switch Device' },
    { id: 'copy_file', label: 'Copy File' },
    { id: 'open_file', label: 'Open File' },
    { id: 'edit_file', label: 'Edit File' },
    { id: 'move_file', label: 'Move File' },
    { id: 'delete_file', label: 'Delete File' },
    { id: 'open_conversation_log', label: 'Open Conversation Log' },
];

const SettingsWindow = ({
    socket,
    micDevices,
    speakerDevices,
    webcamDevices,
    selectedMicId,
    setSelectedMicId,
    selectedSpeakerId,
    setSelectedSpeakerId,
    selectedWebcamId,
    setSelectedWebcamId,
    handleFileUpload,
    handleRememberMemory,
    spotifyState,
    onSpotifyConnect,
    onSpotifyControl,
    onClose,
}) => {
    const [profile, setProfile] = useState({
        location_label: '',
        city: '',
        region: '',
        country: '',
        timezone: 'Asia/Kolkata',
        voice_mode: 'standard',
    });
    const [serviceTokens, setServiceTokens] = useState({
        mem0_api_key: '',
        mem0_user_id: 'sir',
        mem0_app_id: 'edith',
        mem0_org_id: '',
        mem0_project_id: '',
        pollinations_api_key: '',
        clicksend_username: '',
        clicksend_api_key: '',
        clicksend_sms_from: '',
        clicksend_from_email: '',
        nexg_sms_url: '',
        nexg_sms_username: '',
        nexg_sms_password: '',
        nexg_sms_from: '',
        nexg_dlt_content_template_id: '',
        nexg_dlt_principal_entity_id: '',
        nexg_dlt_telemarketer_id: '',
        mem0_configured: false,
        clicksend_configured: false,
        nexg_configured: false,
    });
    const [memoryNote, setMemoryNote] = useState('');
    const [spotifyQuery, setSpotifyQuery] = useState('');
    const [spotifyVolume, setSpotifyVolume] = useState(75);

    useEffect(() => {
        const handleSettings = (settings) => {
            if (settings?.profile) {
                setProfile(prev => ({ ...prev, ...settings.profile }));
            }
            if (settings?.service_tokens) {
                setServiceTokens(prev => ({ ...prev, ...settings.service_tokens }));
            }
        };

        socket.emit('get_settings');
        socket.on('settings', handleSettings);
        return () => socket.off('settings', handleSettings);
    }, [socket]);

    const submitMemoryNote = () => {
        const cleaned = memoryNote.trim();
        if (!cleaned) {
            return;
        }
        handleRememberMemory(cleaned);
        setMemoryNote('');
    };

    const submitSpotifyPlay = () => {
        const cleaned = spotifyQuery.trim();
        if (!cleaned) {
            return;
        }
        onSpotifyControl('play', { query: cleaned });
    };

    const saveProfile = () => {
        socket.emit('update_settings', { profile });
    };

    const saveServiceTokens = () => {
        socket.emit('update_settings', {
            service_tokens: {
                mem0_api_key: serviceTokens.mem0_api_key,
                mem0_user_id: serviceTokens.mem0_user_id,
                mem0_app_id: serviceTokens.mem0_app_id,
                mem0_org_id: serviceTokens.mem0_org_id,
                mem0_project_id: serviceTokens.mem0_project_id,
                pollinations_api_key: serviceTokens.pollinations_api_key,
                clicksend_username: serviceTokens.clicksend_username,
                clicksend_api_key: serviceTokens.clicksend_api_key,
                clicksend_sms_from: serviceTokens.clicksend_sms_from,
                clicksend_from_email: serviceTokens.clicksend_from_email,
                nexg_sms_url: serviceTokens.nexg_sms_url,
                nexg_sms_username: serviceTokens.nexg_sms_username,
                nexg_sms_password: serviceTokens.nexg_sms_password,
                nexg_sms_from: serviceTokens.nexg_sms_from,
                nexg_dlt_content_template_id: serviceTokens.nexg_dlt_content_template_id,
                nexg_dlt_principal_entity_id: serviceTokens.nexg_dlt_principal_entity_id,
                nexg_dlt_telemarketer_id: serviceTokens.nexg_dlt_telemarketer_id,
            },
        });
    };

    return (
        <div className="absolute right-8 top-16 z-50 max-h-[calc(100vh-7rem)] w-80 overflow-y-auto border border-cyan-200/[0.08] bg-[#05090d]/92 p-4 shadow-[0_0_30px_rgba(90,170,190,0.08)] backdrop-blur-xl">
            <div className="flex justify-between items-center mb-4 border-b border-stone-700/70 pb-2">
                <h2 className="text-slate-100 font-bold text-sm uppercase tracking-wider">Settings</h2>
                <button onClick={onClose} className="text-slate-500 hover:text-slate-200">
                    <X size={16} />
                </button>
            </div>

            <div className="mb-4">
                <h3 className="text-slate-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Microphone</h3>
                <select
                    value={selectedMicId}
                    onChange={(e) => setSelectedMicId(e.target.value)}
                    className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 p-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                >
                    {micDevices.map((device, i) => (
                        <option key={device.deviceId} value={device.deviceId}>
                            {device.label || `Microphone ${i + 1}`}
                        </option>
                    ))}
                </select>
            </div>

            <div className="mb-4">
                <h3 className="text-slate-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Speaker</h3>
                <select
                    value={selectedSpeakerId}
                    onChange={(e) => setSelectedSpeakerId(e.target.value)}
                    className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 p-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                >
                    {speakerDevices.map((device, i) => (
                        <option key={device.deviceId} value={device.deviceId}>
                            {device.label || `Speaker ${i + 1}`}
                        </option>
                    ))}
                </select>
            </div>

            <div className="mb-6">
                <h3 className="text-slate-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Webcam</h3>
                <select
                    value={selectedWebcamId}
                    onChange={(e) => setSelectedWebcamId(e.target.value)}
                    className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 p-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                >
                    {webcamDevices.map((device, i) => (
                        <option key={device.deviceId} value={device.deviceId}>
                            {device.label || `Camera ${i + 1}`}
                        </option>
                    ))}
                </select>
            </div>

            <div className="mb-6">
                <h3 className="text-slate-400 font-bold mb-3 text-xs uppercase tracking-wider opacity-80">Tool Confirmations</h3>
                <div className="space-y-2 max-h-40 overflow-y-auto pr-2">
                    {TOOLS.map(tool => {
                        return (
                            <div key={tool.id} className="flex items-center justify-between border border-cyan-200/[0.06] bg-black/25 p-2 text-xs">
                                <span className="text-slate-300">{tool.label}</span>
                                <div className="border border-cyan-200/16 bg-cyan-100/[0.06] px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-200">
                                    Enabled
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            <div className="mb-6">
                <h3 className="text-slate-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Location</h3>
                <div className="border border-cyan-200/[0.06] bg-black/25 p-3 space-y-2">
                    <input
                        value={profile.location_label}
                        onChange={(e) => setProfile(prev => ({ ...prev, location_label: e.target.value }))}
                        placeholder="Home location label, e.g. South Delhi"
                        className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                    />
                    <div className="grid grid-cols-2 gap-2">
                        <input
                            value={profile.city}
                            onChange={(e) => setProfile(prev => ({ ...prev, city: e.target.value }))}
                            placeholder="City"
                            className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                        />
                        <input
                            value={profile.region}
                            onChange={(e) => setProfile(prev => ({ ...prev, region: e.target.value }))}
                            placeholder="State / Region"
                            className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        <input
                            value={profile.country}
                            onChange={(e) => setProfile(prev => ({ ...prev, country: e.target.value }))}
                            placeholder="Country"
                            className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                        />
                        <input
                            value={profile.timezone}
                            onChange={(e) => setProfile(prev => ({ ...prev, timezone: e.target.value }))}
                            placeholder="Timezone"
                            className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                        />
                    </div>
                    <select
                        value={profile.voice_mode}
                        onChange={(e) => setProfile(prev => ({ ...prev, voice_mode: e.target.value }))}
                        className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                    >
                        <option value="standard">Voice Mode: Standard</option>
                        <option value="study">Voice Mode: Study</option>
                        <option value="soft">Voice Mode: Soft</option>
                        <option value="command">Voice Mode: Command</option>
                        <option value="combat">Voice Mode: Combat</option>
                    </select>
                    <button
                        onClick={saveProfile}
                        className="w-full border border-cyan-200/[0.1] bg-cyan-100/[0.03] px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-100 hover:bg-cyan-100/[0.05]"
                    >
                        Save Location
                    </button>
                </div>
            </div>

            <div className="mb-6">
                <h3 className="text-slate-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Spotify</h3>
                <div className="border border-cyan-200/[0.06] bg-black/25 p-3">
                    <div className="text-[11px] text-slate-300 leading-relaxed">
                        {!spotifyState?.configured && 'Spotify credentials are not configured yet.'}
                        {spotifyState?.configured && !spotifyState?.authenticated && !spotifyState?.auth_pending && 'Spotify is ready to connect.'}
                        {spotifyState?.auth_pending && 'Spotify authorization is in progress. Finish it in your browser.'}
                        {spotifyState?.authenticated && `Spotify connected${spotifyState?.preferred_device_name ? ` · Device: ${spotifyState.preferred_device_name}` : ''}.`}
                        {spotifyState?.auth_error && !spotifyState?.authenticated && ` ${spotifyState.auth_error}`}
                    </div>
                    <button
                        onClick={onSpotifyConnect}
                        className="mt-3 w-full border border-cyan-200/[0.1] bg-cyan-100/[0.03] px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-100 hover:bg-cyan-100/[0.05]"
                    >
                        {spotifyState?.authenticated ? 'Reconnect Spotify' : 'Connect Spotify'}
                    </button>

                    <div className="mt-3 flex gap-2">
                        <input
                            value={spotifyQuery}
                            onChange={(e) => setSpotifyQuery(e.target.value)}
                            placeholder="Play a song, artist, or vibe..."
                            className="appearance-none flex-1 border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                        />
                        <button
                            onClick={submitSpotifyPlay}
                            className="border border-cyan-200/[0.1] bg-cyan-100/[0.03] px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-100 hover:bg-cyan-100/[0.05]"
                        >
                            Play
                        </button>
                    </div>

                    <div className="mt-3 grid grid-cols-3 gap-2">
                        <button onClick={() => onSpotifyControl('previous')} className="border border-cyan-200/[0.1] bg-black/45 px-2 py-2 text-[11px] text-slate-100 hover:bg-cyan-100/[0.05]">Prev</button>
                        <button onClick={() => onSpotifyControl('pause')} className="border border-cyan-200/[0.1] bg-black/45 px-2 py-2 text-[11px] text-slate-100 hover:bg-cyan-100/[0.05]">Pause</button>
                        <button onClick={() => onSpotifyControl('next')} className="border border-cyan-200/[0.1] bg-black/45 px-2 py-2 text-[11px] text-slate-100 hover:bg-cyan-100/[0.05]">Next</button>
                    </div>

                    <div className="mt-3">
                        <div className="mb-2 flex items-center justify-between text-[11px] uppercase tracking-[0.18em] text-slate-400">
                            <span>Volume</span>
                            <span>{spotifyVolume}%</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <input
                                type="range"
                                min="0"
                                max="100"
                                step="1"
                                value={spotifyVolume}
                                onChange={(e) => setSpotifyVolume(Number(e.target.value))}
                                className="w-full accent-cyan-200"
                            />
                            <button
                                onClick={() => onSpotifyControl('volume', { volume_percent: spotifyVolume })}
                                className="border border-cyan-200/[0.1] bg-cyan-100/[0.03] px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-100 hover:bg-cyan-100/[0.05]"
                            >
                                Set
                            </button>
                        </div>
                    </div>

                    <button
                        onClick={() => onSpotifyControl('dj', { query: spotifyQuery.trim() || undefined })}
                        className="mt-3 w-full border border-cyan-200/[0.1] bg-cyan-100/[0.03] px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-100 hover:bg-cyan-100/[0.05]"
                    >
                        DJ This
                    </button>
                </div>
            </div>

            <div className="mb-6">
                <h3 className="text-slate-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Integrations</h3>
                <div className="border border-cyan-200/[0.06] bg-black/25 p-3 space-y-2">
                    <div className="text-[11px] text-slate-300 leading-relaxed">
                        {serviceTokens.mem0_configured
                            ? 'Mem0 memory is configured. Edith will use it as the persistent memory layer.'
                            : serviceTokens.nexg_configured
                                ? 'NexG SMS configured. ClickSend email is still available.'
                                : serviceTokens.clicksend_configured
                                    ? 'ClickSend email is configured. NexG SMS is not configured yet.'
                                    : 'Messaging providers and memory are not fully configured yet.'}
                    </div>
                    <input
                        value={serviceTokens.mem0_api_key}
                        onChange={(e) => setServiceTokens(prev => ({ ...prev, mem0_api_key: e.target.value }))}
                        placeholder="Mem0 API Key"
                        type="password"
                        className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                    />
                    <input
                        value={serviceTokens.mem0_user_id}
                        onChange={(e) => setServiceTokens(prev => ({ ...prev, mem0_user_id: e.target.value }))}
                        placeholder="Mem0 User ID"
                        className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                    />
                    <input
                        value={serviceTokens.mem0_app_id}
                        onChange={(e) => setServiceTokens(prev => ({ ...prev, mem0_app_id: e.target.value }))}
                        placeholder="Mem0 App ID"
                        className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                    />
                    <div className="grid grid-cols-2 gap-2">
                        <input
                            value={serviceTokens.mem0_org_id}
                            onChange={(e) => setServiceTokens(prev => ({ ...prev, mem0_org_id: e.target.value }))}
                            placeholder="Mem0 Org ID"
                            className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                        />
                        <input
                            value={serviceTokens.mem0_project_id}
                            onChange={(e) => setServiceTokens(prev => ({ ...prev, mem0_project_id: e.target.value }))}
                            placeholder="Mem0 Project ID"
                            className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                        />
                    </div>
                    <input
                        value={serviceTokens.nexg_sms_url}
                        onChange={(e) => setServiceTokens(prev => ({ ...prev, nexg_sms_url: e.target.value }))}
                        placeholder="NexG SMS URL"
                        className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                    />
                    <div className="grid grid-cols-2 gap-2">
                        <input
                            value={serviceTokens.nexg_sms_username}
                            onChange={(e) => setServiceTokens(prev => ({ ...prev, nexg_sms_username: e.target.value }))}
                            placeholder="NexG Username"
                            className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                        />
                        <input
                            value={serviceTokens.nexg_sms_password}
                            onChange={(e) => setServiceTokens(prev => ({ ...prev, nexg_sms_password: e.target.value }))}
                            placeholder="NexG Password"
                            type="password"
                            className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        <input
                            value={serviceTokens.nexg_sms_from}
                            onChange={(e) => setServiceTokens(prev => ({ ...prev, nexg_sms_from: e.target.value }))}
                            placeholder="NexG Sender"
                            className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                        />
                        <input
                            value={serviceTokens.nexg_dlt_content_template_id}
                            onChange={(e) => setServiceTokens(prev => ({ ...prev, nexg_dlt_content_template_id: e.target.value }))}
                            placeholder="DLT Template ID"
                            className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        <input
                            value={serviceTokens.nexg_dlt_principal_entity_id}
                            onChange={(e) => setServiceTokens(prev => ({ ...prev, nexg_dlt_principal_entity_id: e.target.value }))}
                            placeholder="DLT Principal Entity ID"
                            className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                        />
                        <input
                            value={serviceTokens.nexg_dlt_telemarketer_id}
                            onChange={(e) => setServiceTokens(prev => ({ ...prev, nexg_dlt_telemarketer_id: e.target.value }))}
                            placeholder="DLT Telemarketer ID"
                            className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                        />
                    </div>
                    <input
                        value={serviceTokens.clicksend_username}
                        onChange={(e) => setServiceTokens(prev => ({ ...prev, clicksend_username: e.target.value }))}
                        placeholder="ClickSend Username (email)"
                        className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                    />
                    <input
                        value={serviceTokens.clicksend_api_key}
                        onChange={(e) => setServiceTokens(prev => ({ ...prev, clicksend_api_key: e.target.value }))}
                        placeholder="ClickSend API Key"
                        type="password"
                        className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                    />
                    <div className="grid grid-cols-2 gap-2">
                        <input
                            value={serviceTokens.clicksend_sms_from}
                            onChange={(e) => setServiceTokens(prev => ({ ...prev, clicksend_sms_from: e.target.value }))}
                            placeholder="ClickSend SMS From"
                            className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                        />
                        <input
                            value={serviceTokens.clicksend_from_email}
                            onChange={(e) => setServiceTokens(prev => ({ ...prev, clicksend_from_email: e.target.value }))}
                            placeholder="ClickSend From Email"
                            className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                        />
                    </div>
                    <div className="text-[10px] leading-relaxed text-slate-400">
                        SMS uses NexG query API when configured. Email uses ClickSend SMTP with your username and API key.
                    </div>
                    <input
                        value={serviceTokens.pollinations_api_key}
                        onChange={(e) => setServiceTokens(prev => ({ ...prev, pollinations_api_key: e.target.value }))}
                        placeholder="Pollinations API Key (optional)"
                        className="appearance-none w-full border border-cyan-200/[0.1] bg-black/45 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                    />
                    <button
                        onClick={saveServiceTokens}
                        className="w-full border border-cyan-200/[0.1] bg-cyan-100/[0.03] px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-100 hover:bg-cyan-100/[0.05]"
                    >
                        Save Integrations
                    </button>
                </div>
            </div>

            <div className="mb-6">
                <h3 className="text-slate-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Remember This</h3>
                <textarea
                    value={memoryNote}
                    onChange={(e) => setMemoryNote(e.target.value)}
                    placeholder="Write something Edith should remember across conversations..."
                    className="appearance-none w-full min-h-24 resize-y border border-cyan-200/[0.1] bg-black/45 p-3 text-xs text-slate-100 outline-none focus:border-cyan-300/24"
                />
                <button
                    onClick={submitMemoryNote}
                    className="mt-2 w-full border border-cyan-200/[0.1] bg-cyan-100/[0.03] px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-100 hover:bg-cyan-100/[0.05]"
                >
                    Save Memory
                </button>
            </div>

            <div>
                <h3 className="text-slate-400 font-bold mb-2 text-xs uppercase tracking-wider opacity-80">Memory Data</h3>
                <input
                    type="file"
                    accept=".txt"
                    onChange={handleFileUpload}
                    className="w-full cursor-pointer border border-cyan-200/[0.1] bg-black/45 p-2 text-xs text-slate-100 file:mr-2 file:border-0 file:bg-slate-800/90 file:px-2 file:py-1 file:text-[10px] file:font-semibold file:text-slate-100 hover:file:bg-slate-700/90"
                />
            </div>
        </div>
    );
};

export default SettingsWindow;
