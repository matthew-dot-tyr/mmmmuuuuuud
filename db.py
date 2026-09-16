import os
from dotenv import load_dotenv
from supabase import create_client


load_dotenv()


supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"]
)


def get_user(user_id):
    return supabase.table("users") \
        .select("*") \
        .eq("id", user_id) \
        .execute()


def update_xp(user_id, new_xp, new_level):
    return supabase.table("users") \
        .update({
            "xp": new_xp,
            "level": new_level
        }) \
        .eq("id", user_id) \
        .execute()