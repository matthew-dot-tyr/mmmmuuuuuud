import { useMemo } from "react";

const COLORS = ["#FF8A3D", "#72BF44", "#FFC23D", "#E8505B", "#C9628A"];

export default function Confetti({ count = 26 }) {
  const pieces = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => ({
        left: `${Math.random() * 100}%`,
        background: COLORS[i % COLORS.length],
        animationDelay: `${-Math.random() * 3.2}s`,
        animationDuration: `${2.6 + Math.random() * 1.6}s`,
      })),
    [count],
  );
  return (
    <div className="confetti" aria-hidden="true">
      {pieces.map((style, i) => (
        <i key={i} style={style} />
      ))}
    </div>
  );
}
