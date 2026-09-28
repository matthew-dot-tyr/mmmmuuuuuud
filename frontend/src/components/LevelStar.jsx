export default function LevelStar({ level }) {
  return (
    <span className="lvl">
      <svg viewBox="0 0 34 34" aria-hidden="true">
        <path
          d="M17 2l4.3 9 9.7 1.2-7.1 6.7 1.9 9.6L17 23.8l-8.8 4.7 1.9-9.6L3 12.2l9.7-1.2z"
          fill="#FFC23D"
          stroke="#D89A12"
          strokeWidth="2"
          strokeLinejoin="round"
        />
      </svg>
      <b>{level}</b>
    </span>
  );
}
