import { useEffect, useState } from "react";
import LevelStar from "../components/LevelStar";
import Raccoon from "../components/Raccoon";
import TorgSays from "../components/TorgSays";
import XpBar from "../components/XpBar";
import { ensureUser, friendlyError, getAttempts, getMe, getStreak } from "../lib/api";
import { MAX_LEVEL, attemptXp, levelProgress, peppers, perLevelFrom, plural, themeTitle } from "../lib/game";
import { supabase } from "../lib/supabase";

const GREETINGS = [
  "Готов выбить себе скидку?",
  "Разомнём навык убеждения?",
  "Сегодня торгуемся до победы!",
  "Кто кого переспорит?",
];
const RECENT_LIMIT = 5;

const shortDate = (iso) => new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "short" });

function Recent({ attempts }) {
  if (!attempts?.length) return null;
  return (
    <section className="recent">
      <h2>Последние бои</h2>
      {attempts.slice(0, RECENT_LIMIT).map((a) => (
        <div className="row" key={a.id}>
          <span className="dot" style={{ background: a.success ? "var(--win)" : "var(--lose)" }}>
            {a.success ? a.score : "✕"}
          </span>
          <span className="what">
            {themeTitle(a.theme)}
            <small>
              {peppers(a.level)} · {shortDate(a.created_at)}
            </small>
          </span>
          <span className="xp">+{attemptXp(a)}</span>
        </div>
      ))}
    </section>
  );
}

export default function ProfileScreen({ user, needsEnsure, onUser, onArena }) {
  const [streak, setStreak] = useState(null);
  const [attempts, setAttempts] = useState(null);
  const [error, setError] = useState(null);
  const [reload, setReload] = useState(0);
  const [greeting] = useState(() => GREETINGS[Math.floor(Math.random() * GREETINGS.length)]);

  useEffect(() => {
    let alive = true;
    setError(null);
    (async () => {
      try {
        // POST /user — сразу после входа (создаёт профиль, если его нет), дальше GET /user/me.
        const me = await (needsEnsure ? ensureUser() : getMe());
        if (!alive) return;
        onUser(me);
        const [s, a] = await Promise.allSettled([getStreak(), getAttempts()]);
        if (!alive) return;
        if (s.status === "fulfilled") setStreak(s.value);
        setAttempts(a.status === "fulfilled" ? a.value : []);
      } catch (e) {
        if (alive && e.status !== 401) setError(e);
      }
    })();
    return () => {
      alive = false;
    };
    // needsEnsure/onUser намеренно не в зависимостях: грузим один раз на показ экрана.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reload]);

  if (!user) {
    return (
      <main className="screen">
        {error ? (
          <>
            <div className="spacer" />
            <TorgSays
              action={
                <button type="button" className="btn small" onClick={() => setReload((n) => n + 1)}>
                  Повторить
                </button>
              }
            >
              {friendlyError(error)}
            </TorgSays>
            <div className="spacer" />
          </>
        ) : (
          <>
            <div className="skeleton" style={{ height: 34 }} />
            <div className="skeleton" style={{ height: 190, borderRadius: 24 }} />
            <div className="skeleton" style={{ height: 40 }} />
            <div className="skeleton" style={{ height: 52, borderRadius: 16 }} />
          </>
        )}
      </main>
    );
  }

  const progress = levelProgress(user.xp, perLevelFrom(user));
  const streakCount = streak?.streak_count ?? 0;

  return (
    <main className="screen fade-in">
      <div className="topbar">
        <div className="stat">
          <LevelStar level={user.level} /> Уровень {user.level}
        </div>
        {streak && (
          <div className="stat streak" style={streakCount ? undefined : { color: "var(--muted)" }}>
            🔥 {streakCount} {plural(streakCount, "день", "дня", "дней")}
          </div>
        )}
      </div>

      <div className="hero">
        <div className="bubble">{greeting}</div>
        <Raccoon className="bob" size={110} />
      </div>

      {user.level >= MAX_LEVEL ? (
        <div className="maxlvl">⭐ Максимальный уровень · {user.xp} XP</div>
      ) : (
        <div className="xpbox">
          <div className="xprow">
            <span>До уровня {user.level + 1}</span>
            <span>
              {user.xp} / {user.xp + user.xp_to_next_level} XP
            </span>
          </div>
          <XpBar pct={progress.pct} />
        </div>
      )}

      <button type="button" className="btn" onClick={onArena}>
        На арену
      </button>

      <Recent attempts={attempts} />

      <div className="spacer" />
      <button type="button" className="link-btn signout" onClick={() => supabase.auth.signOut()}>
        Выйти
      </button>
    </main>
  );
}
