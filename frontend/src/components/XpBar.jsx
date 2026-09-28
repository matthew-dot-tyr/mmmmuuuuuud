// from — стартовая заливка в процентах: если задана, полоса анимированно дорастает до pct.
export default function XpBar({ pct, from }) {
  const w = `${Math.max(0, Math.min(100, pct))}%`;
  const style = { width: w, "--w": w };
  if (from != null) style["--from"] = `${Math.max(0, Math.min(100, from))}%`;
  return (
    <div className="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)}>
      <i className={from != null ? "animxp" : undefined} style={style} />
    </div>
  );
}
