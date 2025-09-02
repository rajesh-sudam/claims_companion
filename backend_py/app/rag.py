import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import numpy as np
from pathlib import Path

DOCUMENTS_DIR = os.path.join(os.path.dirname(__file__), "documents")

class RAGService:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2', token=False)
        self.docs = self._load_documents()
        self.embeddings = self.model.encode([doc['text'] for doc in self.docs])
        # self.index = faiss.IndexFlatL2(self.embeddings.shape[1])
        # self.index.add(np.array(self.embeddings))
    
    def _load_documents(self):
        docs = []
        for filename in os.listdir(DOCUMENTS_DIR):
            if filename.endswith(".pdf"):
                path = os.path.join(DOCUMENTS_DIR, filename)
                with open(path, "rb") as f:
                    # reader = PyPDF2.PdfReader(f)
                    text = ""
                    # for page in reader.pages:
                    #     text += page.extract_text() or ""
                    # # Split into chunks (e.g., 2000 chars)
                    # chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]
                    # for idx, chunk in enumerate(chunks):
                    #     docs.append({
                    #         "id": f"{filename}-{idx}", 
                    #         "text": chunk,
                    #         "doc_id": filename,
                    #         "chunk_id": str(idx)
                    #     })
        return docs
    
    def retrieve(self, query, top_k=3):
        query_emb = self.model.encode([query])
        return None
        # # D, I = self.index.search(np.array(query_emb), top_k)
        # results = []
        # for dist, idx in zip(D[0], I[0]):
        #     if idx < len(self.docs):
        #         doc = self.docs[idx].copy()
        #         doc['score'] = float(dist)  # Include distance as score
        #         results.append(doc)
        # return results

# Global RAG service instance
_rag_service: Optional[RAGService] = None

def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
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