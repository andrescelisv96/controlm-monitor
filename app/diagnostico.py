import instructor
from app.modelos import Diagnostico

MODELO = "gemini-3.8-flash"
client = instructor.from_provider(f"google/{MODELO}")

def diagnosticar(prompt: str) -> Diagnostico:
    return client.chat.completions.create(
        response_model=Diagnostico,
        max_retries=3,
        strict=False,
        messages=[{"role": "user", "content": prompt}],
    )