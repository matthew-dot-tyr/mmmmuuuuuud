import os
from dotenv import load_dotenv
from supabase import create_client


load_dotenv()


supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"]
)


MAX_LEVEL = 3
XP_PER_LEVEL = 100


def compute_level(xp):
    """level = 1 + floor(xp / 100), но не больше 3."""
    if xp < 0:
        xp = 0
    return min(1 + xp // XP_PER_LEVEL, MAX_LEVEL)


def get_user(user_id):
    return supabase.table("users") \
        .select("*") \
        .eq("id", user_id) \
        .execute()


def get_or_create_user(user_id):
    res = get_user(user_id)
    if res.data:
        return res.data[0]

    supabase.table("users") \
        .upsert(
            {"id": user_id, "xp": 0, "level": 1},
            on_conflict="id",
            ignore_duplicates=True
        ) \
        .execute()

    return get_user(user_id).data[0]


def update_xp(user_id, new_xp, new_level):
    return supabase.table("users") \
        .update({
            "xp": new_xp,
            "level": new_level
        }) \
        .eq("id", user_id) \
        .execute()