-- Лог попыток (завершённых переговоров) и стрик дней подряд.
-- Выполнить в Supabase: SQL Editor -> New query -> вставить -> Run.

alter table public.users
    add column if not exists last_practiced_date date,
    add column if not exists streak_count integer not null default 0;

-- "level" тут — сложность сценария (1-3, как в negotiations.difficulty),
-- НЕ уровень персонажа (users.level) — совпадение имени со спекой, не путать.
create table if not exists public.attempts (
    id         uuid primary key default gen_random_uuid(),
    user_id    uuid not null references public.users(id),
    theme      text,       -- null для mode=custom, как и в public.negotiations
    level      integer not null,
    success    boolean not null,
    score      integer,
    created_at timestamptz not null default now()
);

create index if not exists attempts_user_idx on public.attempts (user_id, created_at desc);
