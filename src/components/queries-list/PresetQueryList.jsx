
import React, { useEffect, useState } from 'react';

export default function PresetQueryList({ queryGroups, loadPresetQuery }) {
    // if you would like to change the colors
    const baseColors = [
        '#ff7b2fff', // vivid blue
        '#ff7b2fff', // vivid orange/red
        '#ff7b2fff', // vivid green
        '#ff7b2fff', // vivid purple
        '#ff7b2fff', // deep vivid blue
        '#ff7b2fff', // vivid rose
        '#ff7b2fff', // vivid lime/olive
        '#ff7b2fff'  // vivid teal
    ];

    const [isDarkMode, setIsDarkMode] = useState(() => document.body.classList.contains('xy-dark'));

    useEffect(() => {
        const check = () => setIsDarkMode(document.body.classList.contains('xy-dark'));
        const obs = new MutationObserver((mutations) => {
            mutations.forEach(m => {
                if (m.type === 'attributes' && m.attributeName === 'class') check();
            });
        });
        obs.observe(document.body, { attributes: true, attributeFilter: ['class'] });
        window.addEventListener('storage', check);
        return () => { obs.disconnect(); window.removeEventListener('storage', check); };
    }, []);

    // Helpers
    const hexToRgb = (hex) => {
        const h = hex.replace('#', '');
        const r = parseInt(h.substring(0, 2), 16);
        const g = parseInt(h.substring(2, 4), 16);
        const b = parseInt(h.substring(4, 6), 16);
        return { r, g, b };
    };
    const rgbToHex = (r, g, b) => {
        const toHex = (v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0');
        return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
    };

    // Produce lighter (towards white) or darker (towards black) variant
    const adjustForMode = (hex, darkMode) => {
        const { r, g, b } = hexToRgb(hex);
        if (darkMode) {
            // darken by 18% for dark mode
            return rgbToHex(r * 0.78, g * 0.78, b * 0.78);
        } else {
            // lighten by blending 20% towards white for light mode
            return rgbToHex(r + (255 - r) * 0.20, g + (255 - g) * 0.20, b + (255 - b) * 0.20);
        }
    };

    const luminance = (hex) => {
        const { r, g, b } = hexToRgb(hex);
        // relative luminance
        const RsRGB = r / 255, GsRGB = g / 255, BsRGB = b / 255;
        const R = RsRGB <= 0.03928 ? RsRGB / 12.92 : Math.pow((RsRGB + 0.055) / 1.055, 2.4);
        const G = GsRGB <= 0.03928 ? GsRGB / 12.92 : Math.pow((GsRGB + 0.055) / 1.055, 2.4);
        const B = BsRGB <= 0.03928 ? BsRGB / 12.92 : Math.pow((BsRGB + 0.055) / 1.055, 2.4);
        return 0.2126 * R + 0.7152 * G + 0.0722 * B;
    };

    return (
        <div className={"predefined-queries"}>
            {queryGroups.map((group) => (
                <div key={group.dataset} className="query-dataset-group">
                    <h4 className="dataset-header">{group.dataset}</h4>
                    {group.queries.map((q, idx) => {
                        const base = baseColors[idx % baseColors.length];
                        const bg = adjustForMode(base, isDarkMode);
                        const isBestOptimized = q.meta?.bestOptimized;
                        const changedThisTurn = q.meta?.changedThisTurn;
                        const needsRun = q.meta?.needsRun;
                        const highlightRed = q.meta?.highlightRed;
                        const textColor = isBestOptimized ? '#00e5ff' : (luminance(bg) < 0.5 ? '#ffffff' : '#222222');
                        return (
                            <button
                                className={`query-button ${isBestOptimized ? 'query-button-best-optimized' : ''} ${changedThisTurn ? 'query-button-updated' : ''} ${highlightRed ? 'query-button-red' : ''}`}
                                onClick={() => loadPresetQuery(q)}
                                key={q["title"]}
                                style={{
                                    color: textColor,
                                    opacity: 1
                                }}
                            >
                                <span className="query-button-title">{q["title"]}</span>
                                {isBestOptimized && <span className="query-badge query-badge-best">best</span>}
                                {needsRun && <span className="query-badge query-badge-run">to run</span>}
                                {changedThisTurn && <span className="query-badge query-badge-updated">updated</span>}
                            </button>
                        )
                    })}
                </div>
            ))}
        </div>
    )
}
