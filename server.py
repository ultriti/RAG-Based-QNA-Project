
# import os
# import shutil
# import uuid
# from pathlib import Path
# from typing import List

# from dotenv import load_dotenv
# from fastapi import FastAPI, File, HTTPException, UploadFile
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel, Field

# from langchain_community.document_loaders import PyPDFLoader
# from langchain_community.vectorstores import Chroma
# from langchain_huggingface import HuggingFaceEmbeddings
# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_google_genai import ChatGoogleGenerativeAI

# load_dotenv()

# # --------------------------------------------------
# # Paths
# # --------------------------------------------------

# BASE_DIR = Path(__file__).resolve().parent
# UPLOAD_DIR = BASE_DIR / "uploads"
# CHROMA_DIR = BASE_DIR / "chroma_db"

# UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
# CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# # --------------------------------------------------
# # FastAPI application
# # --------------------------------------------------

# app = FastAPI(
#     title="PDF RAG API",
#     description="Upload PDFs and ask questions using RAG, ChromaDB and Gemini.",
#     version="1.0.0",
# )

# # Enable frontend requests. Restrict origins in production.
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=False,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # --------------------------------------------------
# # Embedding model and vector database
# # --------------------------------------------------

# embedding_model = HuggingFaceEmbeddings(
#     model_name="sentence-transformers/all-MiniLM-L6-v2"
# )

# vectorstore = Chroma(
#     persist_directory=str(CHROMA_DIR),
#     embedding_function=embedding_model,
#     collection_name="langchain",
# )

# retriever = vectorstore.as_retriever(
#     search_type="mmr",
#     search_kwargs={
#         "k": 4,
#         "fetch_k": 10,
#         "lambda_mult": 0.5,
#     },
# )

# # --------------------------------------------------
# # Gemini LLM
# # --------------------------------------------------

# llm = ChatGoogleGenerativeAI(
#     model="gemini-3.5-flash-lite",
#     temperature=0,
# )

# # --------------------------------------------------
# # Text splitting
# # --------------------------------------------------

# text_splitter = RecursiveCharacterTextSplitter(
#     chunk_size=1000,
#     chunk_overlap=150,
# )

# # --------------------------------------------------
# # RAG prompt
# # --------------------------------------------------

# prompt = ChatPromptTemplate.from_messages(
#     [
#         (
#             "system",
#             """
#             You are a helpful PDF question-answering assistant.

#             Answer using only the supplied context.
#             Do not use outside knowledge or invent information.

#             If the answer cannot be found in the context,
#             reply exactly:
#             "I can't find the answer in the PDF. Should I search on the web?"

#             Keep your answers clear and relevant.
#             """,
#         ),
#         (
#             "human",
#             """
#             Context:
#             {context}

#             Question:
#             {question}
#             """,
#         ),
#     ]
# )

# # --------------------------------------------------
# # Request schemas
# # --------------------------------------------------

# class QuestionRequest(BaseModel):
#     question: str = Field(..., min_length=1, max_length=5000)


# class QuestionResponse(BaseModel):
#     question: str
#     answer: str
#     sources: List[dict]


# # --------------------------------------------------
# # Health endpoint
# # --------------------------------------------------

# @app.get("/")
# def home():
#     return {
#         "message": "PDF RAG API is running",
#         "docs": "/docs",
#         "endpoints": ["/upload", "/ask", "/health"],
#     }


# @app.get("/health")
# def health():
#     return {
#         "status": "healthy",
#         "vector_database": "ChromaDB",
#         "indexed_chunks": vectorstore._collection.count(),
#     }


# # --------------------------------------------------
# # Upload PDF and create embeddings
# # --------------------------------------------------

# @app.post("/upload")
# def upload_pdf(file: UploadFile = File(...)):
#     if not file.filename:
#         raise HTTPException(
#             status_code=400,
#             detail="Please provide a filename.",
#         )

#     if Path(file.filename).suffix.lower() != ".pdf":
#         raise HTTPException(
#             status_code=400,
#             detail="Only PDF files are supported.",
#         )

#     original_filename = Path(file.filename).name
#     saved_path = UPLOAD_DIR / f"{uuid.uuid4().hex}.pdf"

#     try:
#         # Save the uploaded PDF to disk.
#         with saved_path.open("wb") as output_file:
#             shutil.copyfileobj(file.file, output_file)

#         # Basic PDF signature validation.
#         with saved_path.open("rb") as pdf_file:
#             if pdf_file.read(5) != b"%PDF-":
#                 raise HTTPException(
#                     status_code=400,
#                     detail="The uploaded file is not a valid PDF.",
#                 )

#         # Extract PDF text.
#         loader = PyPDFLoader(str(saved_path))
#         documents = loader.load()

#         if not documents or not any(
#             doc.page_content.strip() for doc in documents
#         ):
#             raise HTTPException(
#                 status_code=422,
#                 detail="No readable text found in this PDF. "
#                        "Scanned PDFs may require OCR.",
#             )

#         # Store the original filename in document metadata.
#         for document in documents:
#             document.metadata["source"] = original_filename

#         # Split pages into smaller chunks.
#         chunks = text_splitter.split_documents(documents)

#         if not chunks:
#             raise HTTPException(
#                 status_code=422,
#                 detail="No text chunks could be created from this PDF.",
#             )

#         # Generate embeddings and add chunks to persistent ChromaDB.
#         vectorstore.add_documents(chunks)

#         return {
#             "message": "PDF uploaded and indexed successfully.",
#             "filename": original_filename,
#             "pages_processed": len(documents),
#             "chunks_indexed": len(chunks),
#             "total_indexed_chunks": vectorstore._collection.count(),
#         }

#     except HTTPException:
#         raise

#     except Exception as exc:
#         raise HTTPException(
#             status_code=500,
#             detail=f"PDF processing failed: {str(exc)}",
#         ) from exc

#     finally:
#         file.file.close()


# # --------------------------------------------------
# # Ask questions about indexed PDFs
# # --------------------------------------------------

# @app.post("/ask", response_model=QuestionResponse)
# def ask_question(request: QuestionRequest):
#     question = request.question.strip()

#     if not question:
#         raise HTTPException(
#             status_code=400,
#             detail="Question cannot be empty.",
#         )

#     try:
#         # Ensure at least one document has been indexed.
#         if vectorstore._collection.count() == 0:
#             raise HTTPException(
#                 status_code=400,
#                 detail="No PDFs uploaded yet. Upload a PDF first.",
#             )

#         # Retrieve relevant chunks.
#         docs = retriever.invoke(question)

#         if not docs:
#             return QuestionResponse(
#                 question=question,
#                 answer=(
#                     "I can't find the answer in the PDF. "
#                     "Should I search on the web?"
#                 ),
#                 sources=[],
#             )

#         context = "\n\n".join(
#             f"[Source: {doc.metadata.get('source', 'Unknown PDF')}, "
#             f"Page: {doc.metadata.get('page', 'Unknown')}]\n"
#             f"{doc.page_content}"
#             for doc in docs
#         )

#         # Build the prompt and call Gemini.
#         final_prompt = prompt.invoke(
#             {
#                 "context": context,
#                 "question": question,
#             }
#         )

#         response = llm.invoke(final_prompt)

#         # Extract unique source filename/page pairs.
#         sources = []
#         seen = set()

#         for doc in docs:
#             source = doc.metadata.get("source", "Unknown PDF")
#             page = doc.metadata.get("page")

#             # PyPDFLoader page metadata is normally zero-based.
#             source_key = (source, page)

#             if source_key not in seen:
#                 seen.add(source_key)
#                 sources.append(
#                     {
#                         "filename": source,
#                         "page": page + 1 if isinstance(page, int) else None,
#                     }
#                 )

#         return QuestionResponse(
#             question=question,
#             answer=str(response.content),
#             sources=sources,
#         )

#     except HTTPException:
#         raise

#     except Exception as exc:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Question answering failed: {str(exc)}",
#         ) from exc


import shutil
import uuid
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# --------------------------------------------------
# Paths
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
CHROMA_DIR = BASE_DIR / "chroma_db"
STATIC_DIR = BASE_DIR / "static"  # index.html, style.css, script.js live here

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------
# FastAPI application
# --------------------------------------------------

app = FastAPI(
    title="PDF RAG API",
    description="Upload PDFs and ask questions using RAG, ChromaDB and Gemini.",
    version="1.0.0",
)

# CORS is no longer required when the frontend is served from the same
# server, but it is harmless to keep for external clients.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# Embedding model and vector database
# --------------------------------------------------

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

vectorstore = Chroma(
    persist_directory=str(CHROMA_DIR),
    embedding_function=embedding_model,
    collection_name="langchain",
)

retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={
        "k": 4,
        "fetch_k": 10,
        "lambda_mult": 0.5,
    },
)

# --------------------------------------------------
# Gemini LLM
# --------------------------------------------------

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0,
)

# --------------------------------------------------
# Text splitting
# --------------------------------------------------

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150,
)

# --------------------------------------------------
# RAG prompt
# --------------------------------------------------

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
            You are a helpful PDF question-answering assistant.

            Answer using only the supplied context.
            Do not use outside knowledge or invent information.

            If the answer cannot be found in the context,
            reply exactly:
            "I can't find the answer in the PDF. Should I search on the web?"

            Keep your answers clear and relevant.
            """,
        ),
        (
            "human",
            """
            Context:
            {context}

            Question:
            {question}
            """,
        ),
    ]
)

# --------------------------------------------------
# Request schemas
# --------------------------------------------------

class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=5000)


class QuestionResponse(BaseModel):
    question: str
    answer: str
    sources: List[dict]


# --------------------------------------------------
# API endpoints
# --------------------------------------------------

@app.get("/api")
def api_info():
    # The old "/" JSON route moved here, because "/" now serves the web UI.
    return {
        "message": "PDF RAG API is running",
        "docs": "/docs",
        "endpoints": ["/upload", "/ask", "/health"],
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "vector_database": "ChromaDB",
        "indexed_chunks": vectorstore._collection.count(),
    }


@app.post("/upload")
def upload_pdf(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Please provide a filename.")

    if Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    original_filename = Path(file.filename).name
    saved_path = UPLOAD_DIR / f"{uuid.uuid4().hex}.pdf"

    try:
        with saved_path.open("wb") as output_file:
            shutil.copyfileobj(file.file, output_file)

        with saved_path.open("rb") as pdf_file:
            if pdf_file.read(5) != b"%PDF-":
                raise HTTPException(
                    status_code=400,
                    detail="The uploaded file is not a valid PDF.",
                )

        loader = PyPDFLoader(str(saved_path))
        documents = loader.load()

        if not documents or not any(doc.page_content.strip() for doc in documents):
            raise HTTPException(
                status_code=422,
                detail="No readable text found in this PDF. "
                       "Scanned PDFs may require OCR.",
            )

        for document in documents:
            document.metadata["source"] = original_filename

        chunks = text_splitter.split_documents(documents)

        if not chunks:
            raise HTTPException(
                status_code=422,
                detail="No text chunks could be created from this PDF.",
            )

        vectorstore.add_documents(chunks)

        return {
            "message": "PDF uploaded and indexed successfully.",
            "filename": original_filename,
            "pages_processed": len(documents),
            "chunks_indexed": len(chunks),
            "total_indexed_chunks": vectorstore._collection.count(),
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"PDF processing failed: {str(exc)}",
        ) from exc

    finally:
        file.file.close()


@app.post("/ask", response_model=QuestionResponse)
def ask_question(request: QuestionRequest):
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        if vectorstore._collection.count() == 0:
            raise HTTPException(
                status_code=400,
                detail="No PDFs uploaded yet. Upload a PDF first.",
            )

        docs = retriever.invoke(question)

        if not docs:
            return QuestionResponse(
                question=question,
                answer="I can't find the answer in the PDF. Should I search on the web?",
                sources=[],
            )

        context = "\n\n".join(
            f"[Source: {doc.metadata.get('source', 'Unknown PDF')}, "
            f"Page: {doc.metadata.get('page', 'Unknown')}]\n"
            f"{doc.page_content}"
            for doc in docs
        )

        final_prompt = prompt.invoke({"context": context, "question": question})
        response = llm.invoke(final_prompt)

        sources = []
        seen = set()

        for doc in docs:
            source = doc.metadata.get("source", "Unknown PDF")
            page = doc.metadata.get("page")
            source_key = (source, page)

            if source_key not in seen:
                seen.add(source_key)
                sources.append(
                    {
                        "filename": source,
                        "page": page + 1 if isinstance(page, int) else None,
                    }
                )

        return QuestionResponse(
            question=question,
            answer=str(response.content),
            sources=sources,
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Question answering failed: {str(exc)}",
        ) from exc


# --------------------------------------------------
# Serve the frontend (MUST stay at the very bottom)
# --------------------------------------------------
# Mounted last so /upload, /ask, /health, /docs keep priority.
# html=True serves static/index.html at "/".
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="frontend")