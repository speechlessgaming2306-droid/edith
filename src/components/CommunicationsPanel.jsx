import React from 'react';

const formatTime = (timestamp) => {
    if (!timestamp) return 'Unknown';
    return new Date(timestamp * 1000).toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'Asia/Kolkata',
    });
};

const CommunicationsPanel = ({ items, onClose }) => {
    return (
        <div className="hud-panel absolute left-6 top-24 z-[120] w-[min(34rem,92vw)] px-5 py-5 backdrop-blur-md">
            <div className="mb-4 flex items-center justify-between">
                <div>
                    <div className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Comms</div>
                    <div className="mt-1 text-lg font-semibold text-slate-100">Communications</div>
                </div>
                <button
                    onClick={onClose}
                    className="border border-slate-200/10 bg-black/30 px-3 py-1 text-xs uppercase tracking-[0.2em] text-slate-300 transition hover:bg-slate-100/[0.04]"
                >
                    Close
                </button>
            </div>

            <div className="max-h-[70vh] space-y-4 overflow-y-auto pr-1 scrollbar-hide">
                {items.length === 0 && (
                    <div className="border border-slate-200/8 bg-black/25 px-4 py-4 text-sm text-slate-400">
                        No communications logged yet.
                    </div>
                )}

                {items.map((item, index) => (
                    <div key={`${item.id || index}`} className="border border-slate-200/8 bg-black/20">
                        <div className="border-b border-slate-200/8 px-4 py-3">
                            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">
                                {item.channel || 'message'} / {item.direction || 'log'} / {item.status || 'logged'} / {formatTime(item.created_at)}
                            </div>
                            <div className="mt-1 text-sm text-slate-200">
                                {(item.sender || item.recipient || 'Unknown')} {item.subject ? `- ${item.subject}` : ''}
                            </div>
                        </div>
                        <div className="space-y-3 px-4 py-4">
                            <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-200">
                                {item.body || '(No body)'}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default CommunicationsPanel;
