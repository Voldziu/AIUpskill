import logging

from typing import List
from langchain.schema import BaseRetriever, Document
from langchain_community.vectorstores import Chroma
from langchain_community.vectorstores.azuresearch import AzureSearch




class ChromaRetriever(BaseRetriever):
    vectorstore: Chroma
    k: int
    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, vectorstore: Chroma, k: int = 3):
        """Initialize with Chroma vectorstore."""
        super().__init__(vectorstore=vectorstore, k=k)
        self.vectorstore = vectorstore
        self.k = k


    def _get_relevant_documents(self, query: str) -> List[Document]:
        """Retrieve relevant documents using Chroma similarity search."""
        self.logger.info(f"Searching Chroma for: '{query}' (k={self.k})")


        # Chroma similarity search with scores
        docs_with_scores = self.vectorstore.similarity_search_with_score(
            query=query,
            k=self.k
        )

        # Convert to Document objects with score in metadata
        documents = []
        for doc, score in docs_with_scores:
            # Add score to metadata
            doc.metadata['score'] = float(score)
            documents.append(doc)

        self.logger.info(f"Retrieved {len(documents)} documents from Chroma")
        for i, doc in enumerate(documents):
            self.logger.debug(
                f"Doc {i + 1}: {doc.metadata.get('source', 'Unknown')} (score: {doc.metadata.get('score', 0):.3f})")

        return documents

