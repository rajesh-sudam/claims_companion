import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import numpy as np
from pathlib import Path
import PyPDF2
from numpy.linalg import norm

DOCUMENTS_DIR = os.path.join(os.path.dirname(__file__), "documents")

class RAGService:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.docs = self._load_documents()
        if self.docs:
            self.embeddings = self.model.encode([doc['text'] for doc in self.docs])
        else:
            self.embeddings = np.array([])

    def _load_documents(self, file_paths: Optional[List[str]] = None):
        docs = []
        files_to_load = file_paths if file_paths is not None else [os.path.join(DOCUMENTS_DIR, f) for f in os.listdir(DOCUMENTS_DIR) if f.endswith(".pdf")]
        
        for path in files_to_load:
            filename = os.path.basename(path)
            if filename.endswith(".pdf"):
                try:
                    with open(path, "rb") as f:
                        reader = PyPDF2.PdfReader(f)
                        text = ""
                        for page in reader.pages:
                            text += page.extract_text() or ""
                        # Split into chunks (e.g., 2000 chars)
                        chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]
                        for idx, chunk in enumerate(chunks):
                            docs.append({
                                "id": f"{filename}-{idx}",
                                "text": chunk,
                                "doc_id": filename,
                                "chunk_id": str(idx)
                            })
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
        return docs

    def add_documents(self, file_paths: List[str]):
        new_docs = self._load_documents(file_paths)
        if not new_docs:
            return

        new_embeddings = self.model.encode([doc['text'] for doc in new_docs])
        
        self.docs.extend(new_docs)
        if self.embeddings.size == 0:
            self.embeddings = new_embeddings
        else:
            self.embeddings = np.vstack([self.embeddings, new_embeddings])


    def retrieve(self, query, top_k=3):
        if not self.docs:
            return []
        query_emb = self.model.encode([query])
        # Using cosine similarity
        cos_sim = np.dot(self.embeddings, query_emb.T) / (norm(self.embeddings, axis=1)[:, np.newaxis] * norm(query_emb.T, axis=0))
        top_k_indices = np.argsort(cos_sim, axis=0)[-top_k:][::-1].flatten()

        results = []
        for idx in top_k_indices:
            doc = self.docs[idx].copy()
            doc['score'] = float(cos_sim[idx])
            results.append(doc)
        return results

# --- FastAPI Dependency ---

_rag_service: Optional[RAGService] = None

def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        print("Initializing RAG Service...")
        _rag_service = RAGService()
        print("RAG Service Initialized.")
    return _rag_service


def analyse_claim_with_rag(
    claim_type: str,
    description: Optional[str],
    files: List[str]
) -> str:
    """
    Analyze a claim using RAG to find relevant policy information.

    Args:
        claim_type: Type of claim (motor, health, etc.)
        description: Incident description
        files: List of file paths to uploaded documents

    Returns:
        Analysis result as a string
    """
    if not description:
        return "No description provided for analysis."

    # Get the RAG service
    rag_service = get_rag_service()
    
    # Add new files to the RAG service
    if files:
        rag_service.add_documents(files)

    # Create a query combining claim type and description
    query = f"Claim type: {claim_type}. Description: {description}"

    # Retrieve relevant document chunks
    relevant_chunks = rag_service.retrieve(query, top_k=5)

    if not relevant_chunks:
        return "No relevant policy information found for this claim."

    # Format the context for AI processing
    context = "\n\n".join([chunk["text"] for chunk in relevant_chunks])

    # Create a simple analysis (in a real implementation, this would use an AI model)
    analysis = f"Found {len(relevant_chunks)} relevant policy sections for this {claim_type} claim. "
    analysis += f"Key information: {context[:200]}..."

    return analysis
