import React from 'react';
import { History, Mail, Mic, MicOff, Power, Settings, Video, VideoOff } from 'lucide-react';

const buttonClass = 'flex h-10 w-10 items-center justify-center border appearance-none text-slate-200 transition-all duration-150 rounded-xl';

const ToolsModule = ({
    isConnected,
    isMuted,
    isVideoOn,
    showSettings,
    showHistory,
    showCommunications,
    onTogglePower,
    onToggleMute,
    onToggleVideo,
    onToggleSettings,
    onToggleHistory,
    onToggleCommunications,
    position,
    onMouseDown,
}) => {
    return (
        <div
            id="tools"
            onMouseDown={onMouseDown}
            className="hud-panel px-5 py-3 backdrop-blur-sm"
            style={position ? {
                left: position.x,
                top: position.y,
                transform: 'translate(-50%, -50%)',
                pointerEvents: 'auto',
                position: 'absolute',
            } : {
                pointerEvents: 'auto',
                position: 'relative',
            }}
        >
            <div className="flex items-center justify-center gap-4">
                <button
                    onClick={onTogglePower}
                    className={`${buttonClass} ${isConnected ? 'border-slate-100/18 bg-slate-100/[0.04] text-slate-100' : 'border-slate-200/[0.08] bg-[#0a0f14] text-slate-500'}`}
                >
                    <Power size={18} />
                </button>

                <button
                    onClick={onToggleMute}
                    disabled={!isConnected}
                    className={`${buttonClass} ${!isConnected ? 'cursor-not-allowed border-slate-200/[0.05] bg-[#0a0f14] text-slate-700' : isMuted ? 'border-red-400/24 bg-red-500/[0.06] text-red-300' : 'border-slate-200/[0.1] bg-[#0a0f14] text-slate-200'}`}
                >
                    {isMuted ? <MicOff size={18} /> : <Mic size={18} />}
                </button>

                <button
                    onClick={onToggleVideo}
                    className={`${buttonClass} ${isVideoOn ? 'border-slate-100/18 bg-slate-100/[0.04] text-slate-100' : 'border-slate-200/[0.08] bg-[#0a0f14] text-slate-500'}`}
                >
                    {isVideoOn ? <Video size={18} /> : <VideoOff size={18} />}
                </button>

                <button
                    onClick={onToggleSettings}
                    className={`${buttonClass} ${showSettings ? 'border-slate-100/18 bg-slate-100/[0.04] text-slate-100' : 'border-slate-200/[0.08] bg-[#0a0f14] text-slate-500'}`}
                >
                    <Settings size={18} />
                </button>

                <button
                    onClick={onToggleHistory}
                    className={`${buttonClass} ${showHistory ? 'border-slate-100/18 bg-slate-100/[0.04] text-slate-100' : 'border-slate-200/[0.08] bg-[#0a0f14] text-slate-500'}`}
                >
                    <History size={18} />
                </button>

                <button
                    onClick={onToggleCommunications}
                    className={`${buttonClass} ${showCommunications ? 'border-slate-100/18 bg-slate-100/[0.04] text-slate-100' : 'border-slate-200/[0.08] bg-[#0a0f14] text-slate-500'}`}
                >
                    <Mail size={18} />
                </button>
            </div>
        </div>
    );
};

export default ToolsModule;
