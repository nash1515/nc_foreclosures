export const GavelIcon = ({ size = 24, color = 'currentColor' }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    {/* Gavel head */}
    <rect
      x="3"
      y="5"
      width="12"
      height="5"
      rx="1"
      fill={color}
      transform="rotate(-45 9 7.5)"
    />
    {/* Gavel handle */}
    <rect
      x="11"
      y="11"
      width="3"
      height="10"
      rx="1"
      fill={color}
      transform="rotate(-45 12.5 16)"
    />
    {/* Sound block */}
    <rect
      x="14"
      y="19"
      width="8"
      height="3"
      rx="0.5"
      fill={color}
    />
  </svg>
);
