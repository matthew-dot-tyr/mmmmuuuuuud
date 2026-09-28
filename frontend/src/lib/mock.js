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

// Длины как у реальной модели: реплики по 2-3 предложения, на сложности 1 — 3
// варианта, на сложности 2 — 4 (ai/contracts.py::OPTIONS_COUNT).
const OPTIONS = [
  [
    { option_id: "a", text: "Тогда, боюсь, мне придётся искать другое место — рынок сейчас платит заметно больше, и у меня уже есть предложения." },
    { option_id: "b", text: "Понимаю про бюджет. Давайте тогда зафиксируем пересмотр оклада в марте письменно, а за этот квартал — разовую премию за сэкономленные 400 тысяч." },
    { option_id: "c", text: "Хорошо, я понимаю ситуацию. Подожду до следующего года, может быть, тогда получится." },
    { option_id: "d", text: "А если часть прибавки заменить дополнительными днями отпуска и оплатой курсов? Для бюджета это дешевле, а для меня ощутимо." },
  ],
  [
    { option_id: "a", text: "Либо прибавка сейчас, либо я пишу заявление. Решайте." },
    { option_id: "b", text: "Предлагаю привязать прибавку к результатам: если до конца квартала закрою ещё один проект в срок, оклад растёт на 15% с апреля." },
    { option_id: "c", text: "Может, тогда хотя бы дополнительный выходной в месяц? Больше ни на что не претендую." },
    { option_id: "d", text: "Давайте посмотрим на цифры вместе: сколько отдел сэкономил благодаря моим проектам и сколько стоит найти и обучить замену." },
  ],
];
const REPLIES = [
  "Цифры хорошие, спорить не буду — два проекта раньше срока это заметно. Но бюджет на год утверждён ещё в декабре, и повысить оклад прямо сейчас я не могу, как бы ни хотел.",
  "Хм. Привязка к результатам — это уже разговор, такое я могу согласовать с финансовым директором. Какие показатели вы предлагаете и в какие сроки?",
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
        "Вы полгода работаете менеджером в отделе продаж. За это время вы закрыли два проекта раньше срока и сэкономили отделу около 400 тысяч рублей. Оклад при этом не менялся с момента найма, и вы договорились о встрече с руководителем, чтобы обсудить повышение.",
      counterpart_opening:
        "Присаживайтесь. Я догадываюсь, о чём пойдёт речь, но сразу скажу: бюджет на год уже утверждён. Прибавку, если что, обсудим в следующем квартале.",
      counterpart_role: "Андрей Викторович, начальник отдела продаж, 45 лет",
      counterpart_tone: "Сдержанный и осторожный руководитель, который ценит цифры и не любит давления.",
      counterpart_goal: "Не выйти за рамки утверждённого бюджета и при этом удержать ценного сотрудника.",
      ...(body.difficulty < 3 ? { options: OPTIONS[0].slice(0, body.difficulty === 1 ? 3 : 4) } : {}),
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
        ...(s.d < 3 ? { options: OPTIONS[t].slice(0, s.d === 1 ? 3 : 4) } : {}),
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
