const env = import.meta.env;

export const MOCK = env.VITE_MOCK === "1";
export const API_URL = (env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
export const SUPABASE_URL = env.VITE_SUPABASE_URL;
export const SUPABASE_ANON_KEY = env.VITE_SUPABASE_ANON_KEY;
