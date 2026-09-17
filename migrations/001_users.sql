-- Схема пользователей и атомарное начисление XP.
-- Выполнить один раз в Supabase: SQL Editor -> New query -> вставить -> Run.

create table if not exists public.users (
    id         uuid primary key default gen_random_uuid(),
    xp         integer not null default 0,
    level      integer not null default 1,
    created_at timestamptz not null default now()
);

-- Начисление XP одним запросом, чтобы два одновременных /judge не затёрли
-- прогресс друг друга. Формула уровня должна совпадать с db.compute_level:
-- level = min(1 + xp / 100, 3), целочисленное деление.
create or replace function public.add_xp(p_user_id uuid, p_gain integer)
returns table (xp integer, level integer)
language sql
as $$
    update public.users u
       set xp    = u.xp + p_gain,
           level = least(1 + (u.xp + p_gain) / 100, 3)
     where u.id = p_user_id
    returning u.xp, u.level;
$$;
