import React from 'react';

export const PropWireIcon = ({ size = 16, style = {}, ...props }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    style={style}
    {...props}
  >
    {/* PropWire stylized P - angular design with cut corner */}
    <path
      d="M6 4 L6 20 L10 20 L10 15 L15 15 L18 12 L18 4 Z M10 7 L14 7 L14 12 L10 12 Z"
      fill="#1E3A5F"
    />
  </svg>
);
