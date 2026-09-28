-- Лимит генераций, лог переговоров и лог отказов.
-- Выполнить в Supabase: SQL Editor -> New query -> вставить -> Run.

create table if not exists public.generation_limits (
    scope        text not null,          -- 'user' | 'ip' | 'turn'
    key          text not null,
    window_start timestamptz not null,
    count        integer not null default 0,
    primary key (scope, key, window_start)
);

create index if not exists generation_limits_window_idx
    on public.generation_limits (window_start);


create or replace function public.check_and_increment_generations(
    p_scope text,
    p_key   text,
    p_limit integer
)
returns table (allowed boolean, current_count integer)
language plpgsql
as $$
declare
    v_window timestamptz := date_trunc('hour', now());
    v_count  integer;
begin
    insert into public.generation_limits (scope, key, window_start, count)
    values (p_scope, p_key, v_window, 1)
    on conflict (scope, key, window_start)
    do update set count = generation_limits.count + 1
    returning generation_limits.count into v_count;

    return query select (v_count <= p_limit), v_count;
end;
$$;


create table if not exists public.negotiations (
    id               uuid primary key,
    user_id          uuid not null,
    mode             text not null,
    theme            text,
    custom_situation text,
    difficulty       integer not null,
    character_level  integer not null,
    created_at       timestamptz not null default now(),
    constraint negotiations_mode_check check (mode in ('theme', 'custom')),
    constraint negotiations_mode_fields_check check (
        (mode = 'custom' and custom_situation is not null and theme is null)
        or
        (mode = 'theme'  and theme is not null and custom_situation is null)
    )
);

create index if not exists negotiations_user_idx on public.negotiations (user_id);
create index if not exists negotiations_mode_idx on public.negotiations (mode, created_at desc);


create table if not exists public.refusal_log (
    id           uuid primary key default gen_random_uuid(),
    user_id      uuid,
    client_ip    text,
    mode         text,
    reason       text not null,
    input_text   text,
    raw_response text,
    difficulty   integer,
    created_at   timestamptz not null default now()
);

create index if not exists refusal_log_reason_idx on public.refusal_log (reason, created_at desc);
