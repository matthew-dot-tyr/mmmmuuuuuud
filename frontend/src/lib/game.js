export const THEMES = [
  { slug: "work", title: "Работа и карьера", color: "var(--primary)", about: "прибавка, условия работы, переработки" },
  { slug: "money", title: "Деньги и бизнес", color: "var(--xp)", about: "оплата, условия сделки, долги" },
  { slug: "purchase", title: "Покупки и аренда", color: "var(--accent)", about: "квартира, машина, ремонт" },
  { slug: "personal", title: "Личное и быт", color: "var(--lose)", about: "как договориться с близкими" },
];

// answers — сколько вариантов ответа даёт бэкенд (ai/contracts.py::OPTIONS_COUNT), на 3 — свободный текст.
export const DIFFICULTIES = [
  {
    level: 1,
    title: "Хочет договориться",
    mood: "happy",
    quote: "Давай найдём решение, которое устроит нас обоих!",
    answers: "3 варианта",
  },
  {
    level: 2,
    title: "Держит позиции",
    mood: "stubborn",
    quote: "Договоримся, но у меня есть условия, которые я не нарушу.",
    answers: "4 варианта",
  },
  {
    level: 3,
    title: "Стоит насмерть",
    mood: "sly",
    quote: "Мои принципы не обсуждаются. Попробуй переубедить.",
    answers: "своими словами",
  },
];

export const CUSTOM_MIN = 30;
export const CUSTOM_MAX = 400;
export const MESSAGE_MAX = 2000;
export const MAX_LEVEL = 3;

const XP_MULTIPLIER = { 1: 5, 2: 8, 3: 12 };
export const LOSS_XP = 5;
export const maxWinXp = (difficulty) => 10 * (XP_MULTIPLIER[difficulty] ?? 0);

export function themeTitle(slug) {
  return THEMES.find((t) => t.slug === slug)?.title ?? "Своя ситуация";
}

export function difficultyTitle(level) {
  return DIFFICULTIES.find((d) => d.level === level)?.title ?? "";
}

export function moodFor(difficulty) {
  return DIFFICULTIES.find((d) => d.level === difficulty)?.mood ?? "happy";
}

export const peppers = (n) => "🌶".repeat(n);

// /attempts не отдаёт начисленный XP — считаем по той же формуле, что progress.py.
export function attemptXp(attempt) {
  if (!attempt.success) return LOSS_XP;
  return (attempt.score ?? 0) * (XP_MULTIPLIER[attempt.level] ?? 0);
}

// Шаг уровня на бэкенде настраивается (XP_PER_LEVEL), поэтому выводим его
// из ответа /user/me: порог следующего уровня = xp + xp_to_next_level = level × шаг.
export function perLevelFrom(user) {
  if (!user || user.level >= MAX_LEVEL || user.xp_to_next_level <= 0) return 100;
  return (user.xp + user.xp_to_next_level) / user.level;
}

export function levelProgress(xp, perLevel) {
  const level = Math.min(MAX_LEVEL, Math.floor(xp / perLevel) + 1);
  if (level >= MAX_LEVEL) return { level, max: true, pct: 100, next: null };
  const start = (level - 1) * perLevel;
  return { level, max: false, pct: ((xp - start) / perLevel) * 100, next: level * perLevel };
}

export function plural(n, one, few, many) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

export const TIPS = [
  "Называй конкретные цифры: «премия 30 тысяч» звучит весомее, чем «какая-нибудь премия».",
  "Сначала выясни, чего хочет соперник, и только потом предлагай решение.",
  "Не делай уступку первым — дай собеседнику обозначить свою рамку.",
  "Опирайся на объективные критерии: рыночные цены, результаты, сроки.",
  "Пауза — тоже ход. Не спеши заполнять тишину уступкой.",
  "Спорь с позицией, а не с человеком: соперник должен оставаться партнёром.",
  "Заранее знай запасной вариант: что сделаешь, если договориться не выйдет.",
  "Меняй, а не дари: «если вы — то я» вместо уступки просто так.",
  "Перескажи слова соперника своими словами — он почувствует, что его услышали.",
  "Ультиматум закрывает разговор. Оставь сопернику пространство для манёвра.",
  "Проси чуть больше, чем рассчитываешь получить, но обязательно обоснуй запрос.",
  "Фиксируй договорённость конкретно: кто, что и к какому сроку делает.",
];

export function tipOfTheDay() {
  const start = new Date(new Date().getFullYear(), 0, 0);
  return Math.floor((Date.now() - start) / 864e5) % TIPS.length;
}

// Сводка по тому, что отдаёт /attempts (последние до 20 боёв, не вся история).
export function formStats(attempts) {
  const wins = attempts.filter((a) => a.success);
  const scores = wins.map((a) => a.score).filter((s) => s != null);
  return {
    total: attempts.length,
    wins: wins.length,
    avg: scores.length ? scores.reduce((sum, s) => sum + s, 0) / scores.length : null,
    best: scores.length ? Math.max(...scores) : null,
  };
}

const COUNTERPART_BOSS = /начальн|руковод|директор|босс|шеф|менеджер|работодат/i;
export const wearsTie = (role) => COUNTERPART_BOSS.test(role || "");
