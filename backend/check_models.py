import os
from dotenv import load_dotenv
import google.genai as genai

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options={"api_version": "v1alpha"},
)

print("=== All models with bidiGenerateContent support ===")
for m in client.models.list():
    actions = str(getattr(m, "supported_actions", "") or "")
    if "bidi" in actions.lower() or "live" in m.name.lower():
        print(f"  {m.name}  |  {actions}")

print("\n=== All available models ===")
for m in client.models.list():
    print(f"  {m.name}")
