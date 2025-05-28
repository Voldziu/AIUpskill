import os
import json
import sys
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
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers import create_notebook


from ChromaRetriever import ChromaRetriever




class ChromaRAGClient:
    """LangChain RAG client using local Chroma vector database."""

    def __init__(self, log_level: str = "INFO", enable_notebook_logging: bool = True,
                 enable_memory: bool = False, persist_directory: str = "./db/chroma_db"):
        """Initialize Chroma-based RAG client."""

        self.logger = None # Initialize later in _setup_logging

        load_dotenv("../.env", override=True)
        self.enable_notebook_logging = enable_notebook_logging
        self.enable_memory = enable_memory
        self.persist_directory = persist_directory
        self._setup_logging(log_level)

        self.logger.info("Initializing Chroma RAG Client...")

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

        # Initialize or load Chroma vectorstore
        vectorstore = Chroma(
            collection_name="rag_documents",
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory
        )
        self.vectorstore = vectorstore

        # Initialize retriever
        self.retriever = ChromaRetriever(
            vectorstore=vectorstore,
            k=int(os.getenv("TOP_K_RESULTS", 3))
        )

        # Create prompt template
        self.prompt_template =None
        self._setup_prompt_template()

        # Initialize memory if enabled
        self.memory = None
        if self.enable_memory:
            self.memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                output_key="answer"
            )

        # Initialize text splitter for document processing
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )

        self.logger.info("Chroma RAG Client initialized successfully")
        self.logger.info(f"Vector database: {self.persist_directory}")
        self.logger.info(f"Collection size: {self.vectorstore._collection.count()} documents")



    def _setup_prompt_template(self):
        self.prompt_template =  PromptTemplate(
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

    def _setup_logging(self, log_level: str):
        """Setup logging configuration."""
        os.makedirs("logs", exist_ok=True)

        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        formatter = logging.Formatter(
            fmt='%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler = logging.FileHandler('logs/chroma_rag.log')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)

        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.propagate = False

        self.logger = logger

    def add_documents(self, documents: List[Document]) -> List[str]:
        """Add documents to Chroma vector database."""
        self.logger.info(f"Adding {len(documents)} documents to Chroma")


        # Add documents to vectorstore
        doc_ids = self.vectorstore.add_documents(documents)

        # Persist the database
        self.vectorstore.persist()

        self.logger.info(f"Successfully added {len(doc_ids)} documents to Chroma")
        self.logger.info(f"Total documents in collection: {self.vectorstore._collection.count()}")

        return doc_ids



    def process_pdf_files(self, pdf_paths: List[str]) -> List[Document]:
        """Process PDF files and add to vector database."""
        self.logger.info(f"Processing {len(pdf_paths)} PDF files")

        all_documents = []

        for pdf_path in pdf_paths:
            self.logger.info(f"Processing PDF: {pdf_path}")

            # Load PDF
            loader = PyPDFLoader(pdf_path)
            documents = loader.load()

            # Split into chunks
            chunks = self.text_splitter.split_documents(documents)

            # Add metadata
            for chunk in chunks:
                chunk.metadata.update({
                    "source_file": pdf_path,
                    "file_type": "pdf",
                    "processed_at": datetime.now().isoformat(),
                    "source": os.path.basename(pdf_path)  # For compatibility
                })

            all_documents.extend(chunks)
            self.logger.info(f"Created {len(chunks)} chunks from {pdf_path}")



        # Add to Chroma
        if all_documents:
            doc_ids = self.add_documents(all_documents)
            self.logger.info(f"Added {len(doc_ids)} document chunks to vector database")

        return all_documents

    def clear_database(self):
        """Clear all documents from Chroma database."""
        self.logger.warning("Clearing Chroma database")

        # Delete the collection
        self.vectorstore.delete_collection()

        # Recreate empty collection
        self.vectorstore = Chroma(
            collection_name="rag_documents",
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory
        )

        # Update retriever
        self.retriever.vectorstore = self.vectorstore

        self.logger.info("Chroma database cleared successfully")



    def get_database_info(self) -> Dict[str, Any]:
        """Get information about the vector database."""

        count = self.vectorstore._collection.count()
        return {
            "total_documents": count,
            "collection_name": "rag_documents",
            "persist_directory": self.persist_directory,
            "embedding_model": os.getenv("EMBEDDING_MODEL_NAME")
        }


    def ask_rag(self, query: str, verbose: bool = False) -> Dict[str, Any]:
        """Main RAG function using LangChain chains with Chroma."""
        self.logger.info(f"Processing RAG query: '{query}'")


        # Check if database has documents
        doc_count = self.vectorstore._collection.count()
        if doc_count == 0:
            return {
                "query": query,
                "answer": "No documents found in the database. Please add documents first using process_pdf_files().",
                "sources": [],
                "context_used": False,
                "num_sources": 0
            }

        if self.enable_memory and self.memory:
            # Use conversational chain with memory
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
            # Use stateless RetrievalQA chain
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

        # Format response
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

        # Log to notebook if enabled
        if self.enable_notebook_logging and response["context_used"]:
            self._log_to_notebook(query, answer, sources)

        self.logger.info(f"RAG query completed with {len(sources)} sources")
        return response

    def _log_to_notebook(self, query: str, answer: str, sources: List[Dict[str, Any]]):
        """Log query and response to Jupyter notebook."""
        notebook_path = "notebooks/chroma_queries.ipynb"
        os.makedirs("notebooks", exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query_id = f"CQ{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        cell_content = f'''# Chroma RAG Query #{query_id} - {timestamp}

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
                "query_id": query_id,
                "chroma_version": True
            },
            "source": cell_content.split('\n')
        }

        # Load or create notebook
        if os.path.exists(notebook_path):
            with open(notebook_path, 'r', encoding='utf-8') as f:
                notebook = json.load(f)
        else:
            notebook = create_notebook(timestamp)

        notebook["cells"].append(new_cell)
        notebook["cells"].append({
            "cell_type": "markdown",
            "metadata": {},
            "source": ["---", ""]
        })

        with open(notebook_path, 'w', encoding='utf-8') as f:
            json.dump(notebook, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Query logged to notebook: {notebook_path}")

    def interactive_mode(self):
        """Interactive RAG session with Chroma."""
        print("🚀 Chroma RAG Client - Interactive Mode")
        print("Type 'quit' or 'exit' to end session")
        print("Type 'info' to see database information")
        print("Type 'memory on/off' to toggle conversation memory")
        print("Type 'help' for commands")
        print("-" * 50)

        # Show database info at start
        db_info = self.get_database_info()
        print(f"📊 Database: {db_info.get('total_documents', 0)} documents loaded")

        while True:
            try:
                user_input = input("\n💬 Ask a question: ").strip()

                if user_input.lower() in ['quit', 'exit']:
                    print("👋 Goodbye!")
                    break

                if user_input.lower() == 'help':
                    print("""
                        Available commands:
                        - Ask any question for RAG-powered answers
                        - 'info' - Show database information
                        - 'memory on/off' - Toggle conversation memory
                        - 'quit' or 'exit' - End session
                        - 'help' - Show this message
                    """)
                    continue

                if user_input.lower() == 'info':
                    db_info = self.get_database_info()
                    print(f"📊 Database Information:")
                    for key, value in db_info.items():
                        print(f"  {key}: {value}")
                    continue

                if user_input.lower().startswith('memory'):
                    if 'on' in user_input.lower():
                        self.enable_memory = True
                        if not self.memory:
                            self.memory = ConversationBufferMemory(
                                memory_key="chat_history",
                                return_messages=True,
                                output_key="answer"
                            )
                        print("🧠 Memory enabled - conversation context will be maintained")
                    elif 'off' in user_input.lower():
                        self.enable_memory = False
                        print("🧠 Memory disabled - each query will be independent")
                    continue

                if not user_input:
                    continue

                # Process query
                result = self.ask_rag(user_input, verbose=True)

                if not result['context_used']:
                    print("❗ No relevant information found for your question.")
                    if result['answer'].startswith('No documents found'):
                        print("💡 Add documents using: process_pdf_files(['file1.pdf', 'file2.pdf'])")
                else:
                    print(f"\n✅ Answer:")
                    print(result['answer'])

                    if result['sources']:
                        print(f"\n📚 Sources ({len(result['sources'])}):")
                        for i, source in enumerate(result['sources'], 1):
                            print(f"  {i}. {source['title']} (Page: {source['page']}, Score: {source['score']:.3f})")

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")


# Backward compatibility wrapper
class AzureRAGClient(ChromaRAGClient):
    """Backward compatibility wrapper."""

    def ask(self, query: str, verbose: bool = False) -> Dict[str, Any]:
        """Maintain compatibility with existing ask() method."""
        return self.ask_rag(query, verbose)