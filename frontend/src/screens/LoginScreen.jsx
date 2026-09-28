import { useState } from "react";
import Raccoon from "../components/Raccoon";
import TorgSays from "../components/TorgSays";
import { MOCK } from "../lib/config";
import { supabase } from "../lib/supabase";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginScreen({ authError }) {
  const [email, setEmail] = useState("");
  const [sentTo, setSentTo] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(authError ? `Ссылка не сработала: ${authError}. Запроси новую.` : null);

  async function sendLink(e) {
    e.preventDefault();
    const value = email.trim();
    if (!EMAIL_RE.test(value)) {
      setError("Кажется, в почте опечатка. Проверь адрес.");
      return;
    }
    setBusy(true);
    setError(null);
    const { error: err } = await supabase.auth.signInWithOtp({
      email: value,
      options: { emailRedirectTo: window.location.origin + window.location.pathname },
    });
    setBusy(false);
    if (err) {
      setError(
        err.status === 429
          ? "Писем было слишком много. Подожди минутку и попробуй снова."
          : `Не получилось отправить письмо: ${err.message}`,
      );
      return;
    }
    setSentTo(value);
  }

  return (
    <div className="app">
      <main className="screen center-screen login">
        <Raccoon className="bob" size={120} mood="happy" />
        <h1>
          АРЕНА
          <br />
          <span>ПЕРЕГОВОРОВ</span>
        </h1>

        {sentTo ? (
          <div className="mail-sent fade-in">
            <b>Проверь почту</b>
            <p className="lead">
              Отправил ссылку для входа на <span className="email">{sentTo}</span>
              Открой её на этом устройстве — и сразу окажешься на арене.
            </p>
            <p className="hint">Письма нет? Загляни в «Спам» или отправь ещё раз.</p>
            <button type="button" className="link-btn" onClick={() => setSentTo(null)}>
              Другая почта / отправить ещё раз
            </button>
            {MOCK && (
              <div className="mock-link">
                <button type="button" className="btn small ghost" onClick={() => supabase.openMagicLink()}>
                  Мок: открыть ссылку из письма
                </button>
              </div>
            )}
          </div>
        ) : (
          <>
            <p className="lead">Тренируй переговоры с ИИ-соперником и прокачивай уровень</p>
            <form className="stack" onSubmit={sendLink} noValidate>
              <label className="visually-hidden" htmlFor="email">
                Почта
              </label>
              <input
                id="email"
                className="field"
                type="email"
                inputMode="email"
                autoComplete="email"
                placeholder="you@mail.ru"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={busy}
              />
              <button className="btn" type="submit" disabled={busy}>
                {busy ? "Отправляю…" : "Получить ссылку"}
              </button>
            </form>
            {error && <TorgSays>{error}</TorgSays>}
            <p className="hint">Пришлём ссылку для входа на почту. Пароль не нужен, аккаунт создастся сам.</p>
          </>
        )}
      </main>
    </div>
  );
}
