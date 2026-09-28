// Иконки тем из design/mockups.html.
const ICONS = {
  work: (
    <>
      <rect x="2" y="6" width="16" height="11" rx="3" fill="#fff" />
      <rect x="7" y="3" width="6" height="4" rx="1.5" fill="none" stroke="#fff" strokeWidth="2" />
    </>
  ),
  money: (
    <>
      <circle cx="10" cy="10" r="7.5" fill="#fff" />
      <text x="10" y="14" textAnchor="middle" fontFamily="Nunito" fontWeight="900" fontSize="11" fill="#D89A12">
        ₽
      </text>
    </>
  ),
  purchase: (
    <>
      <path d="M3 9l7-6 7 6v8H3z" fill="#fff" />
      <rect x="8" y="12" width="4" height="5" fill="#C9628A" />
    </>
  ),
  personal: <path d="M10 17s-7-4.3-7-9a4 4 0 017-2.6A4 4 0 0117 8c0 4.7-7 9-7 9z" fill="#fff" />,
};

export default function ThemeIcon({ slug, color }) {
  return (
    <span className="ic" style={{ background: color }}>
      <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
        {ICONS[slug]}
      </svg>
    </span>
  );
}
