import os
from dotenv import load_dotenv

load_dotenv()

print("URL:")
print(os.environ.get("SUPABASE_URL"))

print("KEY:")
print(os.environ.get("SUPABASE_KEY")[:20])