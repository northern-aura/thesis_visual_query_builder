import React, { useEffect, useState } from 'react';

export default function ThemeMenu({ currentMode = 'dark', onChangeMode }) {
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [isDarkMode, setIsDarkMode] = useState(false);

    useEffect(() => {
        const checkDarkMode = () => {
            const darkModeActive = document.body.classList.contains('xy-dark');
            setIsDarkMode(darkModeActive);
        };
        checkDarkMode();
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    checkDarkMode();
                }
            });
        });
        observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
        return () => observer.disconnect();
    }, []);

    const getHoverStyle = (isHover) => {
        if (isDarkMode) {
            return isHover ? '#3a3a3a' : 'transparent';
        } else {
            return isHover ? '#f5f5f5' : 'transparent';
        }
    };

    const handleSelect = (mode) => {
        setIsMenuOpen(false);
        if (onChangeMode) onChangeMode(mode);
    };

    return (
        <div className="theme-menu" style={{ position: 'relative' }}>
            <button
                onClick={() => setIsMenuOpen(!isMenuOpen)}
                style={{
                    padding: '12px 18px',
                    fontSize: '16px',
                    backgroundColor: isDarkMode ? '#2a2a2a' : '#ffffff',
                    color: isDarkMode ? '#ffffff' : '#222222',
                    border: isDarkMode ? '1px solid #444' : '1px solid #ddd',
                    borderRadius: '8px',
                    fontWeight: '700',
                    cursor: 'pointer',
                    boxShadow: isDarkMode ? '0 2px 6px rgba(0,0,0,0.6)' : '0 2px 6px rgba(0,0,0,0.12)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    height: 45,
                    transition: 'background-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease'
                }}
                title="Theme"
            >
                {currentMode.charAt(0).toUpperCase() + currentMode.slice(1)}
                <span aria-hidden="true" style={{ fontSize: 16, lineHeight: 1 }}> {isDarkMode ? '🌙' : '☀️'} </span>
            </button>

            {isMenuOpen && (
                <div className="export-dropdown" style={{
                    position: 'absolute',
                    bottom: '100%',
                    right: '0',
                    marginBottom: '8px',
                    backgroundColor: isDarkMode ? '#2a2a2a' : 'white',
                    border: isDarkMode ? '1px solid #444' : '1px solid #ddd',
                    borderRadius: '8px',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                    overflow: 'hidden',
                    minWidth: '160px',
                    zIndex: 100
                }}>
                    <button
                        onClick={() => handleSelect('dark')}
                        style={{
                            width: '100%',
                            padding: '12px 16px',
                            fontSize: '14px',
                            backgroundColor: 'transparent',
                            color: isDarkMode ? '#fff' : '#333',
                            border: 'none',
                            borderBottom: '1px solid ' + (isDarkMode ? '#444' : '#eee'),
                            cursor: 'pointer',
                            textAlign: 'left'
                        }}
                        onMouseEnter={e => e.target.style.backgroundColor = getHoverStyle(true)}
                        onMouseLeave={e => e.target.style.backgroundColor = getHoverStyle(false)}
                    >
                        Dark
                    </button>
                    <button
                        onClick={() => handleSelect('light')}
                        style={{
                            width: '100%',
                            padding: '12px 16px',
                            fontSize: '14px',
                            backgroundColor: 'transparent',
                            color: isDarkMode ? '#fff' : '#333',
                            border: 'none',
                            borderBottom: '1px solid ' + (isDarkMode ? '#444' : '#eee'),
                            cursor: 'pointer',
                            textAlign: 'left'
                        }}
                        onMouseEnter={e => e.target.style.backgroundColor = getHoverStyle(true)}
                        onMouseLeave={e => e.target.style.backgroundColor = getHoverStyle(false)}
                    >
                        Light
                    </button>
                    <button
                        onClick={() => handleSelect('system')}
                        style={{
                            width: '100%',
                            padding: '12px 16px',
                            fontSize: '14px',
                            backgroundColor: 'transparent',
                            color: isDarkMode ? '#fff' : '#333',
                            border: 'none',
                            cursor: 'pointer',
                            textAlign: 'left'
                        }}
                        onMouseEnter={e => e.target.style.backgroundColor = getHoverStyle(true)}
                        onMouseLeave={e => e.target.style.backgroundColor = getHoverStyle(false)}
                    >
                        System
                    </button>
                </div>
            )}
        </div>
    );
}
