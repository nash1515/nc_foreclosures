import React from 'react';

export const GoogleMapsIcon = ({ size = 16, style = {}, ...props }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    style={style}
    {...props}
  >
    {/* Google Maps red pin marker */}
    <path
      d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"
      fill="#EA4335"
    />
    <circle
      cx="12"
      cy="9"
      r="2.5"
      fill="#B31412"
    />
  </svg>
);
