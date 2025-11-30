from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os

from rag.pdf_loader import load_pdf
from rag.embedder import get_embedding
from rag.vector_store import vector_store
import google.generativeai as genai
import json

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------- UPLOAD PDF ----------
@app.route("/upload-pdf", methods=["POST"])
def upload_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    # 1. Extract PDF text
    text = load_pdf(file_path)

    # 2. Chunking (simple splitting)
    chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]

    # 3. Embed & store
    for chunk in chunks:
        emb = get_embedding(chunk)
        vector_store.add(emb, chunk)

    return jsonify({"message": "PDF uploaded and indexed successfully"}), 200



# ---------- ASK QUESTION ----------
@app.route("/ask", methods=["POST"])
def ask_question():
    data = request.json
    query = data.get("question")

    if not query:
        return jsonify({"error": "Question missing"}), 400

    # 1. Embed question
    query_emb = get_embedding(query)

    # 2. Retrieve context chunks
    context_chunks = vector_store.search(query_emb, k=5)
    context = "\n\n".join(context_chunks)

    # 3. Ask Gemini with retrieved context
    prompt = f"""
You are a helpful assistant. Use ONLY the following PDF context:

{context}

Question: {query}

Required output format and rules:
- Return ONLY a single valid JSON object and nothing else (no markdown, no backticks, no commentary).
- The JSON must contain exactly one key: "answer" whose value is a string.
- The answer string MUST NOT contain newline characters (\\n), bullet characters ("*", "-", "•"), or any markdown formatting (no **, __, etc.).
- Do NOT use currency symbols. Replace the rupee symbol '₹' with the word " ruppees" (note the leading space) so amounts look like: "6,00,000 ruppees".
- Keep the answer concise and factual, based strictly on the provided PDF context.

Return the JSON only.
"""

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)

    # Try to parse the model output as JSON. If parsing fails, sanitize the text.
    try:
        parsed = json.loads(response.text)
        # Ensure the parsed object has the expected shape
        if isinstance(parsed, dict) and "answer" in parsed:
            return jsonify(parsed), 200
    except Exception:
        pass

    # Fallback sanitization: remove newlines, bullets, markdown and replace rupee symbol
    ans = response.text
    ans = ans.replace('\n', ' ').replace('\r', ' ')
    for ch in ['*', '•']:
        ans = ans.replace(ch, '')
    ans = ans.replace('-', ' ')
    ans = ans.replace('₹', ' ruppees')
    # Collapse multiple spaces
    ans = ' '.join(ans.split())

    return jsonify({"answer": ans}), 200



if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=8081)
