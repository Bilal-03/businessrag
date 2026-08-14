import React from 'react';

const Logo = ({ size = 40, showText = false, tone = 'light' }) => {
  const source = showText
    ? `/brand/bizguide-ai-logo-${tone === 'dark' ? 'dark' : 'light'}.svg`
    : tone === 'dark'
      ? '/brand/bizguide-ai-app-icon.svg'
      : '/brand/bizguide-ai-mark.svg';

  return (
    <div className={`brand-lockup ${showText ? 'brand-lockup-full' : 'brand-lockup-mark'}`}>
      <img
        className={showText ? 'brand-logo-image' : 'brand-mark-image'}
        src={source}
        alt={showText ? 'BizGuide AI' : ''}
        aria-hidden={showText ? undefined : true}
        style={showText ? { maxHeight: `${size}px` } : { width: size, height: size }}
      />
    </div>
  );
};

export default Logo;
