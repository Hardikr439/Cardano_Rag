import faiss
import numpy as np

class VectorStore:
    def __init__(self):
        # Gemini text-embedding-004 outputs 768 dim vectors
        self.index = faiss.IndexFlatL2(768)
        self.chunks = []

    def add(self, emb, chunk):
        emb = np.array(emb).reshape(1, -1).astype("float32")
        self.index.add(emb)
        self.chunks.append(chunk)

    def search(self, query_emb, k=3):
        if self.index.ntotal == 0:
            return []

        query_emb = np.array(query_emb).reshape(1, -1).astype("float32")
        distances, indices = self.index.search(query_emb, k)

        valid_indices = [i for i in indices[0] if i < len(self.chunks)]
        results = [self.chunks[i] for i in valid_indices]

        return results


vector_store = VectorStore()
