import React, { useEffect, useRef } from 'react';

const ChatModule = ({
    messages,
    inputValue,
    setInputValue,
    handleSend,
    isModularMode,
    activeDragElement,
    position,
    width = 672,
    height,
    onMouseDown
}) => {
    const messagesEndRef = useRef(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
    }, [messages]);

    return (
        <div
            id="chat"
            onMouseDown={onMouseDown}
            className={`hud-panel pointer-events-auto px-6 py-5 transition-all duration-200 ${
                isModularMode ? 'absolute' : 'relative w-full'
            } ${
                isModularMode ? (activeDragElement === 'chat' ? 'ring-2 ring-cyan-300/35' : 'ring-1 ring-cyan-200/8') : ''
            }`}
            style={isModularMode ? {
                left: position.x,
                top: position.y,
                transform: 'translate(-50%, 0)',
                width,
                height,
            } : {
                width,
                height,
            }}
        >
            <div className="hud-accent-line absolute inset-x-0 top-0 h-px" />

            <div
                className="relative z-10 mb-4 flex flex-col gap-3 overflow-y-auto pr-1"
                style={{ height: height ? `calc(${height}px - 92px)` : '20rem' }}
            >
                {messages.slice(-20).map((msg, i) => (
                    <div key={i} className="border-l border-slate-200/10 pl-3 py-1.5">
                        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.24em] text-slate-500">
                            <span>{msg.sender}</span>
                            <span className="text-slate-700">/</span>
                            <span>{msg.time}</span>
                        </div>
                        <div className="mt-2 whitespace-pre-wrap text-[15px] leading-7 text-slate-100">
                            {msg.text}
                        </div>
                    </div>
                ))}
                <div ref={messagesEndRef} />
            </div>

            <div className="absolute bottom-4 left-5 right-5 z-10">
                <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleSend}
                    placeholder=">"
                    className="appearance-none w-full border border-slate-200/10 bg-[#0d1116]/86 px-4 py-3 font-mono text-[15px] text-slate-100 outline-none transition-all placeholder:text-slate-500 focus:border-slate-200/16"
                />
            </div>
        </div>
    );
};

export default ChatModule;
