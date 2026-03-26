import React from 'react';

const formatSessionTime = (timestamp) => {
    if (!timestamp) return 'Unknown';
    return new Date(timestamp * 1000).toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'Asia/Kolkata',
    });
};

const ConversationHistoryPanel = ({ sessions, onClose }) => {
    return (
        <div className="hud-panel absolute right-6 top-24 z-[120] w-[min(34rem,92vw)] px-5 py-5 backdrop-blur-md">
            <div className="mb-4 flex items-center justify-between">
                <div>
                    <div className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Archive</div>
                    <div className="mt-1 text-lg font-semibold text-slate-100">Previous Conversations</div>
                </div>
                <button
                    onClick={onClose}
                    className="border border-slate-200/10 bg-black/30 px-3 py-1 text-xs uppercase tracking-[0.2em] text-slate-300 transition hover:bg-slate-100/[0.04]"
                >
                    Close
                </button>
            </div>

            <div className="max-h-[70vh] space-y-4 overflow-y-auto pr-1 scrollbar-hide">
                {sessions.length === 0 && (
                    <div className="border border-slate-200/8 bg-black/25 px-4 py-4 text-sm text-slate-400">
                        No archived conversations yet.
                    </div>
                )}

                {sessions.map((session, index) => (
                    <div key={`${session.started_at}-${index}`} className="border border-slate-200/8 bg-black/20">
                        <div className="border-b border-slate-200/8 px-4 py-3">
                            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">
                                {session.conversation ? `Conversation ${session.conversation}` : 'Conversation'} / {session.project || 'Temp'} / {formatSessionTime(session.started_at)}
                            </div>
                        </div>
                        <div className="space-y-3 px-4 py-4">
                            {(session.messages || []).map((msg, msgIndex) => (
                                <div key={msgIndex} className="border-l border-slate-200/10 pl-3">
                                    <div className="text-[11px] uppercase tracking-[0.22em] text-slate-500">
                                        {msg.sender}
                                    </div>
                                    <div className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-slate-200">
                                        {msg.text}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default ConversationHistoryPanel;
