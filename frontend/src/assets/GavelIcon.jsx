export const GavelIcon = ({ size = 24, color = 'currentColor' }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    {/* Center post */}
    <rect x="11" y="4" width="2" height="16" fill={color} />
    {/* Base */}
    <rect x="7" y="20" width="10" height="2" rx="0.5" fill={color} />
    {/* Balance beam */}
    <rect x="2" y="5" width="20" height="2" rx="0.5" fill={color} />
    {/* Left scale strings */}
    <path d="M4 7 L4 12" stroke={color} strokeWidth="1" />
    <path d="M8 7 L8 12" stroke={color} strokeWidth="1" />
    {/* Left pan */}
    <path d="M2 12 Q6 14 10 12 L9 13 Q6 15 3 13 Z" fill={color} />
    {/* Right scale strings */}
    <path d="M16 7 L16 12" stroke={color} strokeWidth="1" />
    <path d="M20 7 L20 12" stroke={color} strokeWidth="1" />
    {/* Right pan */}
    <path d="M14 12 Q18 14 22 12 L21 13 Q18 15 15 13 Z" fill={color} />
    {/* Top ornament */}
    <circle cx="12" cy="3" r="1.5" fill={color} />
  </svg>
);
