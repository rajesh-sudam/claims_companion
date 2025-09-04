import os
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from sentence_transformers import SentenceTransformer
import numpy as np
from pathlib import Path
import PyPDF2
from numpy.linalg import norm
import chromadb
from chromadb.config import Settings
# LangChain imports
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain.schema import BaseRetriever

# Maintain your existing directory structure
DOCUMENTS_DIR = os.path.join(os.path.dirname(__file__), "documents")

@dataclass
class InsuranceChunk:
    """Structured representation of insurance document chunks"""
    content: str
    metadata: Dict[str, Any]
    section_type: str  # "coverage", "exclusion", "definition", "procedure"
    section_hierarchy: List[str]  # ["Section 1", "1.1", "1.1.a"]
    cross_references: List[str]  # References to other sections
    conditions: List[str]  # If-then conditions found
    numerical_values: Dict[str, float]  # Extracted amounts, percentages

class RAGService:
    """Enhanced RAG Service - maintains your original interface"""
    
    def __init__(self):
        # Your original embedding model
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.docs = self._load_documents()
        if self.docs:
            self.embeddings = self.model.encode([doc['text'] for doc in self.docs])
        else:
            self.embeddings = np.array([])
        
        # Enhanced components
        self.document_processor = InsuranceDocumentProcessor()
        self.vectorstore = None
        self.hybrid_retriever = None
        
    def _load_documents(self, file_paths: Optional[List[str]] = None):
        """Your original document loading logic"""
        docs = []
        files_to_load = file_paths if file_paths is not None else [
            os.path.join(DOCUMENTS_DIR, f) for f in os.listdir(DOCUMENTS_DIR) 
            if f.endswith(".pdf")
        ]
        
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
        if not file_paths:
            return
        
        try:
            all_documents = []
            for path in file_paths:
                # Handle both absolute and relative paths
                if not os.path.isabs(path):
                    # Try relative to app directory first
                    abs_path = os.path.join("/home/app", path)
                    if not os.path.exists(abs_path):
                        abs_path = os.path.join("/home/app/app", path)
                else:
                    abs_path = path
                
                if os.path.exists(abs_path) and abs_path.endswith('.pdf'):
                    loader = PyPDFLoader(abs_path)
                    documents = loader.load()
                    all_documents.extend(documents)
                    print(f"Loaded {len(documents)} pages from {abs_path}")
                else:
                    print(f"File not found: {abs_path}")
        except Exception as e:
            print(f"Error adding documents: {e}")

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if self.hybrid_retriever:
            try:
                docs = self.hybrid_retriever.get_relevant_documents(query)
                results = []
                seen_content = set()
                
                for i, doc in enumerate(docs[:top_k * 2]):  # Get more to account for duplicates
                    # Create a simple hash of the content to detect duplicates
                    content_hash = hash(doc.page_content[:100])
                    if content_hash not in seen_content:
                        seen_content.add(content_hash)
                        results.append({
                            "id": f"enhanced-{len(results)}",
                            "text": doc.page_content,
                            "doc_id": doc.metadata.get('source', 'unknown'),
                            "chunk_id": str(doc.metadata.get('chunk_id', len(results))),
                            "score": 1.0 - (len(results) * 0.1),
                            "section_type": doc.metadata.get('section_type', ''),
                            "hierarchy": doc.metadata.get('hierarchy', ''),
                            "cross_references": doc.metadata.get('cross_references', ''),
                            "conditions": doc.metadata.get('conditions', '')
                        })
                        
                        if len(results) >= top_k:
                            break
            except Exception as E:
                print(f"Retrival Error {E}")
                
                return results
    
    def initialize_enhanced_retrieval(self, pdf_path: str, persist_directory: str = "/tmp/chroma_rag_db"):
        """Initialize enhanced retrieval capabilities"""
        try:
            # Load documents using LangChain
            loader = PyPDFLoader(pdf_path)
            documents = loader.load()
            print(f"Loaded {len(documents)} pages from {pdf_path}")
            
            # Process with intelligent chunking
            insurance_chunks = self.document_processor.intelligent_chunking(documents)
            print(f"Created {len(insurance_chunks)} intelligent chunks")
            
            # Convert to LangChain documents
            langchain_docs = self._convert_to_langchain_docs(insurance_chunks)
            
            # Create or load vectorstore
            embed_model = FastEmbedEmbeddings(model_name="BAAI/bge-base-en-v1.5")
            
            if os.path.exists(persist_directory) and os.listdir(persist_directory):
                print(f"Loading existing vectorstore from {persist_directory}")
                self.vectorstore = Chroma(
                    persist_directory=persist_directory,
                    embedding_function=embed_model
                )
            else:
                print(f"Creating new vectorstore at {persist_directory}")
                self.vectorstore = Chroma.from_documents(
                langchain_docs,
                embedding=embed_model,
                persist_directory=persist_directory,
                client_settings=Settings(
                    chroma_db_impl="duckdb+parquet",
                    persist_directory=persist_directory,
                    anonymized_telemetry=False
                )
                    )
            
            # Initialize hybrid retriever
            self.hybrid_retriever = HybridInsuranceRetriever(self.vectorstore, insurance_chunks)
            print("Enhanced retrieval system initialized successfully")
            
        except Exception as e:
            print(f"Failed to initialize enhanced retrieval: {e}")
            print("Falling back to original retrieval method")
    
    def _convert_to_langchain_docs(self, insurance_chunks: List[InsuranceChunk]) -> List[Document]:
        """Convert InsuranceChunk objects to LangChain Documents"""
        langchain_docs = []
        for i, chunk in enumerate(insurance_chunks):
            # Clean metadata for ChromaDB compatibility
            clean_metadata = {}
            
            if hasattr(chunk, 'metadata') and chunk.metadata:
                for key, value in chunk.metadata.items():
                    if isinstance(value, (str, int, float, bool, type(None))):
                        clean_metadata[key] = value
            
            # Convert complex fields to strings
            clean_metadata['section_type'] = str(chunk.section_type) if chunk.section_type else ''
            clean_metadata['cross_references'] = ', '.join(str(ref) for ref in chunk.cross_references) if chunk.cross_references else ''
            clean_metadata['conditions'] = ' | '.join(str(cond) for cond in chunk.conditions) if chunk.conditions else ''
            clean_metadata['hierarchy'] = ' > '.join(str(hier) for hier in chunk.section_hierarchy) if chunk.section_hierarchy else ''
            
            doc = Document(
                page_content=chunk.content,
                metadata=clean_metadata
            )
            langchain_docs.append(doc)
        
        return langchain_docs
    
    def enhanced_retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Enhanced retrieval using hybrid approach if available"""
        if self.hybrid_retriever:
            try:
                docs = self.hybrid_retriever.get_relevant_documents(query)
                results = []
                for i, doc in enumerate(docs[:top_k]):
                    results.append({
                        "id": f"enhanced-{i}",
                        "text": doc.page_content,
                        "doc_id": doc.metadata.get('source', 'unknown'),
                        "chunk_id": str(doc.metadata.get('chunk_id', i)),
                        "score": 1.0 - (i * 0.1),  # Approximate scoring
                        "section_type": doc.metadata.get('section_type', ''),
                        "hierarchy": doc.metadata.get('hierarchy', '')
                    })
                return results
            except Exception as e:
                print(f"Enhanced retrieval failed: {e}, falling back to original")
        
        # Fallback to original retrieve method
        return self.retrieve(query, top_k)

class InsuranceDocumentProcessor:
    """Advanced processor for insurance documents"""
    
    def __init__(self):
        self.section_patterns = {
            'section': r'Section\s+([IVX\d]+\.?[\d\w]*)',
            'subsection': r'(\d+\.)+\s*[A-Za-z]',
            'definition': r'Definition|means|shall mean|is defined as',
            'exclusion': r'excluded|not covered|does not cover|limitation',
            'coverage': r'covered|coverage|benefits|pays|reimburse',
            'condition': r'if|provided that|subject to|only if|when'
        }
        
    def extract_structure(self, text: str) -> Dict[str, Any]:
        """Extract document structure and metadata"""
        structure = {
            'sections': [],
            'definitions': [],
            'exclusions': [],
            'conditions': [],
            'cross_refs': [],
            'amounts': {}
        }
        
        # Find section headers
        for match in re.finditer(self.section_patterns['section'], text, re.IGNORECASE):
            structure['sections'].append({
                'number': match.group(1),
                'start_pos': match.start(),
                'text': match.group(0)
            })
        
        # Find cross-references
        cross_ref_pattern = r'(?:see|refer to|as (?:defined|stated) in)\s+(?:Section\s+)?([IVX\d\.]+)'
        structure['cross_refs'] = re.findall(cross_ref_pattern, text, re.IGNORECASE)
        
        # Extract monetary amounts and percentages
        amount_pattern = r'\$[\d,]+(?:\.\d{2})?|\d+%|\d+\s*percent'
        structure['amounts'] = re.findall(amount_pattern, text)
        
        # Find conditional statements
        condition_pattern = r'(?:if|when|provided that|subject to)[^.!?]*[.!?]'
        structure['conditions'] = re.findall(condition_pattern, text, re.IGNORECASE)
        
        return structure

    def intelligent_chunking(self, documents: List[Document]) -> List[InsuranceChunk]:
        """Create semantically meaningful chunks with preserved structure"""
        chunks = []
        
        for doc in documents:
            text = doc.page_content
            structure = self.extract_structure(text)
            
            # Split by sections first, then by semantic boundaries
            if structure['sections']:
                section_chunks = self._split_by_sections(text, structure)
            else:
                section_chunks = self._semantic_split_fallback(text)
            
            for i, chunk_text in enumerate(section_chunks):
                chunk_structure = self.extract_structure(chunk_text)
                chunk_type = self._classify_chunk_type(chunk_text)
                
                chunks.append(InsuranceChunk(
                    content=chunk_text,
                    metadata={
                        **doc.metadata,
                        'chunk_id': i,
                        'char_count': len(chunk_text),
                        'word_count': len(chunk_text.split()),
                    },
                    section_type=chunk_type,
                    section_hierarchy=self._extract_hierarchy(chunk_text),
                    cross_references=chunk_structure['cross_refs'],
                    conditions=chunk_structure['conditions'],
                    numerical_values=self._extract_numerical_values(chunk_structure['amounts'])
                ))
        
        return chunks
    
    def _split_long_section(self, text: str) -> List[str]:
        """Split a long section into smaller chunks while preserving context"""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", "!", "?", ";", " "],
            length_function=len
        )
        temp_doc = Document(page_content=text)
        sub_chunks = splitter.split_documents([temp_doc])
        return [chunk.page_content for chunk in sub_chunks]
    
    def _split_by_sections(self, text: str, structure: Dict) -> List[str]:
        """Split text by logical sections"""
        if not structure['sections']:
            return [text]
        
        chunks = []
        sections = structure['sections']
        
        for i, section in enumerate(sections):
            start_pos = section['start_pos']
            end_pos = sections[i + 1]['start_pos'] if i + 1 < len(sections) else len(text)
            section_text = text[start_pos:end_pos].strip()
            
            if len(section_text) > 2000:
                sub_chunks = self._split_long_section(section_text)
                chunks.extend(sub_chunks)
            else:
                chunks.append(section_text)
        
        return chunks
    
    def _semantic_split_fallback(self, text: str) -> List[str]:
        """Improved fallback splitting with overlap"""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", "!", "?", ";", " "],
            length_function=len
        )
        return [chunk.page_content for chunk in splitter.split_documents([Document(page_content=text)])]
    
    def _classify_chunk_type(self, text: str) -> str:
        """Classify chunk by content type"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['definition', 'means', 'shall mean', 'is defined as']):
            return 'definition'
        elif any(word in text_lower for word in ['excluded', 'not covered', 'limitation', 'does not apply']):
            return 'exclusion'
        elif any(word in text_lower for word in ['coverage', 'covered', 'benefits', 'reimburse', 'pays']):
            return 'coverage'
        elif any(word in text_lower for word in ['claim', 'file', 'procedure', 'process', 'submit']):
            return 'procedure'
        else:
            return 'general'
    
    def _extract_hierarchy(self, text: str) -> List[str]:
        """Extract section hierarchy from text"""
        section_matches = re.findall(r'(?:Section\s+)?([IVX\d]+(?:\.\d+)*(?:\.[a-zA-Z])?)', text)
        return section_matches[:3]
    
    def _extract_numerical_values(self, amounts: List[str]) -> Dict[str, float]:
        """Extract and parse numerical values"""
        values = {}
        for amount in amounts:
            if '$' in amount:
                clean_amount = re.sub(r'[^\d.]', '', amount)
                try:
                    values[f'amount_{len(values)}'] = float(clean_amount)
                except ValueError:
                    pass
            elif '%' in amount or 'percent' in amount:
                clean_percent = re.sub(r'[^\d.]', '', amount)
                try:
                    values[f'percentage_{len(values)}'] = float(clean_percent)
                except ValueError:
                    pass
        return values

class HybridInsuranceRetriever:
    """Custom retriever that combines multiple retrieval strategies"""
    
    def __init__(self, vectorstore, chunks: List[InsuranceChunk]):
        self.vectorstore = vectorstore
        self.chunks = chunks
        self.chunk_index = {i: chunk for i, chunk in enumerate(chunks)}
    
    def get_relevant_documents(self, query: str) -> List[Document]:
        """Main retrieval method"""
        # Vector similarity search
        similar_docs = self.vectorstore.similarity_search_with_score(query, k=10)
        
        # Extract and classify query
        insurance_keywords = self._extract_insurance_keywords(query)
        query_type = self._classify_query_type(query)
        
        # Expand with cross-references
        expanded_docs = self._expand_with_references(similar_docs, query_type)
        
        # Re-rank results
        final_docs = self._rerank_results(expanded_docs, query, query_type)
        
        return final_docs[:5]
    
    def _extract_insurance_keywords(self, query: str) -> List[str]:
        """Extract insurance-specific terms from query"""
        insurance_terms = [
            'deductible', 'premium', 'coverage', 'exclusion', 'claim', 
            'policy', 'benefit', 'liability', 'comprehensive', 'collision'
        ]
        return [term for term in insurance_terms if term.lower() in query.lower()]
    
    def _classify_query_type(self, query: str) -> str:
        """Classify the type of insurance question"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['covered', 'cover', 'coverage']):
            return 'coverage_check'
        elif any(word in query_lower for word in ['exclude', 'exclusion', 'not covered']):
            return 'exclusion_lookup'
        elif any(word in query_lower for word in ['define', 'definition', 'mean', 'means']):
            return 'definition_lookup'
        elif any(word in query_lower for word in ['claim', 'file', 'process', 'submit']):
            return 'procedure_inquiry'
        else:
            return 'general'
    
    def _expand_with_references(self, docs: List[tuple], query_type: str) -> List[Document]:
        """Expand results with cross-referenced sections"""
        expanded = []
        
        for doc, score in docs:
            expanded.append((doc, score))
            
            # Add cross-referenced sections if available
            chunk_id = doc.metadata.get('chunk_id')
            if chunk_id and int(chunk_id) in self.chunk_index:
                chunk = self.chunk_index[int(chunk_id)]
                for ref in chunk.cross_references:
                    ref_chunks = [c for c in self.chunks if ref in c.section_hierarchy]
                    for ref_chunk in ref_chunks:
                        ref_doc = Document(
                            page_content=ref_chunk.content,
                            metadata={'source': 'cross_reference', 'reference_to': ref}
                        )
                        expanded.append((ref_doc, score * 0.8))
        
        return [doc for doc, score in expanded]
    
    def _rerank_results(self, docs: List[Document], query: str, query_type: str) -> List[Document]:
        """Re-rank results based on insurance-specific criteria"""
        scored_docs = []
        
        for doc in docs:
            score = 0
            content_lower = doc.page_content.lower()
            
            # Base relevance scoring
            query_words = query.lower().split()
            matching_words = sum(1 for word in query_words if word in content_lower)
            score += matching_words / len(query_words)
            
            # Boost for document type matching query type
            if query_type == 'coverage_check' and 'coverage' in content_lower:
                score += 0.3
            elif query_type == 'exclusion_lookup' and 'exclusion' in content_lower:
                score += 0.3
            elif query_type == 'definition_lookup' and any(word in content_lower for word in ['definition', 'means']):
                score += 0.3
            
            scored_docs.append((doc, score))
        
        # Sort by score and return documents
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, score in scored_docs]

# Maintain your original global service instance pattern
_rag_service: Optional[RAGService] = None

def get_rag_service() -> RAGService:
    """Your original get_rag_service function"""
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
    """Enhanced claim analysis using intelligent document processing and retrieval"""
    rag_service = get_rag_service()
    
    # Ensure enhanced retrieval is available
    if not rag_service.hybrid_retriever:
        print("Enhanced retrieval system not initialized - initializing now")
        # Initialize with default documents directory if available
        default_docs = [os.path.join(DOCUMENTS_DIR, f) for f in os.listdir(DOCUMENTS_DIR) if f.endswith(".pdf")] if os.path.exists(DOCUMENTS_DIR) else []
        if default_docs:
            rag_service.add_documents(default_docs)
            rag_service.initialize_enhanced_retrieval(default_docs[0])
    
    # Add new claim-related files
    if files:
        rag_service.add_documents(files)

    # Create comprehensive query
    query_parts = [f"Claim type: {claim_type}"]
    if description:
        query_parts.append(f"Description: {description}")
    
    query = ". ".join(query_parts)

    # Retrieve relevant information using enhanced system
    relevant_chunks = rag_service.retrieve(query, top_k=8)

    # Enhanced context analysis
    context_analysis = {
        'coverage_contexts': [],
        'exclusion_contexts': [],
        'definition_contexts': [],
        'procedure_contexts': [],
        'condition_contexts': []
    }
    
    context_str = ""
    context_map = {}
    
    if relevant_chunks:
        for i, chunk in enumerate(relevant_chunks):
            doc_id = chunk.get("doc_id", "unknown_doc")
            chunk_id = chunk.get("chunk_id", str(i))
            section_type = chunk.get("section_type", "general")
            citation = f"({doc_id}:{chunk_id})"
            
            chunk_text = chunk.get('text', '')
            context_str += f"[{citation}] {chunk_text}\n\n"
            context_map[citation] = chunk_text
            
            # Categorize contexts by type for better analysis
            context_info = {
                'citation': citation,
                'text': chunk_text,
                'hierarchy': chunk.get('hierarchy', ''),
                'cross_references': chunk.get('cross_references', ''),
                'conditions': chunk.get('conditions', '')
            }
            
            if section_type == 'coverage':
                context_analysis['coverage_contexts'].append(context_info)
            elif section_type == 'exclusion':
                context_analysis['exclusion_contexts'].append(context_info)
            elif section_type == 'definition':
                context_analysis['definition_contexts'].append(context_info)
            elif section_type == 'procedure':
                context_analysis['procedure_contexts'].append(context_info)
            else:
                # Check for conditions in the text
                if chunk.get('conditions'):
                    context_analysis['condition_contexts'].append(context_info)
    
    # Enhanced output structure with detailed analysis
    output = {
        "decision": "NEEDS_MORE_INFO",
        "confidence_score": 0.0,
        "reasoning": [],
        "requirements_met": [],
        "exclusions_triggered": [],
        "conditions_to_verify": [],
        "coverage_summary": "",
        "relevant_definitions": [],
        "procedural_requirements": [],
        "next_steps": [],
        "supporting_evidence": []
    }

    if not relevant_chunks:
        output["decision"] = "INSUFFICIENT_CONTEXT"
        output["next_steps"].append("Provide more details about the claim or upload relevant policy documents.")
        output["reasoning"].append("No relevant policy information found in the knowledge base.")
        return json.dumps(output, indent=2)

    # Enhanced decision logic using structured context analysis
    coverage_indicators = 0
    exclusion_indicators = 0
    condition_requirements = []
    
    # Analyze coverage contexts
    for context in context_analysis['coverage_contexts']:
        text_lower = context['text'].lower()
        if any(phrase in text_lower for phrase in ['coverage applies', 'covered for', 'benefits include', 'policy covers']):
            coverage_indicators += 1
            output["requirements_met"].append(f"Coverage indicated in policy {context['citation']}")
            output["supporting_evidence"].append({
                "type": "coverage",
                "citation": context['citation'],
                "text": context['text'][:200] + "...",
                "hierarchy": context['hierarchy']
            })
    
    # Analyze exclusion contexts
    for context in context_analysis['exclusion_contexts']:
        text_lower = context['text'].lower()
        if any(phrase in text_lower for phrase in ['not covered', 'excluded', 'does not cover', 'limitation applies']):
            exclusion_indicators += 1
            output["exclusions_triggered"].append(f"Exclusion found in policy {context['citation']}")
            output["supporting_evidence"].append({
                "type": "exclusion", 
                "citation": context['citation'],
                "text": context['text'][:200] + "...",
                "hierarchy": context['hierarchy']
            })
    
    # Analyze conditional contexts
    for context in context_analysis['condition_contexts']:
        if context['conditions']:
            condition_requirements.extend(context['conditions'])
            output["conditions_to_verify"].append({
                "condition": context['conditions'],
                "source": context['citation'],
                "context": context['text'][:150] + "..."
            })
    
    # Process definitions for better understanding
    for context in context_analysis['definition_contexts']:
        output["relevant_definitions"].append({
            "source": context['citation'],
            "definition": context['text'][:300] + "..."
        })
    
    # Process procedural requirements
    for context in context_analysis['procedure_contexts']:
        text_lower = context['text'].lower()
        if any(phrase in text_lower for phrase in ['must file', 'required to submit', 'within', 'deadline']):
            output["procedural_requirements"].append({
                "requirement": context['text'][:200] + "...",
                "source": context['citation']
            })
    
    # Enhanced decision making with confidence scoring
    total_contexts = len(relevant_chunks)
    coverage_ratio = coverage_indicators / max(total_contexts, 1)
    exclusion_ratio = exclusion_indicators / max(total_contexts, 1)
    
    # Calculate confidence based on evidence strength
    confidence = min(0.9, (coverage_indicators + exclusion_indicators) * 0.2)
    output["confidence_score"] = round(confidence, 2)
    
    # Decision logic with enhanced reasoning
    if coverage_indicators > 0 and exclusion_indicators == 0:
        output["decision"] = "LIKELY_APPROVE"
        output["reasoning"].append(f"Found {coverage_indicators} coverage indicator(s) with no exclusions")
        output["coverage_summary"] = f"Your {claim_type} claim appears to be covered based on policy analysis."
        
        if condition_requirements:
            output["decision"] = "APPROVE_WITH_CONDITIONS"
            output["reasoning"].append("Approval subject to meeting specified conditions")
            output["next_steps"].append("Verify all conditions are met before final approval")
        else:
            output["next_steps"].append("Proceed with claim processing")
            
    elif exclusion_indicators > coverage_indicators:
        output["decision"] = "LIKELY_DENY" 
        output["reasoning"].append(f"Found {exclusion_indicators} exclusion indicator(s) outweighing {coverage_indicators} coverage indicator(s)")
        output["coverage_summary"] = f"Your {claim_type} claim may be denied due to policy exclusions."
        output["next_steps"].append("Review exclusions with claimant and consider appeal options if circumstances warrant")
        
    elif coverage_indicators > 0 and exclusion_indicators > 0:
        output["decision"] = "REQUIRES_REVIEW"
        output["reasoning"].append("Conflicting coverage and exclusion indicators found - manual review required")
        output["coverage_summary"] = f"Your {claim_type} claim requires detailed review due to conflicting policy provisions."
        output["next_steps"].append("Escalate to senior claims examiner for detailed policy interpretation")
        
    else:
        output["decision"] = "NEEDS_MORE_INFO" 
        output["reasoning"].append("Insufficient clear indicators for coverage determination")
        output["next_steps"].append("Gather additional information about the specific circumstances of the claim")
        output["next_steps"].append("Review additional policy sections that may apply")
    
    # Add general next steps based on findings
    if output["procedural_requirements"]:
        output["next_steps"].append("Ensure all procedural requirements are met")
    
    if output["conditions_to_verify"]:
        output["next_steps"].append("Verify all conditional requirements are satisfied")

    return json.dumps(output, indent=2)

# Enhanced RAG Chain Creation (new functionality)
def create_enhanced_insurance_rag(api_key: str, pdf_path: str = None):
    """Create an enhanced RAG system that integrates with your existing service"""
    rag_service = get_rag_service()
    
    if pdf_path:
        # Initialize enhanced capabilities
        rag_service.initialize_enhanced_retrieval(pdf_path)
    
    if not rag_service.vectorstore:
        print("Enhanced retrieval not available, using original RAG service")
        return None
    
    # Enhanced prompt template
    enhanced_prompt = ChatPromptTemplate.from_template("""
    You are an expert insurance policy analyst. Use the provided policy context to answer the user's question.

    IMPORTANT INSTRUCTIONS:
    1. Base your answer ONLY on the provided context
    2. If multiple policy sections apply, explain how they interact
    3. If there are conditions or exclusions that apply, clearly state them
    4. If you find conflicting information, explain the conflict
    5. Always cite specific policy sections when making claims
    6. If you cannot find the answer in the context, say "I cannot find this information in the provided policy documents"

    Context from Policy Documents:
    {context}

    User's Question: {question}

    Analysis:
    """)
    
    # Chat model
    try:
        chat_model = ChatOpenAI(
            temperature=0,
            model='gpt-4o-mini',
            api_key=api_key
        )
    except Exception as e:
        print(f"OpenAI model initialization failed: {e}")
        return None
    
    # Build the enhanced chain
    def format_context(docs):
        formatted_sections = []
        for i, doc in enumerate(docs):
            section_info = ""
            if doc.metadata.get('section_type'):
                section_info += f"[{doc.metadata['section_type'].upper()}] "
            if doc.metadata.get('hierarchy'):
                section_info += f"Section {doc.metadata['hierarchy']}: "
            
            formatted_sections.append(f"{section_info}\n{doc.page_content}\n")
        
        return "\n---\n".join(formatted_sections)
    
    enhanced_chain = (
        {"context": rag_service.hybrid_retriever.get_relevant_documents | format_context, "question": lambda x: x}
        | enhanced_prompt
        | chat_model
    )
    
    return enhanced_chain, rag_service.hybrid_retriever

# Utility functions for source inspection
def query_with_sources(rag_chain, query: str, hybrid_retriever):
    """Query the RAG system and show both answer and sources"""
    
    # Get retrieved documents first
    retrieved_docs = hybrid_retriever.get_relevant_documents(query)
    
    # Get the answer
    answer = rag_chain.invoke(query)
    
    # Display results
    print("="*80)
    print(f"QUERY: {query}")
    print("="*80)
    print(f"ANSWER: {answer}")
    print("="*80)
    print("SOURCES USED:")
    print("="*80)
    
    for i, doc in enumerate(retrieved_docs, 1):
        print(f"\nSOURCE {i}:")
        print("-" * 40)
        print(f"Content: {doc.page_content[:500]}...")
        print(f"Section Type: {doc.metadata.get('section_type', 'N/A')}")
        print(f"Hierarchy: {doc.metadata.get('hierarchy', 'N/A')}")
        print(f"Page: {doc.metadata.get('page', 'N/A')}")
        print(f"Source File: {doc.metadata.get('source', 'N/A')}")
    
    return answer, retrieved_docs