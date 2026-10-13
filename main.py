from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

vectorstore = Chroma(persist_directory="chroma_db", embedding_function=embedding_model)

retriever = vectorstore.as_retriever(
    search_type="mmr", search_kwargs={"k": 4, "fetch_k": 10, "lambda_mult": 0.5}
)

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", temperature=0)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
            You are a helpful AI assistant.
            Use only the provided context.

            If the answer is not available in the context,
            reply:
            "I can't find the answer in the PDF. Should I search on the web?"
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

print("RAG System Created")
print("Press 0 to Exit")

while True:
    query = input("\nYou: ")

    if query == "0":
        break

    docs = retriever.invoke(query)

    context = "\n\n".join([doc.page_content for doc in docs])

    final_prompt = prompt.invoke(
        {
            "context": context,
            "question": query,
        }
    )

    response = llm.invoke(final_prompt)

    print(f"\nAI: {response.content}")
