# from langchain_core.documents import Document
# from langchain_community.vectorstores import Chroma
# from langchain_community.embeddings import HuggingFaceEmbeddings
# from langchain_community.document_loaders import PyPDFLoader

# from dotenv import load_dotenv

# load_dotenv()


# data =  PyPDFLoader(r"E:\Personal Projects\Generative AI Projects\RAG-Based-QNA-Project\Deep Learning PDF.pdf")
# docs = data.load()

# print(docs[0].page_content)

# embedding_model = HuggingFaceEmbeddings()

# vectorstore = Chroma.from_documents(
#     documents = docs,
#     embedding = embedding_model,
#     persist_directory = 'chroma_db'
# )


from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

load_dotenv()

loader = PyPDFLoader(
    r"E:\Personal Projects\Generative AI Projects\RAG-Based-QNA-Project\Deep Learning PDF.pdf"
)

docs = loader.load()

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

vectorstore = Chroma.from_documents(
    documents=docs,
    embedding=embedding_model,
    persist_directory="chroma_db"
)

print("Vector DB created successfully!")