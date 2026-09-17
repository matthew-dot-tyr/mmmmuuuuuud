from db import get_user, update_xp


user_id = "fae71a89-486d-449f-a860-e4327a7306f2"

print(get_user(user_id))


update_xp(
    user_id,
    100,
    2
)


print(get_user(user_id))