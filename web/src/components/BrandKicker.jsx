import React from 'react';

const BrandKicker = ({ icon: Icon, children }) => (
  <div className="panel-kicker">
    <span className="panel-kicker-brand" aria-hidden="true">
      <img src="/brand/bizguide-ai-mark.svg" alt="" />
    </span>
    {Icon && <Icon size={14} aria-hidden="true" />}
    <span>{children}</span>
  </div>
);

export default BrandKicker;
