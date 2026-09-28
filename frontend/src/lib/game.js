export const THEMES = [
  { slug: "work", title: "Работа и карьера", color: "var(--primary)" },
  { slug: "money", title: "Деньги и бизнес", color: "var(--xp)" },
  { slug: "purchase", title: "Покупки и аренда", color: "var(--accent)" },
  { slug: "personal", title: "Личное и быт", color: "var(--lose)" },
];

export const DIFFICULTIES = [
  { level: 1, title: "Хочет договориться", mood: "happy" },
  { level: 2, title: "Держит позиции", mood: "stubborn" },
  { level: 3, title: "Стоит насмерть", mood: "sly" },
];

export const CUSTOM_MIN = 30;
export const CUSTOM_MAX = 400;
export const MESSAGE_MAX = 2000;
export const MAX_LEVEL = 3;

const XP_MULTIPLIER = { 1: 5, 2: 8, 3: 12 };
const LOSS_XP = 5;

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

const COUNTERPART_BOSS = /начальн|руковод|директор|босс|шеф|менеджер|работодат/i;
export const wearsTie = (role) => COUNTERPART_BOSS.test(role || "");
