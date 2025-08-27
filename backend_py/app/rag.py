import os
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import PyPDF2

DOCUMENTS_DIR = os.path.join(os.path.dirname(__file__), "documents")

class RAGService:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.docs = self._load_documents()
        self.embeddings = self.model.encode([doc['text'] for doc in self.docs])
        self.index = faiss.IndexFlatL2(self.embeddings.shape[1])
        self.index.add(np.array(self.embeddings))

    def _load_documents(self):
        docs = []
        for filename in os.listdir(DOCUMENTS_DIR):
            if filename.endswith(".pdf"):
                path = os.path.join(DOCUMENTS_DIR, filename)
                with open(path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() or ""
                    # Split into chunks (e.g., 2000 chars)
                    chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]
                    for idx, chunk in enumerate(chunks):
                        docs.append({"id": f"{filename}-{idx}", "text": chunk})
        return docs

    def retrieve(self, query, top_k=3):
        query_emb = self.model.encode([query])
        D, I = self.index.search(np.array(query_emb), top_k)
        return [self.docs[i]['text'] for i in I[0]]