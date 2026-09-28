import { API_URL } from "./config";
import { ApiError } from "./errors";
import { getAccessToken, supabase } from "./supabase";

// Условие прямо на import.meta.env — так сборщик выкидывает мок из продакшен-бандла.
const mock = import.meta.env.VITE_MOCK === "1" ? await import("./mock") : null;

function detailText(data, status) {
  let detail = data?.detail;
  if (Array.isArray(detail)) detail = detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  return detail || `Ошибка ${status}`;
}

export async function api(method, path, body) {
  const token = await getAccessToken();
  if (mock) return mock.mockApi(method, path, body, token);

  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(API_URL + path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Сервер недоступен");
  }

  const text = await res.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: text };
  }

  if (!res.ok) {
    // Сессия умерла на стороне Supabase — выходим, onAuthStateChange вернёт на экран входа.
    if (res.status === 401) await supabase.auth.signOut();
    throw new ApiError(res.status, detailText(data, res.status));
  }
  return data;
}

export const getMe = () => api("GET", "/user/me");
export const ensureUser = () => api("POST", "/user");
export const getStreak = () => api("GET", "/streak");
export const getAttempts = () => api("GET", "/attempts");
export const startNegotiation = (body) => api("POST", "/negotiation/start", body);
export const sendTurn = (body) => api("POST", "/negotiation/turn", body);

// Тексты ошибок — от лица енота Торга.
export function friendlyError(err) {
  if (!(err instanceof ApiError)) return "Ой, у меня лапы запутались. Попробуй ещё раз.";
  switch (err.status) {
    case 0:
      return "Не могу достучаться до арены. Проверь интернет и попробуй ещё раз.";
    case 503:
      return "Торг задумался и завис: ИИ временно недоступен. Давай попробуем ещё раз?";
    case 403:
      return `Сюда пока не пускают: ${err.detail}`;
    case 409:
      return "Этот бой уже засчитан — возвращаю тебя в профиль.";
    case 400:
    case 422:
      return `Что-то не сходится: ${err.detail}`;
    default:
      return `Что-то пошло не так (${err.status}): ${err.detail}`;
  }
}
