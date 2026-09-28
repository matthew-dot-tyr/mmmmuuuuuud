import { useState } from "react";
import Raccoon from "../components/Raccoon";
import ThemeIcon from "../components/ThemeIcon";
import TorgSays from "../components/TorgSays";
import { friendlyError, getMe, startNegotiation } from "../lib/api";
import { CUSTOM_MAX, CUSTOM_MIN, DIFFICULTIES, THEMES, peppers } from "../lib/game";

const CUSTOM = "custom";

export default function SetupScreen({ user, onUser, onBack, onStart }) {
  const unlocked = user?.unlocked_difficulties ?? [1];
  const [theme, setTheme] = useState(THEMES[0].slug);
  const [custom, setCustom] = useState("");
  const [difficulty, setDifficulty] = useState(Math.max(...unlocked));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [rejection, setRejection] = useState(null);

  const customLen = custom.trim().length;
  const customOk = customLen >= CUSTOM_MIN && customLen <= CUSTOM_MAX;
  const ready = !busy && unlocked.includes(difficulty) && (theme !== CUSTOM || customOk);

  async function start() {
    const body =
      theme === CUSTOM
        ? { mode: "custom", custom_situation: custom.trim(), difficulty }
        : { mode: "theme", theme, difficulty };
    setBusy(true);
    setError(null);
    setRejection(null);
    try {
      const res = await startNegotiation(body);
      if (res.rejected) {
        setRejection(res.message || "Не получилось построить сценарий. Попробуй описать иначе.");
        return;
      }
      onStart(res, difficulty);
    } catch (e) {
      if (e.status === 401) return;
      setError(e);
      if (e.status === 403) getMe().then(onUser).catch(() => {});
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="screen fade-in">
      <div className="topbar">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Назад в профиль" disabled={busy}>
          ←
        </button>
        <span className="sub">Подготовка к бою</span>
        <span style={{ width: 34 }} />
      </div>

      <p className="sub">Тема</p>
      <div className="tiles" role="radiogroup" aria-label="Тема">
        {THEMES.map((t) => (
          <button
            key={t.slug}
            type="button"
            role="radio"
            aria-checked={theme === t.slug}
            className={`tile${theme === t.slug ? " sel" : ""}`}
            onClick={() => {
              setTheme(t.slug);
              setRejection(null);
            }}
            disabled={busy}
          >
            <ThemeIcon slug={t.slug} color={t.color} />
            {t.title}
          </button>
        ))}
        <button
          type="button"
          role="radio"
          aria-checked={theme === CUSTOM}
          className={`tile wide${theme === CUSTOM ? " sel" : ""}`}
          onClick={() => setTheme(CUSTOM)}
          disabled={busy}
        >
          <span className="ic" style={{ background: "var(--primary-light)", color: "var(--primary-dark)", fontSize: 18 }}>
            ✎
          </span>
          <span>
            Своя ситуация
            <br />
            <small>Опиши переговоры своими словами</small>
          </span>
        </button>
      </div>

      {theme === CUSTOM && (
        <div className="custom-box fade-in">
          <label className="visually-hidden" htmlFor="custom">
            Своя ситуация
          </label>
          <textarea
            id="custom"
            className="field"
            rows={4}
            maxLength={CUSTOM_MAX}
            placeholder="С кем и о чём договариваешься? Например: хочу, чтобы арендодатель снизил цену за квартиру, потому что…"
            value={custom}
            onChange={(e) => {
              setCustom(e.target.value);
              setRejection(null);
            }}
            disabled={busy}
            autoFocus
          />
          <div className={`counter${customLen && !customOk ? " bad" : ""}`}>
            {customLen < CUSTOM_MIN ? `ещё ${CUSTOM_MIN - customLen} симв. · ` : ""}
            {customLen} / {CUSTOM_MAX}
          </div>
          {rejection && <TorgSays mood="stubborn">{rejection}</TorgSays>}
        </div>
      )}

      <p className="sub">Соперник</p>
      <div className="diff" role="radiogroup" aria-label="Сложность">
        {DIFFICULTIES.map((d) => {
          const open = unlocked.includes(d.level);
          return (
            <button
              key={d.level}
              type="button"
              role="radio"
              aria-checked={difficulty === d.level}
              className={`dcard${difficulty === d.level ? " sel" : ""}`}
              onClick={() => setDifficulty(d.level)}
              disabled={!open || busy}
              title={open ? undefined : `Откроется с ${d.level} уровня`}
            >
              <Raccoon mood={d.mood} size={36} />
              <span className="pep">{open ? peppers(d.level) : "🔒"}</span>
              <b>{d.title}</b>
              {!open && <small>с {d.level} уровня</small>}
            </button>
          );
        })}
      </div>

      {rejection && theme !== CUSTOM && <TorgSays mood="stubborn">{rejection}</TorgSays>}
      {error && (
        <TorgSays
          action={
            error.status === 503 || error.status === 0 ? (
              <button type="button" className="btn small" onClick={start}>
                Повторить
              </button>
            ) : null
          }
        >
          {friendlyError(error)}
        </TorgSays>
      )}

      <div className="spacer" />
      {busy && (
        <div className="preparing" role="status">
          <Raccoon mood="sly" size={34} className="bob" /> Торг готовит сценарий…
        </div>
      )}
      <button type="button" className="btn" onClick={start} disabled={!ready}>
        В бой
      </button>
    </main>
  );
}
