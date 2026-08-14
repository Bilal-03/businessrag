import React from 'react';

const Logo = ({ size = 40, showText = false, textSize = 24 }) => {
  return (
    <div className="brand-lockup">
      <span
        className="brand-mark"
        style={{ width: size, height: size, fontSize: `${size * 0.48}px` }}
        aria-hidden="true"
      >
        <img className="brand-mark-image" src="/brand/bizguide-ai-mark.svg" alt="" />
      </span>
      {showText && (
        <span className="brand-name" style={{ fontSize: `${textSize}px` }}>
          <span>BizGuide</span><span className="brand-name-accent"> AI</span>
        </span>
      )}
    </div>
  );
};

export default Logo;
