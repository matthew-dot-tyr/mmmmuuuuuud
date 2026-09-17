-- Защита от повторного начисления XP за одни и те же переговоры.
-- Состояние диалога мы нигде не храним и гоняем через клиент, поэтому без
-- этой таблицы выигрышный последний ход можно прислать дважды и получить XP
-- дважды. Первичный ключ и делает всю работу: второй insert падает.
-- Выполнить в Supabase: SQL Editor -> New query -> вставить -> Run.

create table if not exists public.finished_negotiations (
    id           uuid primary key,
    user_id      uuid not null,
    finished_at  timestamptz not null default now()
);

create index if not exists finished_negotiations_user_idx
    on public.finished_negotiations (user_id);
