import React from 'react';

const Logo = ({ size = 40, showText = false, textSize = 24 }) => {
  return (
    <div className="brand-lockup">
      <span
        className="brand-mark"
        style={{ width: size, height: size, fontSize: `${size * 0.48}px` }}
        aria-hidden="true"
      >
        B
      </span>
      {showText && (
        <span className="brand-name" style={{ fontSize: `${textSize}px` }}>
          BizGuide
        </span>
      )}
    </div>
  );
};

export default Logo;
