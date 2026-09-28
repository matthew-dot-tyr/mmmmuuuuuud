import { createClient } from "@supabase/supabase-js";
import { SUPABASE_ANON_KEY, SUPABASE_URL } from "./config";

// Условие прямо на import.meta.env — так сборщик выкидывает мок из продакшен-бандла.
const mock = import.meta.env.VITE_MOCK === "1" ? await import("./mock") : null;

if (!mock && (!SUPABASE_URL || !SUPABASE_ANON_KEY)) {
  throw new Error("Заполни VITE_SUPABASE_URL и VITE_SUPABASE_ANON_KEY в frontend/.env (см. .env.example)");
}

export const supabase = mock
  ? mock.mockSupabase
  : createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: { detectSessionInUrl: true, persistSession: true, autoRefreshToken: true },
    });

// Ссылка из письма приносит токены в #-фрагменте. detectSessionInUrl должен
// разобрать его сам, но в static/play.html на этом ловили пустую сессию —
// поэтому, как и там, ставим сессию явно и сразу чистим адресную строку.
export async function consumeAuthHash() {
  const hash = window.location.hash.slice(1);
  if (!hash) return null;
  const params = new URLSearchParams(hash);
  const access_token = params.get("access_token");
  const refresh_token = params.get("refresh_token");
  const errorDescription = params.get("error_description");
  history.replaceState(null, "", window.location.pathname + window.location.search);
  if (errorDescription) return errorDescription;
  if (access_token && refresh_token) {
    const { error } = await supabase.auth.setSession({ access_token, refresh_token });
    if (error) return error.message;
  }
  return null;
}

export async function getAccessToken() {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}
