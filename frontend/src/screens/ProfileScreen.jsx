import { useEffect, useLayoutEffect, useRef, useState } from "react";
import LevelStar from "../components/LevelStar";
import Raccoon from "../components/Raccoon";
import TorgSays from "../components/TorgSays";
import XpBar from "../components/XpBar";
import { ensureUser, friendlyError, getAttempts, getMe, getStreak } from "../lib/api";
import {
  DIFFICULTIES,
  MAX_LEVEL,
  TIPS,
  attemptXp,
  formStats,
  levelProgress,
  peppers,
  perLevelFrom,
  plural,
  themeTitle,
  tipOfTheDay,
} from "../lib/game";
import { supabase } from "../lib/supabase";

const GREETINGS = [
  "Готов выбить себе скидку?",
  "Разомнём навык убеждения?",
  "Сегодня торгуемся до победы!",
  "Кто кого переспорит?",
];
const RECENT_LIMIT = 3;
const FIT_STEPS = ["hide-tip", "hide-row3", "hide-row2", "hide-form", "hide-howto"];

// Экран профиля не прокручивается: прячем нижние блоки по одному, пока всё не влезет.
function useFit(ref, deps) {
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const fit = () => {
      el.classList.remove(...FIT_STEPS);
      for (const step of FIT_STEPS) {
        // +2px — допуск на дробные размеры, иначе блок прячется из-за полпикселя.
        if (el.scrollHeight <= el.clientHeight + 2) break;
        el.classList.add(step);
      }
    };
    fit();
    document.fonts?.ready.then(fit); // веб-шрифты меняют высоту текста после загрузки
    const observer = new ResizeObserver(fit);
    observer.observe(el);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

const shortDate = (iso) => new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
const oneDecimal = (n) => n.toLocaleString("ru-RU", { maximumFractionDigits: 1 });

function Form({ attempts }) {
  if (!attempts?.length) return null;
  const s = formStats(attempts);
  return (
    <section className="recent form-block">
      <h2>
        Форма · {s.total} {plural(s.total, "последний бой", "последних боя", "последних боёв")}
      </h2>
      <div className="form-tiles">
        <div className="form-tile win">
          <b>
            {s.wins}/{s.total}
          </b>
          <span>побед</span>
        </div>
        <div className="form-tile avg">
          <b>{s.avg != null ? oneDecimal(s.avg) : "—"}</b>
          <span>средняя оценка</span>
        </div>
        <div className="form-tile best">
          <b>{s.best != null ? `${s.best}/10` : "—"}</b>
          <span>лучшая</span>
        </div>
      </div>
    </section>
  );
}

const STEPS = [
  "Выбери тему и соперника — или опиши свою ситуацию.",
  "Веди переговоры: выбирай ответ или пиши своими словами.",
  "Получи разбор судьи и XP, открывай соперников посильнее.",
];

// Для новичка вместо пустых «Формы» и «Последних боёв».
function HowTo() {
  return (
    <section className="recent howto">
      <h2>Как проходит бой</h2>
      <ol className="steps">
        {STEPS.map((step, i) => (
          <li key={i}>
            <span className="step-num">{i + 1}</span>
            {step}
          </li>
        ))}
      </ol>
    </section>
  );
}

function TorgTip() {
  const [index, setIndex] = useState(tipOfTheDay);
  return (
    <section className="tip-card" aria-live="polite">
      <Raccoon mood="sly" size={44} />
      <div className="tip-body">
        <p className="sub">Совет от Торга</p>
        <p key={index} className="fade-in">
          {TIPS[index]}
        </p>
        <button type="button" className="link-btn" onClick={() => setIndex((i) => (i + 1) % TIPS.length)}>
          Ещё совет →
        </button>
      </div>
    </section>
  );
}

function Recent({ attempts }) {
  if (!attempts?.length) return null;
  return (
    <section className="recent recent-block">
      <h2>Последние бои</h2>
      <div className="recent-list">
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
      </div>
    </section>
  );
}

export default function ProfileScreen({ user, needsEnsure, onUser, onArena }) {
  const [streak, setStreak] = useState(null);
  const [attempts, setAttempts] = useState(null);
  const [error, setError] = useState(null);
  const [reload, setReload] = useState(0);
  const [greeting] = useState(() => GREETINGS[Math.floor(Math.random() * GREETINGS.length)]);
  const restRef = useRef(null);
  useFit(restRef, [user, attempts]);

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
  const signOut = () => {
    if (window.confirm("Выйти из аккаунта?")) supabase.auth.signOut();
  };

  return (
    <main className="screen profile fade-in">
      <div className="topbar">
        <div className="stat">
          <LevelStar level={user.level} /> Уровень {user.level}
        </div>
        <div className="topbar-right">
          {streak && (
            <div className="stat streak" style={streakCount ? undefined : { color: "var(--muted)" }}>
              🔥 {streakCount} {plural(streakCount, "день", "дня", "дней")}
            </div>
          )}
          <button type="button" className="exit-btn" onClick={signOut} aria-label="Выйти из аккаунта" title="Выйти">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4" />
              <path d="M15 16l4-4-4-4" />
              <path d="M19 12H9" />
            </svg>
          </button>
        </div>
      </div>

      <div className="hero">
        <div className="bubble">{greeting}</div>
        <Raccoon className="bob" size={84} />
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
          <p className="next-unlock">
            🔒 Откроет соперника «{DIFFICULTIES[user.level]?.title}» {peppers(user.level + 1)}
          </p>
        </div>
      )}

      <div className="profile-rest" ref={restRef}>
        <button type="button" className="btn" onClick={onArena}>
          На арену
        </button>
        {attempts?.length === 0 && <HowTo />}
        <Form attempts={attempts} />
        <Recent attempts={attempts} />
        <TorgTip />
      </div>
    </main>
  );
}
