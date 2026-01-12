import React from 'react';

/**
 * Hurricane Warning Flag Icon
 * Maritime signal flag - red with black square center, wind-blown appearance
 * Official hurricane warning flag as per NOAA standards
 */
export const HurricaneWarningIcon = ({ size = 16, style = {} }) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={style}
    >
      {/* Flag pole */}
      <rect x="2" y="2" width="1.5" height="20" fill="#4a4a4a" />

      {/* Flag with billowing/wind-blown shape - red background */}
      <path
        d="M 3.5 4
           C 8 3.5, 12 3, 16 4
           C 17 4.5, 18 5.5, 19 6.5
           C 20 8, 21 10, 21.5 12
           C 21 14, 20 16, 19 17.5
           C 18 18.5, 17 19.5, 16 20
           C 12 21, 8 20.5, 3.5 20
           Z"
        fill="#DC143C"
        stroke="#8B0000"
        strokeWidth="0.3"
      />

      {/* Frayed/ragged trailing edge (right side) */}
      <path
        d="M 16 4 L 16.5 4.5 L 16.2 5
           M 18 6 L 18.8 6.8 L 18.5 7.5
           M 20 9 L 20.8 9.5 L 20.6 10.2
           M 21.5 12 L 22 12.5 L 21.8 13
           M 20.5 15 L 21.2 15.5 L 21 16
           M 19 17.5 L 19.5 18 L 19.2 18.5
           M 16.5 19.5 L 17 20 L 16.7 20.5"
        stroke="#8B0000"
        strokeWidth="0.5"
        strokeLinecap="round"
        fill="none"
      />

      {/* Black square in center */}
      <rect
        x="9"
        y="8.5"
        width="6"
        height="7"
        fill="#000000"
        rx="0.3"
      />

      {/* Shading/depth on flag to enhance 3D wind-blown effect */}
      <path
        d="M 3.5 4
           C 8 3.5, 12 3, 16 4
           C 17 4.5, 18 5.5, 19 6.5
           C 20 8, 21 10, 21.5 12"
        stroke="#FF6B6B"
        strokeWidth="0.8"
        fill="none"
        opacity="0.4"
        strokeLinecap="round"
      />

      {/* Shadow on bottom half for depth */}
      <path
        d="M 3.5 12
           C 8 12, 12 12, 16 12
           C 17 12.5, 18 13.5, 19 14.5
           C 18 15.5, 17 16.5, 16 17
           C 12 18, 8 17.5, 3.5 17
           Z"
        fill="#000000"
        opacity="0.15"
      />
    </svg>
  );
};
