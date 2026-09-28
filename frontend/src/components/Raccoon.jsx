// Маскот Торг — перенос функции raccoon() из design/mockups.html.
// mood: happy | stubborn | sly | sad (sad — для экрана поражения).
const INK = "#3B2A20";
const MASK = "#3A2C25";
const FUR = "#A38F80";

function Brows({ mood }) {
  const d = {
    stubborn: "M30 41l13 4M70 41l-13 4",
    sly: "M30 43l13-2M57 45l13-4",
    sad: "M30 45l13-5M70 45l-13-5",
  }[mood];
  return d ? <path d={d} stroke={MASK} strokeWidth="4" strokeLinecap="round" /> : null;
}

function Eyes({ mood }) {
  if (mood === "sly") {
    return <path d="M33 52q5 3 10 0M57 52q5 3 10 0" stroke="#fff" strokeWidth="4" fill="none" strokeLinecap="round" />;
  }
  return (
    <>
      <circle cx="38" cy="52" r="6" fill="#fff" />
      <circle cx="62" cy="52" r="6" fill="#fff" />
      <circle cx="39" cy="53" r="3.2" fill={INK} />
      <circle cx="63" cy="53" r="3.2" fill={INK} />
    </>
  );
}

function Mouth({ mood }) {
  const props = { stroke: INK, strokeWidth: "3.5", fill: "none", strokeLinecap: "round" };
  if (mood === "happy") return <path d="M42 72q8 8 16 0" {...props} />;
  if (mood === "stubborn") return <path d="M43 74h14" {...props} />;
  if (mood === "sad") return <path d="M42 77q8-7 16 0" {...props} />;
  return <path d="M42 73q10 4 17-3" {...props} />;
}

export default function Raccoon({ mood = "happy", size = 100, tie = false, cheer = false, className = "" }) {
  return (
    <span className={`raccoon ${className}`}>
      <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true">
        {cheer && <path d="M14 70L4 48M86 70l10-22" stroke={FUR} strokeWidth="8" strokeLinecap="round" />}
        <path d="M18 34L14 10l22 14z" fill={FUR} />
        <path d="M82 34l4-24-22 14z" fill={FUR} />
        <path d="M20 28l-2-12 11 8z" fill="#FFB3A7" />
        <path d="M80 28l2-12-11 8z" fill="#FFB3A7" />
        <ellipse cx="50" cy="58" rx="38" ry="34" fill="#C2B0A1" />
        <ellipse cx="50" cy="72" rx="20" ry="16" fill="#FBF3EC" />
        <path d="M16 52q17-14 34-2q17-12 34 2q-4 12-18 12q-10 0-16-8q-6 8-16 8q-14 0-18-12z" fill={MASK} />
        <Eyes mood={mood} />
        <Brows mood={mood} />
        {mood === "sad" && <path d="M66 60q-3 6 0 8q3-2 0-8z" fill="#8FC9F0" />}
        <ellipse cx="50" cy="64" rx="5" ry="3.6" fill={INK} />
        <Mouth mood={mood} />
        {tie && <path d="M50 88l-5 4 5 8 5-8z" fill="#E8505B" />}
      </svg>
    </span>
  );
}
