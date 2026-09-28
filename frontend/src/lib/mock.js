// Заглушка Supabase Auth и API для `npm run dev:mock`: вёрстка всех экранов
// без почты и бэкенда. В обычном режиме не используется.
import { ApiError } from "./errors";

const delay = (ms) => new Promise((r) => setTimeout(r, ms));
const load = (key, fallback) => {
  try {
    return JSON.parse(sessionStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
};
const save = (key, value) => {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* приватный режим — живём без сохранения */
  }
};

// ---------- auth ----------

const listeners = new Set();
let session = load("mock-session", null);
let pendingEmail = null;

function emit(event) {
  listeners.forEach((cb) => cb(event, session));
}

export const mockSupabase = {
  auth: {
    getSession: async () => ({ data: { session } }),
    onAuthStateChange(cb) {
      listeners.add(cb);
      return { data: { subscription: { unsubscribe: () => listeners.delete(cb) } } };
    },
    signInWithOtp: async ({ email }) => {
      await delay(500);
      pendingEmail = email;
      return { error: null };
    },
    setSession: async () => ({ error: null }),
    signOut: async () => {
      session = null;
      save("mock-session", null);
      emit("SIGNED_OUT");
      return { error: null };
    },
  },
  // Только в моке: имитирует переход по ссылке из письма.
  openMagicLink() {
    session = { access_token: "mock-token", user: { email: pendingEmail } };
    save("mock-session", session);
    emit("SIGNED_IN");
  },
};

// ---------- API ----------

const PER_LEVEL = 100;
const today = () => new Date().toISOString().slice(0, 10);
const daysAgo = (n) => new Date(Date.now() - n * 864e5).toISOString();

let db = load("mock-db", {
  xp: 160,
  streak: 3,
  last: daysAgo(1).slice(0, 10),
  attempts: [
    { id: "2", theme: "work", level: 2, success: true, score: 8, created_at: daysAgo(1) },
    { id: "1", theme: "purchase", level: 1, success: false, score: null, created_at: daysAgo(2) },
  ],
});
let failedOnce = false;
const finished = new Set();

const levelOf = (xp) => Math.min(3, Math.floor(xp / PER_LEVEL) + 1);
const user = () => {
  const level = levelOf(db.xp);
  return {
    user_id: "00000000-mock",
    xp: db.xp,
    level,
    xp_to_next_level: level >= 3 ? 0 : level * PER_LEVEL - db.xp,
    unlocked_difficulties: [1, 2, 3].filter((d) => d <= level),
  };
};

const OPTIONS = [
  [
    { option_id: "a", text: "Тогда я начну искать другое место." },
    { option_id: "b", text: "Давайте зафиксируем пересмотр в марте и премию за этот квартал." },
    { option_id: "c", text: "Хорошо, подожду до следующего года." },
  ],
  [
    { option_id: "a", text: "Либо сейчас, либо никогда." },
    { option_id: "b", text: "Предлагаю привязать прибавку к результатам проекта — это честно для обеих сторон." },
    { option_id: "c", text: "Может, тогда хотя бы дополнительный выходной?" },
  ],
];
const REPLIES = [
  "Цифры хорошие. Но повысить оклад прямо сейчас я не могу.",
  "Хм. Привязка к результатам — это уже разговор. Какие показатели предлагаете?",
];

const encode = (obj) => btoa(JSON.stringify(obj));
const decode = (token) => {
  try {
    return JSON.parse(atob(token));
  } catch {
    return null;
  }
};

export async function mockApi(method, path, body, token) {
  const raise = (status, detail) => new ApiError(status, detail);
  if (!token) throw raise(401, "Нужен вход");

  const route = `${method} ${path}`;
  await delay(route.startsWith("POST /negotiation") ? 1100 : 250);

  if (route === "POST /user" || route === "GET /user/me") return user();
  if (route === "GET /streak") return { streak_count: db.streak, last_practiced_date: db.last };
  if (route === "GET /attempts") return db.attempts.slice(0, 20);

  if (route === "POST /negotiation/start") {
    if (body.difficulty > user().level) throw raise(403, "Сложность ещё закрыта");
    if (body.mode === "custom" && /плохо|непонятно/i.test(body.custom_situation)) {
      return {
        rejected: true,
        reason: "too_vague",
        message: "Описание слишком общее: не понятно, с кем и о чём договариваться. Добавь подробностей.",
      };
    }
    return {
      negotiation_id: crypto.randomUUID(),
      session_token: encode({ d: body.difficulty, t: 0, bad: false, th: body.theme ?? null, id: crypto.randomUUID() }),
      scenario_text:
        "Ты полгода работаешь в отделе продаж, закрыл два проекта раньше срока и сэкономил отделу 400 тысяч. Пора говорить о повышении оклада.",
      counterpart_opening: "Бюджет на год уже утверждён. Прибавку обсудим в следующем квартале.",
      counterpart_role: "Начальник отдела",
      counterpart_tone: "Сдержанный",
      counterpart_goal: "не выйти из бюджета",
      ...(body.difficulty < 3 ? { options: OPTIONS[0] } : {}),
    };
  }

  if (route === "POST /negotiation/turn") {
    const s = decode(body.session_token);
    if (!s) throw raise(400, "Испорченный session_token");
    if (finished.has(s.id)) throw raise(409, "Эти переговоры уже засчитаны");
    if (/503/.test(body.message || "") && !failedOnce) {
      failedOnce = true;
      throw raise(503, "ИИ временно недоступен, попробуйте ещё раз");
    }
    const bad = s.bad || body.option_id === "a" || /сдаюсь/i.test(body.message || "");
    const t = s.t + 1;
    if (t < 2 && !bad) {
      return {
        continue: true,
        counterpart_reply: REPLIES[t],
        session_token: encode({ ...s, t, bad }),
        ...(s.d < 3 ? { options: OPTIONS[t] } : {}),
      };
    }

    finished.add(s.id);
    const success = !bad;
    const score = success ? 8 : null;
    const xpGained = success ? score * { 1: 5, 2: 8, 3: 12 }[s.d] : 5;
    const levelBefore = levelOf(db.xp);
    db = {
      ...db,
      xp: db.xp + xpGained,
      streak: db.last === today() ? db.streak : db.streak + 1,
      last: today(),
      attempts: [
        { id: String(db.attempts.length + 1), theme: s.th, level: s.d, success, score, created_at: new Date().toISOString() },
        ...db.attempts,
      ],
    };
    save("mock-db", db);
    return {
      continue: false,
      counterpart_reply: success
        ? "Ладно, убедили. Фиксируем пересмотр в марте и премию по итогам квартала."
        : "Раз так — разговор окончен. Вернёмся к нему в следующем году.",
      outcome: success ? "success" : "failure",
      score,
      feedback: success
        ? {
            broke_quote: null,
            broke_reason: null,
            what_worked: "Опирался на цифры и предложил компромисс вместо ультиматума.",
            alternative_phrasing: null,
            tip: "Назови конкретную сумму премии, а не оставляй её на усмотрение начальника.",
          }
        : "Ультиматум в первой же реплике закрыл разговор. Начни с аргументов и оставь сопернику пространство для манёвра.",
      xp_gained: xpGained,
      xp: db.xp,
      level: levelOf(db.xp),
      level_up: levelOf(db.xp) > levelBefore,
    };
  }

  throw raise(404, `Мок не знает ${route}`);
}
