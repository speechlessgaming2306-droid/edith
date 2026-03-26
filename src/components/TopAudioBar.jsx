import React from 'react';

const TopAudioBar = ({ audioData }) => {
    const average = audioData?.length ? audioData.reduce((sum, value) => sum + value, 0) / audioData.length / 255 : 0;
    const width = `${Math.max(8, Math.min(100, average * 140))}%`;

    return (
        <div className="h-[2px] w-[340px] overflow-hidden rounded-full bg-cyan-200/[0.05]">
            <div className="h-full rounded-full bg-emerald-300/70 transition-all duration-150" style={{ width }} />
        </div>
    );
};

export default TopAudioBar;
