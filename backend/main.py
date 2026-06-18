"""
AI page assistant Chrome Extension

Endpoints:

POST /summarize - takes raw page HTML, returns a concise summary
POST /ask - takes page HTML + question, returns a RAG-based answer
GET /health - health check
"""
import os
import hashlib
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_core.output_parsers import StrOutputParser
from bs4 import BeautifulSoup


app = FastAPI(
    title="AI page Assistant API",
    description="Backend for the Chrome extension",
    version="1.0.0"
)

# Allow requests from chrome extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"]
)

# In-memory FAISS cache - keyed by page content hash
_page_cache: dict[str, FAISS] = {}

# Schemas

class PageRequest(BaseModel):
    html: str
    url: Optional[str] = ""

class AskRequest(BaseModel):
    html: str
    question: str
    url: Optional[str] = ""

class SummaryResponse(BaseModel):
    url: str
    summary: str
    word_count: int

class AnswerResponse(BaseModel):
    url: str
    question: str
    answer: str
    source_chunks: int

# Helpers 

def extract_text(html: str) -> str:
    """Extract clean readable text from raw HTML"""
    soup = BeautifulSoup(html, "html.parser")
    # Remove script, style, nav, footer noise
    for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    # collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured.")
    return ChatOpenAI(model='gpt-4o-mini', temperature=0.5, api_key=api_key)

def get_embeddings():
    api_key = os.getenv("OPENAI_API_KEY")
    return OpenAIEmbeddings(api_key=api_key)

def build_vector_store(text: str, page_hash: str) -> FAISS:
    """Chunk text and build a FAISS vector store. Cache by page hash."""
    if page_hash in _page_cache:
        return _page_cache[page_hash]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=['\n\n', '\n', ". ", " "],
    )
    chunks = splitter.split_text(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="Could not extract meaningful text from this page.")
    
    docs = [Document(page_content=chunk) for chunk in chunks]
    vectorstore = FAISS.from_documents(docs, get_embeddings())
    _page_cache[page_hash] = vectorstore
    return vectorstore

# Endpoints
@app.get("/health")
def health():
    return {"status": "ok", "cached_pages": len(_page_cache)}

@app.post("/summarize", response_model=SummaryResponse)
def summarize(request: PageRequest):
    """
    Summarise a webpage.
    Called automatically when the extension popup opens.
    """
    text = extract_text(request.html)
    if len(text) < 100:
        return SummaryResponse(
            url=request.url,
            summary="This page doesn't contain enough readable text to summarise.",
            word_count=0,
        )

    # Truncate to first 4000 words for summary
    words = text.split()
    truncated = " ".join(words[:4000])
    word_count = len(words)

    llm = get_llm()
    prompt = f"""Summarise the following webpage content in 3-4 concise sentences.
Focus on the main topic, key points, and purpose of the page.
Be factual and neutral.

Page content:
{truncated}

Summary:
"""
    response = llm.invoke(prompt)
    return SummaryResponse(
        url=request.url,
        summary=response.content.strip(),
        word_count=word_count,
    )

@app.post("/ask", response_model=AnswerResponse)
def ask(request: AskRequest):
    """
    Answer a question about the current webpage using a pure LCEL RAG pipeline.
    """
    text = extract_text(request.html)
    if len(text) < 100:
        raise HTTPException(status_code=400, detail="Not enough readable content on this page.")
    page_hash = hashlib.md5(text[:2000].encode()).hexdigest()
    vectorstore = build_vector_store(text, page_hash)

    # 1. Define the prompt template (expects 'context' and 'question')
    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an AI assistant answering questions about a webpage.\n"
                   "Use only the context provided below to answer. If the answer is not in the context, "
                   "say \"I couldn't find information about that on this page.\"\n"
                   "Be concise and accurate.\n\n"
                   "Context:\n{context}"),
        ("human", "{question}")
    ])

    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    # Helper function to format list of Documents into a single string for the prompt
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    # 2. Build a pure LCEL Pipeline
    # Step A: Fetch and format the context, pass the question through, and preserve raw source docs
    map_setup = RunnableParallel(
        {
            "context": retriever | format_docs,
            "question": RunnablePassthrough(),
            "source_documents": retriever
        }
    )
    
    # Step B: Pipe the setup map into parallel processors for the final output keys
    rag_pipeline = map_setup | {
        "answer": qa_prompt | get_llm() | StrOutputParser(),
        "source_documents": lambda x: x["source_documents"]
    }

    # 3. Execute the pipeline by passing the raw question string directly
    result = rag_pipeline.invoke(request.question)
    
    answer = result.get("answer", "No answer generated.").strip()
    source_docs = result.get("source_documents", [])

    return AnswerResponse(
        url=request.url,
        question=request.question,
        answer=answer,
        source_chunks=len(source_docs),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)