import React from 'react';

export const ZillowIcon = ({ size = 16, style = {}, ...props }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    style={style}
    {...props}
  >
    <text
      x="12"
      y="18"
      textAnchor="middle"
      fontSize="20"
      fontWeight="900"
      fontFamily="Arial Black, Arial, sans-serif"
      fill="#006AFF"
    >
      Z
    </text>
  </svg>
);
