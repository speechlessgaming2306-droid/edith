import React from 'react';

const Visualizer = ({ audioData, isListening, intensity = 0, width = 600, height = 400 }) => {
    const average = audioData?.length ? audioData.reduce((sum, value) => sum + value, 0) / audioData.length / 255 : 0;
    const pulse = Math.min(1, Math.max(intensity, average));
    const energy = isListening ? pulse : pulse * 0.45;
    const blobScale = 1 + energy * 0.34;
    const innerBlobScale = 1 + energy * 0.22;
    const shimmerShift = 48 + energy * 24;
    const size = Math.min(width, height) * 0.86;
    const driftDuration = `${Math.max(3.2, 5.8 - energy * 2.2)}s`;
    const pulseDuration = `${Math.max(1.8, 3.1 - energy * 1.1)}s`;

    return (
        <div className="relative flex items-center justify-center" style={{ width, height }}>
            <div className="pointer-events-none flex flex-col items-center gap-6">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_rgba(248,252,255,0.10),_transparent_20%),radial-gradient(circle_at_center,_rgba(178,198,228,0.10),_transparent_38%),radial-gradient(circle_at_center,_rgba(102,126,164,0.08),_transparent_58%)]" />
                <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
                    <div
                        className="visualizer-ambient absolute inset-[-16%] rounded-full"
                        style={{
                            opacity: isListening ? 0.95 : 0.55,
                            transform: `scale(${1.06 + energy * 0.32})`,
                            background: 'radial-gradient(circle at center, rgba(242,247,255,0.20) 0%, rgba(180,205,235,0.12) 28%, rgba(116,148,196,0.07) 54%, transparent 76%)',
                            filter: `blur(${18 + energy * 18}px)`,
                            animationDuration: driftDuration,
                        }}
                    />
                    <div
                        className="visualizer-blob absolute inset-0"
                        style={{
                            transform: `scale(${blobScale})`,
                            background: 'radial-gradient(circle at 34% 28%, rgba(255,255,255,0.92) 0%, rgba(233,242,255,0.76) 12%, rgba(166,194,229,0.58) 30%, rgba(83,108,144,0.34) 58%, rgba(15,20,28,0.08) 82%, transparent 100%)',
                            boxShadow: isListening
                                ? `0 0 ${34 + energy * 26}px rgba(210, 228, 248, 0.12), inset 0 -18px 34px rgba(48, 70, 102, 0.34)`
                                : '0 0 18px rgba(210, 228, 248, 0.05), inset 0 -14px 26px rgba(42, 60, 88, 0.20)',
                            animationDuration: `${driftDuration}, ${pulseDuration}`,
                        }}
                    />
                    <div
                        className="visualizer-blob-inner absolute inset-[15%]"
                        style={{
                            transform: `scale(${innerBlobScale})`,
                            background: `radial-gradient(circle at ${shimmerShift}% 32%, rgba(255,255,255,0.72) 0%, rgba(230,240,252,0.48) 16%, rgba(135,162,198,0.20) 44%, transparent 72%)`,
                            opacity: isListening ? 0.94 : 0.55,
                            animationDuration: `${Math.max(3.6, 6.8 - energy * 2.3)}s, ${Math.max(1.6, 2.7 - energy * 0.8)}s`,
                        }}
                    />
                    <div className={`absolute h-3.5 w-3.5 rounded-full ${isListening ? 'bg-slate-50/90' : 'bg-slate-400/70'}`} />
                </div>

                <div className="flex flex-col items-center gap-2 pt-5">
                    <div
                        className="font-bold tracking-[0.42em] text-slate-100"
                        style={{ fontSize: Math.min(width, height) * 0.075 }}
                    >
                        EDITH
                    </div>
                    <div className="text-[10px] uppercase tracking-[0.46em] text-slate-400">
                        {isListening ? 'Listening' : 'Standby'}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default React.memo(Visualizer);
