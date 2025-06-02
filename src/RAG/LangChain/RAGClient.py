import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain.chains import RetrievalQA
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain_community.vectorstores import Chroma
from langchain_community.vectorstores.azuresearch import AzureSearch
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

from opencensus.ext.azure.log_exporter import AzureLogHandler

current_dir = os.path.dirname(os.path.abspath(__file__))

from ChromaRetriever import ChromaRetriever

class RAGClient:
    """LangChain RAG client using remote or local database."""

    def __init__(self, log_level: str = "INFO", enable_notebook_logging: bool = True,
                 enable_memory: bool = False, persist_directory: str = "./db/chroma_db", 
                 local: bool = False, verbose: bool = True, connection_string: str = None):
        """Initialize RAG client."""
        
        # Load environment variables
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        env_path = os.path.join(parent_dir, '.env')
        load_dotenv(env_path, override=True)
        
        self.enable_notebook_logging = enable_notebook_logging
        self.enable_memory = enable_memory
        self.persist_directory = persist_directory
        self.local = local
        self.verbose = verbose
        self.connection_string = connection_string
        self.logger = None 
        self._setup_logging(log_level)
        if self.verbose:
            self.logger.info("Initializing RAG Client...")

        # Initialize Azure embeddings
        self.embeddings = AzureOpenAIEmbeddings(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            deployment=os.getenv("EMBEDDING_MODEL_NAME"),
            api_version="2024-12-01-preview"
        )

        # Initialize LangChain LLM
        self.llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            deployment_name=os.getenv("CHAT_MODEL_NAME"),
            api_version="2024-12-01-preview",
            temperature=float(os.getenv("TEMPERATURE", 0.6)),
            max_tokens=int(os.getenv("MAX_TOKENS", 500))
        )

        # Initialize vectorstore
        self.vectorstore = None
        self.retriever = None
        self._setup_vectorstore(local)

        # Create prompt template
        self.prompt_template = None
        self._setup_prompt_template()

        # Initialize memory if enabled
        self.memory = None
        if self.enable_memory:
            self.memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                output_key="answer"
            )

        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )

        if self.verbose:
            self.logger.info("RAG Client initialized successfully")
            self.logger.info(f"Vector database: {self.persist_directory}")

    def _setup_prompt_template(self):
        self.prompt_template = PromptTemplate(
            template="""You are a helpful AI assistant that answers questions based on the provided context documents.

            Instructions:
            - Use only the information provided in the context documents to answer the question
            - If the context doesn't contain enough information to answer the question, say so clearly
            - Cite your sources by referencing the document titles when possible
            - Be concise but comprehensive in your responses
            - If there are conflicting information in the documents, acknowledge this
            
            Context Documents:
            {context}
            
            Question: {question}
            
            Answer:""",
            input_variables=["context", "question"]
        )

    def _setup_vectorstore(self, local):
        if local:
            vectorstore = Chroma(
                collection_name="rag_documents",
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory
            )
            self.vectorstore = vectorstore
            self.retriever = ChromaRetriever(
                vectorstore=vectorstore,
                k=int(os.getenv("TOP_K_RESULTS", 3))
            )
        else:
            vectorstore = AzureSearch(
                azure_search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
                azure_search_key=os.getenv("AZURE_SEARCH_API_KEY"),
                index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
                embedding_function=self.embeddings,
            )
            self.vectorstore = vectorstore
            self.retriever = vectorstore.as_retriever(
                search_type="similarity",
                k=int(os.getenv("TOP_K_RESULTS", 3)),
            )
        
    def _setup_logging(self, log_level: str):
        """Setup logging configuration."""
        #os.makedirs("logs", exist_ok=True)

        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        formatter = logging.Formatter(
            fmt='%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        

        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        
        azure_handler = AzureLogHandler(connection_string=self.connection_string)
        azure_handler.setLevel(logging.INFO)

        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
       
       
        logger.addHandler(console_handler)
        logger.addHandler(azure_handler)
        logger.propagate = False

        self.logger = logger

    def add_documents(self, documents: List[Document]) -> List[str]:
        """Add documents to vector database."""
        if self.verbose:
            self.logger.info(f"Adding {len(documents)} documents")

        doc_ids = self.vectorstore.add_documents(documents, ids=[doc.id for doc in documents])

        if self.local:
            self.vectorstore.persist()

        if self.verbose:
            self.logger.info(f"Successfully added {len(doc_ids)} documents")
        
        return doc_ids

    def process_pdf_files(self, pdf_paths: List[str]) -> List[Document]:
        """Process PDF files and add to vector database."""
        if self.verbose:
            self.logger.info(f"Processing {len(pdf_paths)} PDF files")

        all_documents = []

        for pdf_path in pdf_paths:
            if self.verbose:
                self.logger.info(f"Processing PDF: {pdf_path}")

            loader = PyPDFLoader(pdf_path)
            documents = loader.load()
            chunks = self.text_splitter.split_documents(documents)

            for chunk in chunks:
                chunk.metadata.update({
                    "source_file": pdf_path,
                    "file_type": "pdf",
                    "processed_at": datetime.now().isoformat(),
                    "source": os.path.basename(pdf_path)
                })

            all_documents.extend(chunks)
            if self.verbose:
                self.logger.info(f"Created {len(chunks)} chunks from {pdf_path}")

        if all_documents:
            doc_ids = self.add_documents(all_documents)
            if self.verbose:
                self.logger.info(f"Added {len(doc_ids)} document chunks to vector database")

        return all_documents

    def clear_database(self):
        """Clear all documents from database."""
        if self.verbose:
            self.logger.warning("Clearing database")

        
        
        if not self.local:
            search_client = self.vectorstore.client
            
            # Search for all documents to get their IDs
            results = search_client.search("*", select="id")
            
            doc_ids = [doc["id"] for doc in results]
        
            if doc_ids:
                # Delete documents by ID
                search_client.delete_documents([{"id": doc_id} for doc_id in doc_ids])
                if self.verbose:
                    self.logger.info(f"Deleted {len(doc_ids)} documents from Azure Search")
            else:
                if self.verbose:
                    self.logger.info("No documents found to delete")
        else:
            self.vectorstore.delete_collection()
            
        self._setup_vectorstore(self.local)  # Reinitialize vectorstore after clearing
            

        
        
        if self.verbose:
            self.logger.info("Database cleared successfully")

    def get_database_info(self) -> Dict[str, Any]:
        """Get information about the vector database."""
        return {
            "collection_name": "rag_documents",
            "persist_directory": self.persist_directory,
            "embedding_model": os.getenv("EMBEDDING_MODEL_NAME")
        }

    def ask_rag(self, query: str, verbose: bool = False) -> Dict[str, Any]:
        """Main RAG function."""
        if self.verbose:
            self.logger.info(f"Processing RAG query: '{query}'")

        if self.local:
            doc_count = self.vectorstore._collection.count()
        else:
            doc_count = 1

        if doc_count == 0:
            return {
                "query": query,
                "answer": "No documents found in the database. Please add documents first.",
                "sources": [],
                "context_used": False,
                "num_sources": 0
            }

        if self.enable_memory and self.memory:
            qa_chain = ConversationalRetrievalChain.from_llm(
                llm=self.llm,
                retriever=self.retriever,
                memory=self.memory,
                combine_docs_chain_kwargs={"prompt": self.prompt_template},
                return_source_documents=True,
                verbose=verbose
            )
            result = qa_chain({"question": query})
            answer = result["answer"]
            source_docs = result.get("source_documents", [])
        else:
            qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=self.retriever,
                chain_type_kwargs={"prompt": self.prompt_template},
                return_source_documents=True,
                verbose=verbose
            )
            result = qa_chain({"query": query})
            answer = result["result"]
            source_docs = result.get("source_documents", [])

        sources = [
            {
                "title": doc.metadata.get("source", "Unknown"),
                "source": doc.metadata.get("source_file", doc.metadata.get("source", "Unknown")),
                "score": doc.metadata.get("score", 0),
                "page": doc.metadata.get("page", "N/A")
            }
            for doc in source_docs
        ]

        response = {
            "query": query,
            "answer": answer,
            "sources": sources,
            "context_used": len(sources) > 0,
            "num_sources": len(sources)
        }

        if self.enable_notebook_logging and response["context_used"]:
            self._log_to_notebook(query, answer, sources)

        if self.verbose:
            self.logger.info(f"RAG query completed with {len(sources)} sources")
            
        return response

    def _log_to_notebook(self, query: str, answer: str, sources: List[Dict[str, Any]]):
        """Log query and response to Jupyter notebook."""
        notebook_path = "notebooks/chroma_queries.ipynb"
        os.makedirs("notebooks", exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query_id = f"CQ{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        cell_content = f'''# RAG Query #{query_id} - {timestamp}

## Question
{query}

## Answer
{answer}

## Sources ({len(sources)})
'''

        for i, source in enumerate(sources, 1):
            cell_content += f'''
### Source {i}
- **File**: {source.get('source', 'Unknown')}
- **Page**: {source.get('page', 'N/A')}
- **Similarity Score**: {source.get('score', 0):.3f}
'''

        new_cell = {
            "cell_type": "markdown",
            "metadata": {
                "query_timestamp": timestamp,
                "query_id": query_id
            },
            "source": cell_content.split('\n')
        }

        if os.path.exists(notebook_path):
            with open(notebook_path, 'r', encoding='utf-8') as f:
                notebook = json.load(f)
        else:
            notebook = {"cells": []}

        notebook["cells"].append(new_cell)
        notebook["cells"].append({
            "cell_type": "markdown",
            "metadata": {},
            "source": ["---", ""]
        })

        with open(notebook_path, 'w', encoding='utf-8') as f:
            json.dump(notebook, f, indent=2, ensure_ascii=False)

        if self.verbose:
            self.logger.info(f"Query logged to notebook: {notebook_path}")

# Backward compatibility wrapper
class AzureRAGClient(RAGClient):
    """Backward compatibility wrapper."""
    
    def ask(self, query: str, verbose: bool = False) -> Dict[str, Any]:
        """Maintain compatibility with existing ask() method."""
        return self.ask_rag(query, verbose)