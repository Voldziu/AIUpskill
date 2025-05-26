import os
import json
import argparse
import logging

from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential


class AzureRAGClient:


    def __init__(self, log_level:str = "INFO"):

        load_dotenv(".env",override=True)




        self.logger = None

        self._setup_logging(log_level)

        self.logger.info("Initializing Azure RAG Client...")

        # Azure OpenAI Configuration
        self.openai_client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-12-01-preview",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        self.chat_deployment = os.getenv("CHAT_MODEL_NAME")
        self.embedding_deployment = os.getenv("EMBEDDING_MODEL_NAME")


        self.search_client = SearchClient(
            endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
            index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
            credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_API_KEY"))
        )

        # RAG Configuration
        self.max_tokens = int(os.getenv("MAX_TOKENS"))
        self.temperature = float(os.getenv("TEMPERATURE"))
        self.top_k_results = int(os.getenv("TOP_K_RESULTS"))

    def _setup_logging(self, log_level: str):


        os.makedirs("logs", exist_ok=True)


        numeric_level = getattr(logging, log_level.upper(), logging.INFO)

        formatter = logging.Formatter(
            fmt='%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


        file_handler = logging.FileHandler('logs/azure_rag.log')
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

    def generate_embeddings(self, text: str) -> List[float]:
        """

        Returns embeddings for the given text using Azure OpenAI.
        In case of an error, returns an empty list.

        """

        response = self.openai_client.embeddings.create(
            model=self.embedding_deployment,
            input=text
        )


        if response.data and response.data[0].embedding:
            self.logger.debug("Embeddings generated successfully")
            return response.data[0].embedding
        else:
            self.logger.error("Failed to generate embeddings: Invalid response status")
            return []


    def search_documents(self, query: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search for relevant documents using vector similarity.
        Returns empty list if no documents are found or if embeddings generation fails.
        """
        if top_k is None:
            top_k = self.top_k_results #use default value if not provided

        self.logger.info(f"Searching documents for query: '{query}' (top_k={top_k})")

        # generate embeddings for the query
        query_embedding = self.generate_embeddings(query)


        if not query_embedding:
            self.logger.error("Failed to generate query embeddings")
            return []

        self.logger.info(f"Query embeddings generated successfully: {len(query_embedding)} dimensions")

        # Create vector query
        vector_query = VectorizedQuery(
            vector=query_embedding,
            k_nearest_neighbors=top_k,
            fields="contentVector"  # Adjust field name based on your index
        )

        # Perform hybrid search (vector + text)
        results = self.search_client.search(
            search_text=query,
            vector_queries=[vector_query],
            select=["id", "content", "title", "url", "filepath", "meta_json_string"],
            top=top_k
        )

        documents = [
            {
                "id": doc.get("id", ""),
                "content": doc.get("content", ""),
                "title": doc.get("title", ""),
                "url": doc.get("url", ""),
                "filepath": doc.get("filepath", ""),
                "meta_json_string": doc.get("meta_json_string", ""),
                "score": doc.get("@search.score", 0),
                # Map to standard fields for compatibility
                "source": doc.get("url") or doc.get("filepath", "Unknown")
            }
            for doc in results
        ]

        self.logger.info(f"Retrieved {len(documents)} documents")
        for i, doc in enumerate(documents):
            self.logger.debug(f"Document {i + 1}: {doc['title']} (score: {doc['score']:.3f})")

        return documents



    def create_rag_prompt(self, query: str, context_docs: List[Dict[str, Any]]) -> str:
        """Create a RAG prompt with context and query."""

        # Build context from retrieved documents
        context_parts = []
        for i, doc in enumerate(context_docs, 1):
            source_info = f"Source: {doc.get('source', 'Unknown')}"
            if doc.get('title'):
                source_info += f" - {doc['title']}"

            context_parts.append(f"Document {i}:\n{source_info}\n{doc['content']}\n")

        context = "\n".join(context_parts)

        system_prompt = """
        You are a helpful AI assistant that answers questions based on the provided context documents. 

        Instructions:
        - Use only the information provided in the context documents to answer the question
        - If the context doesn't contain enough information to answer the question, say so clearly - don't make assumptions
        - Cite your sources by referencing the document numbers when possible
        - Be concise but comprehensive in your responses
        - If there are conflicting information in the documents, acknowledge this
        
        Context Documents:
        {context}
        
        Question: {query}
        
        Answer:
        
        """

        self.logger.info(f"Creating RAG prompt for query: '{query}' with {len(context_docs)} context documents")

        return system_prompt.format(context=context, query=query)

    def generate_response(self, prompt: str) -> str:
        """
        Generate response using Azure OpenAI.
        Returns the generated text or an empty string if generation fails."""

        self.logger.debug("Generating response from Azure OpenAI")

        response = self.openai_client.chat.completions.create(
            model=self.chat_deployment,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        print(response)
        if response.choices:

            generated_text = response.choices[0].message.content.strip()
            self.logger.info(f"Generated response ({len(generated_text)} chars)")
            return generated_text

        else:
            self.logger.error(f"Failed to generate response: {response.status_code} - {response.error}")
            return ""



    def ask(self, query: str, verbose: bool = False) -> Dict[str, Any]:
        """Main RAG pipeline: 1. search, 2. retrieve, and 3. generate."""

        self.logger.info(f"Processing RAG query: '{query}'")


        # Step 1: Retrieve relevant documents
        documents = self.search_documents(query)

        if not documents:
            return {
                "query": query,
                "answer": "I couldn't find any relevant information to answer your question.",
                "sources": [],
                "context_used": False
            }

        self.logger.info(f"Found {len(documents)} relevant documents")

        if verbose:
            print(f"📚 Found {len(documents)} relevant documents")
            for i, doc in enumerate(documents, 1):
                print(f"  {i}. {doc.get('title', 'Untitled')} (Score: {doc.get('score', 0):.3f})")



        # Step 2: Create RAG prompt with context

        rag_prompt = self.create_rag_prompt(query, documents)

        if verbose:
            print("🤖 Generating response...")

        # Step 3: Generate response
        answer = self.generate_response(rag_prompt)


        result = {
            "query": query,
            "answer": answer,
            "sources": [
                {
                    "title": doc.get("title", "Untitled"),
                    "source": doc.get("source", "Unknown"),
                    "score": doc.get("score", 0)
                }
                for doc in documents
            ],
            "context_used": True,
            "num_sources": len(documents)
        }

        self.logger.info(f"RAG query completed successfully with {len(documents)} sources")

        return result


    def interactive_mode(self):
        """Start interactive RAG session."""
        print("🚀 Azure RAG Client - Interactive Mode")
        print("Type 'quit' or 'exit' to end the session")
        print("Type 'help' for available commands")
        print("-" * 50)

        while True:
            try:
                user_input = input("\n💬 Ask a question: ").strip()

                if user_input.lower() in ['quit', 'exit']:
                    print("👋 Goodbye!")
                    break

                if user_input.lower() == 'help':
                    print("""
                        Available commands:
                        - Ask any question to get RAG-powered answers
                        - 'quit' or 'exit' to end session
                        - 'help' to show this message
                    """)
                    continue

                if not user_input:
                    continue



                self.logger.info(f"Interactive query: '{user_input}'")

                # Process the query
                result = self.ask(user_input, verbose=True)

                if not result['context_used']:
                    print("❗ No answers found for your question. Please ask another question....")
                    continue
                else:

                    print(f"\n✅ Answer:")
                    print(result['answer'])

                if result['sources']:
                    self.logger.info(f"\n📖 Sources ({len(result['sources'])}):")

                    for i, source in enumerate(result['sources'], 1):
                        self.logger.info(f"Source {i}: {source['title']} - {source['source']} (Score: {source['score']:.3f})")

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
