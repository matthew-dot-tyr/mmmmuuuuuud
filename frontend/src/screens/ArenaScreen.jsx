import { useEffect, useRef, useState } from "react";
import Raccoon from "../components/Raccoon";
import TorgSays from "../components/TorgSays";
import { friendlyError, sendTurn } from "../lib/api";
import { MESSAGE_MAX, moodFor, wearsTie } from "../lib/game";

const RETRYABLE = new Set([0, 503]);

export default function ArenaScreen({ battle, onExit, onFinish }) {
  const { start, difficulty } = battle;
  // session_token — непрозрачная строка: всегда шлём последний полученный.
  const token = useRef(start.session_token);
  const chatRef = useRef(null);
  const [messages, setMessages] = useState([{ from: "them", text: start.counterpart_opening }]);
  const [options, setOptions] = useState(start.options ?? null);
  const [selected, setSelected] = useState(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [retryBody, setRetryBody] = useState(null);
  const [final, setFinal] = useState(null);

  const turn = messages.filter((m) => m.from === "them").length;

  useEffect(() => {
    const el = chatRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages, busy, error]);

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

  const canAnswer = !busy && !retryBody && (options ? Boolean(selected) : Boolean(text.trim()));

  return (
    <main className="screen arena">
      <header className="foe">
        <Raccoon mood={moodFor(difficulty)} size={54} tie={wearsTie(start.counterpart_role)} />
        <div className="who">
          <b>{start.counterpart_role}</b>
          <div className="tags">
            {start.counterpart_tone && <span className="tag">{start.counterpart_tone}</span>}
            {start.counterpart_goal && <span className="tag goal">Цель: {start.counterpart_goal}</span>}
          </div>
        </div>
        <button type="button" className="icon-btn" onClick={exit} aria-label="Покинуть арену">
          ×
        </button>
      </header>

      <details className="situation">
        <summary>Ситуация</summary>
        <p>{start.scenario_text}</p>
      </details>

      <div className="chat" ref={chatRef} aria-live="polite">
        <span className="round">{final ? "Бой окончен" : `Ход ${turn}`}</span>
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.from} fade-in`}>
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

      <div className="opts">
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
        ) : retryBody ? null : (
          <>
            {options ? (
              <div className="stack" role="radiogroup" aria-label="Варианты ответа" style={{ gap: 8 }}>
                {options.map((o) => (
                  <button
                    key={o.option_id}
                    type="button"
                    role="radio"
                    aria-checked={selected === o.option_id}
                    className={`opt${selected === o.option_id ? " sel" : ""}`}
                    onClick={() => setSelected(o.option_id)}
                    disabled={busy || Boolean(retryBody)}
                  >
                    {o.text}
                  </button>
                ))}
              </div>
            ) : (
              <>
                <label className="visually-hidden" htmlFor="reply">
                  Твой ответ
                </label>
                <textarea
                  id="reply"
                  className="field"
                  rows={3}
                  maxLength={MESSAGE_MAX}
                  placeholder="Твой ответ своими словами…"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) answer();
                  }}
                  disabled={busy || Boolean(retryBody)}
                />
                {text.length > MESSAGE_MAX - 200 && (
                  <div className="counter">
                    {text.length} / {MESSAGE_MAX}
                  </div>
                )}
              </>
            )}
            <button type="button" className="btn green" onClick={answer} disabled={!canAnswer}>
              Ответить
            </button>
          </>
        )}
      </div>
    </main>
  );
}
