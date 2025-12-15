import React from 'react';

export const ZillowIcon = ({ size = 16, style = {}, ...props }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    style={style}
    {...props}
  >
    <path
      d="M12 2L2 12h3v8h6v-6h2v6h6v-8h3L12 2z"
      fill="#006AFF"
    />
  </svg>
);
