import React from 'react';

const Logo = ({ size = 40, showText = false, textSize = 24 }) => {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
      <img
        src="/logo.png"
        alt="BizGuide AI Logo"
        width={size}
        height={size}
        style={{
          borderRadius: `${size * 0.22}px`,
          flexShrink: 0,
          objectFit: 'cover',
          boxShadow: '0 4px 16px rgba(99, 102, 241, 0.4)',
        }}
      />
      {showText && (
        <span style={{
          fontSize: `${textSize}px`,
          fontWeight: 700,
          background: 'linear-gradient(135deg, #f8fafc, #c4b5fd)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          letterSpacing: '-0.5px',
          lineHeight: 1,
        }}>
          BizGuide
        </span>
      )}
    </div>
  );
};

export default Logo;
