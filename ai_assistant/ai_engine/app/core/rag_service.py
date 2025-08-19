# services/3-ai-engine/app/core/rag_service.py

import logging
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.document_loaders import DirectoryLoader, CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from chromadb.config import Settings
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader

# Import the configuration settings
from ai_engine.app.core import config

# Basic logging configuration to monitor the service's behavior.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CiscoRAGService:
    """
    A service class to handle all RAG (Retrieval-Augmented Generation) operations.
    This includes loading data, creating a vector store, and running the query chain.
    """
    def __init__(self):
        """
        Initializes the service by setting up the vector store and the RAG chain.
        """
        logging.info("Initializing CiscoRAGService...")
        try:
            self.vectorstore = self._initialize_vectorstore()
            self.chain = self._build_rag_chain()
            logging.info("RAG Service initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to initialize CiscoRAGService: {e}")
            raise

def _initialize_vectorstore(self) -> Chroma:
    """
    Initializes the vector store. It loads from disk if it already exists,
    otherwise it creates a new one by processing source documents.
    """
    # Use OpenAI's embedding model
    embedding_function = OpenAIEmbeddings(model=config.EMBEDDING_MODEL)

    # Check if the vector store already exists and is not empty
    if os.path.exists(config.VECTOR_STORE_PATH) and os.listdir(config.VECTOR_STORE_PATH):
        logging.info(f"Loading existing Vector Store from: {config.VECTOR_STORE_PATH}")
        return Chroma(
            persist_directory=config.VECTOR_STORE_PATH,
            embedding_function=embedding_function
        )
    
    # If it doesn't exist, create it
    logging.info("Creating a new Vector Store...")
    try:
        logging.info("Loading documents from source...")
        # Load various file types from the raw data directory
        csv_loader = CSVLoader(file_path=f"{config.RAW_DATA_PATH}/product_catalog.csv")
        text_loader = DirectoryLoader(f"{config.RAW_DATA_PATH}/solution_guides/", glob="**/*.txt", show_progress=True)
        pdf_loader = DirectoryLoader(f"{config.RAW_DATA_PATH}/", glob="**/*.pdf", loader_cls=PyPDFLoader, show_progress=True)
        # Add other loaders as needed (e.g., for docx)

        all_loaders = [csv_loader, text_loader, pdf_loader]
        all_docs = []
        for loader in all_loaders:
            all_docs.extend(loader.load())
        
        logging.info(f"Loaded {len(all_docs)} documents.")

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP
        )
        splits = text_splitter.split_documents(all_docs)
        logging.info(f"Documents split into {len(splits)} chunks.")

        logging.info("Persisting the Vector Store...")
        vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=embedding_function,
            persist_directory=config.VECTOR_STORE_PATH,
            # Disable anonymized telemetry for enterprise readiness
            settings=Settings(anonymized_telemetry=False)
        )
        logging.info(f"Vector Store created and persisted at: {config.VECTOR_STORE_PATH}")
        return vectorstore
    except Exception as e:
        logging.error(f"Error creating new Vector Store: {e}")
        raise

    def _build_rag_chain(self):
        """
        Constructs the RAG chain using the LLM, a prompt template, and the retriever.
        
        Returns:
            Runnable: The executable LangChain RAG chain.
        """
        retriever = self.vectorstore.as_retriever()
        llm = ChatOpenAI(model_name=config.LLM_MODEL, temperature=0.1)

        # This prompt template is crucial for guiding the LLM's behavior.
        prompt_template = """
        You are an expert Cisco product assistant. Your role is to help a salesperson create a quote.
        Use ONLY the context provided below to answer the question. Do not make up products or information.
        Be clear, concise, and justify your recommendations based on the context.

        Context:
        {context}

        Salesperson's Question:
        {question}

        Expert Answer:
        """
        prompt = PromptTemplate.from_template(prompt_template)

        # The LCEL (LangChain Expression Language) chain definition.
        rag_chain = (
            {"context": retriever, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )
        return rag_chain

    def generate_response(self, query: str) -> str:
        """
        Generates a response for a given query using the RAG chain.
        This is the main public method to be called by the API.

        Args:
            query (str): The user's question in natural language.

        Returns:
            str: The AI-generated response.
        """
        logging.info(f"Received new query: {query}")
        try:
            response = self.chain.invoke(query)
            logging.info("Response generated successfully.")
            return response
        except Exception as e:
            logging.error(f"Error invoking RAG chain: {e}")
            # In a real app, you might return a more structured error object.
            return "An error occurred while processing your request."