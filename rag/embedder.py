import google.generativeai as genai
import os

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_embedding(text):
    model = genai.embed_content(
        model="models/text-embedding-004",
        content=text
    )
    return model["embedding"]
