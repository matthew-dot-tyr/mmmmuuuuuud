import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Raccoon from "../components/Raccoon";
import TorgSays from "../components/TorgSays";
import { friendlyError, sendTurn } from "../lib/api";
import { MESSAGE_MAX, moodFor, peppers, wearsTie } from "../lib/game";

const RETRYABLE = new Set([0, 503]);
const LETTERS = "АБВГДЕ";

export default function ArenaScreen({ battle, onExit, onFinish }) {
  const { start, difficulty } = battle;
  // session_token — непрозрачная строка: всегда шлём последний полученный.
  const token = useRef(start.session_token);
  const feedRef = useRef(null);
  const lastThemRef = useRef(null);
  const replyRef = useRef(null);
  const [messages, setMessages] = useState([{ from: "them", text: start.counterpart_opening }]);
  const [options, setOptions] = useState(start.options ?? null);
  const [selected, setSelected] = useState(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [retryBody, setRetryBody] = useState(null);
  const [final, setFinal] = useState(null);

  const turn = messages.filter((m) => m.from === "them").length;
  const lastThemIndex = messages.findLastIndex((m) => m.from === "them");

  // Новая реплика соперника — показываем её начало (варианты ниже, до них доскроллят).
  // Своя реплика или «Торг думает…» — в самый низ ленты.
  useEffect(() => {
    const feed = feedRef.current;
    if (!feed || messages.length < 2) return;
    const last = messages[messages.length - 1];
    if (last.from === "them" && lastThemRef.current) {
      feed.scrollTo({ top: lastThemRef.current.offsetTop - 12, behavior: "smooth" });
    } else {
      feed.scrollTo({ top: feed.scrollHeight, behavior: "smooth" });
    }
  }, [messages]);

  useEffect(() => {
    const feed = feedRef.current;
    if (busy && feed) feed.scrollTo({ top: feed.scrollHeight, behavior: "smooth" });
  }, [busy]);

  // Поле ввода растёт по тексту, но не выше ~5 строк.
  useLayoutEffect(() => {
    const el = replyRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 132)}px`;
  }, [text]);

  async function send(body, shownText) {
    if (shownText) setMessages((m) => [...m, { from: "me", text: shownText }]);
    setBusy(true);
    setError(null);
    try {
      const res = await sendTurn({ ...body, session_token: token.current });
      setRetryBody(null);
      setMessages((m) => [...m, { from: "them", text: res.counterpart_reply }]);
      if (res.continue) {
        token.current = res.session_token;
        setOptions(res.options ?? null);
        setSelected(null);
        setText("");
      } else {
        setFinal(res);
      }
    } catch (e) {
      if (e.status === 401) return;
      if (e.status === 409) {
        onExit();
        return;
      }
      setError(e);
      if (RETRYABLE.has(e.status)) {
        // Реплика уже в чате — «Повторить» шлёт тот же запрос с тем же токеном.
        setRetryBody(body);
      } else {
        setRetryBody(null);
        if (shownText) setMessages((m) => m.slice(0, -1));
      }
    } finally {
      setBusy(false);
    }
  }

  function answer() {
    if (busy || retryBody) return;
    if (options) {
      const option = options.find((o) => o.option_id === selected);
      if (option) send({ option_id: option.option_id }, option.text);
    } else {
      const message = text.trim();
      if (message) send({ message }, message);
    }
  }

  function exit() {
    if (final || window.confirm("Покинуть арену? Этот бой не засчитается.")) onExit();
  }

  const locked = busy || Boolean(retryBody);
  const canAnswer = !locked && (options ? Boolean(selected) : Boolean(text.trim()));
  const showOptions = options && !final && !busy && !retryBody;

  return (
    <main className="screen arena">
      <header className="foe">
        <Raccoon mood={moodFor(difficulty)} size={42} tie={wearsTie(start.counterpart_role)} />
        <div className="who">
          <b>{start.counterpart_role}</b>
          <small>
            {final ? "Бой окончен" : `Ход ${turn}`} · {peppers(difficulty)}
          </small>
        </div>
        <button type="button" className="icon-btn" onClick={exit} aria-label="Покинуть арену">
          ×
        </button>
      </header>

      <div className="feed" ref={feedRef}>
        <section className="brief" aria-label="Ситуация">
          <p className="sub">Ситуация</p>
          <p>{start.scenario_text}</p>
          {start.counterpart_tone && (
            <p className="brief-row">
              <span className="tag">Характер</span> {start.counterpart_tone}
            </p>
          )}
          {start.counterpart_goal && (
            <p className="brief-row">
              <span className="tag goal">Цель соперника</span> {start.counterpart_goal}
            </p>
          )}
        </section>

        <div className="chat" aria-live="polite">
          {messages.map((m, i) => (
            <div key={i} ref={i === lastThemIndex ? lastThemRef : undefined} className={`msg ${m.from} fade-in`}>
              {m.text}
            </div>
          ))}
          {busy && (
            <div className="typing" role="status">
              <span className="dots" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
              Торг думает…
            </div>
          )}
        </div>

        {showOptions && (
          <section className="choices fade-in" aria-label="Варианты ответа">
            <p className="sub">Твой ответ</p>
            <div role="radiogroup" aria-label="Варианты ответа" className="choice-list">
              {options.map((o, i) => (
                <button
                  key={o.option_id}
                  type="button"
                  role="radio"
                  aria-checked={selected === o.option_id}
                  className={`opt${selected === o.option_id ? " sel" : ""}`}
                  onClick={() => setSelected(o.option_id)}
                >
                  <span className="opt-letter" aria-hidden="true">
                    {LETTERS[i] ?? i + 1}
                  </span>
                  <span>{o.text}</span>
                </button>
              ))}
            </div>
          </section>
        )}
      </div>

      <footer className="dock">
        {error && (
          <TorgSays
            action={
              retryBody ? (
                <button type="button" className="btn small" onClick={() => send(retryBody)} disabled={busy}>
                  Повторить
                </button>
              ) : null
            }
          >
            {friendlyError(error)}
          </TorgSays>
        )}

        {final ? (
          <button type="button" className="btn green" onClick={() => onFinish(final)}>
            Итоги боя
          </button>
        ) : retryBody ? null : options ? (
          <button type="button" className="btn green" onClick={answer} disabled={!canAnswer}>
            {busy ? "Торг думает…" : selected ? "Ответить" : "Выбери ответ выше"}
          </button>
        ) : (
          <div className="composer">
            <label className="visually-hidden" htmlFor="reply">
              Твой ответ
            </label>
            <textarea
              id="reply"
              ref={replyRef}
              className="field"
              rows={1}
              maxLength={MESSAGE_MAX}
              placeholder="Твой ответ своими словами…"
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) answer();
              }}
              disabled={locked}
            />
            <button type="button" className="btn green send" onClick={answer} disabled={!canAnswer} aria-label="Ответить">
              ➤
            </button>
          </div>
        )}
        {!options && !final && !retryBody && text.length > MESSAGE_MAX - 200 && (
          <div className="counter">
            {text.length} / {MESSAGE_MAX}
          </div>
        )}
      </footer>
    </main>
  );
}
