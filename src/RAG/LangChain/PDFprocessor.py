import os

from typing import List, Dict, Any
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

from RAGClient import RAGClient


class DocumentProcessor:
    """Handle document processing and indexing for Chroma vector database."""

    def __init__(self, rag_client: RAGClient, chunk_size: int = 1000,
                 chunk_overlap: int = 200):
        """Initialize document processor."""
        self.rag_client = rag_client
        self.logger = rag_client.logger

        # Text splitter for chunking documents
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )

        self.logger.info(f"Document processor initialized - chunk_size: {chunk_size}, overlap: {chunk_overlap}")

    def find_pdf_files(self, directory: str) -> List[str]:
        """Find all PDF files in directory."""
        directory = Path(directory)

        if not directory.exists():
            self.logger.error(f"Directory not found: {directory}")
            return []


        pattern = "*.pdf"
        pdf_files = list(directory.glob(pattern))

        pdf_files = [str(f) for f in pdf_files]
        self.logger.info(f"Found {len(pdf_files)} PDF files in {directory}")

        return pdf_files

    def validate_pdf_files(self, pdf_paths: List[str]) -> List[str]:
        """Validate PDF files exist and are readable."""
        valid_files = []

        for pdf_path in pdf_paths:
            path = Path(pdf_path)

            if not path.exists():
                self.logger.error(f"PDF file not found: {pdf_path}")
                continue

            if not path.suffix.lower() == '.pdf':
                self.logger.warning(f"Not a PDF file: {pdf_path}")
                continue


            size = path.stat().st_size
            if size == 0:
                self.logger.warning(f"Empty PDF file: {pdf_path}")
                continue

            valid_files.append(str(path))
            self.logger.debug(f"Valid PDF: {pdf_path} ({size} bytes)")



        self.logger.info(f"Validated {len(valid_files)}/{len(pdf_paths)} PDF files")
        return valid_files

    def process_single_pdf(self, pdf_path: str) -> List[Document]:
        """Process a single PDF file into document chunks."""
        self.logger.info(f"Processing PDF: {pdf_path}")


        # Load PDF
        loader = PyPDFLoader(pdf_path)
        pages = loader.load()

        self.logger.debug(f"Loaded {len(pages)} pages from {pdf_path}")

        # Split into chunks
        chunks = self.text_splitter.split_documents(pages)

        # Add enhanced metadata
        for i, chunk in enumerate(chunks):
            chunk.id =  f"doc_{i}_{hash(chunk.page_content[:100])}"
            chunk.metadata.update({
                "source_file": pdf_path,
                "source": os.path.basename(pdf_path),
                "file_type": "pdf",
                "chunk_id": i,
                "total_chunks": len(chunks),
                "processed_at": "",  # Will be set when adding to DB
                "file_size": os.path.getsize(pdf_path)
            })

        self.logger.info(f"Created {len(chunks)} chunks from {pdf_path}")
        return chunks



    def process_pdf_directory(self, directory: str) -> List[Document]:
        """Process all PDFs in a directory."""
        self.logger.info(f"Processing PDF directory: {directory})")

        pdf_files = self.find_pdf_files(directory)
        if not pdf_files:
            return []

        valid_files = self.validate_pdf_files(pdf_files)
        if not valid_files:
            return []

        return self.process_pdf_batch(valid_files)

    def process_pdf_batch(self, pdf_paths: List[str]) -> List[Document]:
        """Process multiple PDF files."""
        self.logger.info(f"Processing batch of {len(pdf_paths)} PDF files")

        all_documents = []
        successful = 0

        for pdf_path in pdf_paths:
            chunks = self.process_single_pdf(pdf_path)
            if chunks:
                all_documents.extend(chunks)
                successful += 1

        self.logger.info(f"Successfully processed {successful}/{len(pdf_paths)} PDFs")
        self.logger.info(f"Total document chunks: {len(all_documents)}")

        return all_documents

    def add_documents(self, documents: List[Document]) -> bool:
        """Add processed documents to  database."""
        if not documents:
            self.logger.warning("No documents to add to database")
            return False

        self.logger.info(f"Adding {len(documents)} documents to database")

        doc_ids = self.rag_client.add_documents(documents)

        if doc_ids:
            self.logger.info(f"Successfully added {len(doc_ids)} documents to database")
            return True
        else:
            self.logger.error("Failed to add documents to database")
            return False



    def index_pdf_files(self, pdf_paths: List[str]) -> Dict[str, Any]:
        """Complete pipeline: process PDFs and add to database."""
        self.logger.info("Starting PDF indexing pipeline")

        # Validate files
        valid_files = self.validate_pdf_files(pdf_paths)
        if not valid_files:
            return {
                "success": False,
                "message": "No valid PDF files found",
                "files_processed": 0,
                "chunks_created": 0,
                "chunks_indexed": 0
            }

        # Process documents
        documents = self.process_pdf_batch(valid_files)
        if not documents:
            return {
                "success": False,
                "message": "No documents could be processed",
                "files_processed": 0,
                "chunks_created": 0,
                "chunks_indexed": 0
            }

        # Add to database
        success = self.add_documents(documents)

        result = {
            "success": success,
            "message": "PDF indexing completed successfully" if success else "Failed to index documents",
            "files_processed": len(valid_files),
            "chunks_created": len(documents),
            "chunks_indexed": len(documents) if success else 0
        }

        self.logger.info(f"Indexing pipeline completed: {result}")
        return result

    def index_directory(self, directory: str) -> Dict[str, Any]:
        """Index all PDFs in a directory."""
        self.logger.info(f"Indexing directory: {directory}")

        pdf_files = self.find_pdf_files(directory)
        if not pdf_files:
            return {
                "success": False,
                "message": f"No PDF files found in {directory}",
                "files_processed": 0,
                "chunks_created": 0,
                "chunks_indexed": 0
            }

        return self.index_pdf_files(pdf_files)

    def get_processing_stats(self, documents: List[Document]) -> Dict[str, Any]:
        """Get statistics about processed documents."""
        if not documents:
            return {"total_documents": 0}

        # Group by source file
        by_source = {}
        total_chars = 0

        for doc in documents:
            source = doc.metadata.get('source', 'Unknown')
            if source not in by_source:
                by_source[source] = {
                    'chunks': 0,
                    'total_chars': 0,
                    'pages': set()
                }

            by_source[source]['chunks'] += 1
            chunk_chars = len(doc.page_content)
            by_source[source]['total_chars'] += chunk_chars
            total_chars += chunk_chars

            if 'page' in doc.metadata:
                by_source[source]['pages'].add(doc.metadata['page'])

        # Calculate averages
        avg_chunk_size = total_chars / len(documents) if documents else 0

        stats = {
            "total_documents": len(documents),
            "total_characters": total_chars,
            "average_chunk_size": int(avg_chunk_size),
            "unique_sources": len(by_source),
            "by_source": {}
        }

        for source, data in by_source.items():
            stats["by_source"][source] = {
                "chunks": data['chunks'],
                "total_characters": data['total_chars'],
                "average_chunk_size": int(data['total_chars'] / data['chunks']),
                "unique_pages": len(data['pages'])
            }

        return stats

    def reindex_database(self, pdf_paths: List[str], clear_existing: bool = False) -> Dict[str, Any]:
        """Reindex database with new documents."""
        self.logger.info("Starting database reindexing")

        if clear_existing:
            self.logger.info("Clearing existing database")
            self.rag_client.clear_database()

        return self.index_pdf_files(pdf_paths)


def example_usage():
    """Example of how to use the document processor."""

    # Initialize RAG client
    rag_client = RAGClient(
        log_level="INFO",
        enable_notebook_logging=True
    )

    # Initialize processor
    processor = DocumentProcessor(rag_client)

    # Example 1: Index specific files
    pdf_files = [
        "data/Dubai Brochure.pdf",
        "data/Las Vegas Brochure.pdf"
    ]

    result = processor.index_pdf_files(pdf_files)
    print(f"Indexing result: {result}")

    # Example 2: Index entire directory
    result = processor.index_directory("data/pdfs")
    print(f"Directory indexing result: {result}")

    # Example 3: Get database info
    db_info = rag_client.get_database_info()
    print(f"Database info: {db_info}")

    # Example 4: Test queries
    queries = [
        "What destinations are available?",
        "Tell me about Dubai hotels"
    ]

    for query in queries:
        result = rag_client.ask_rag(query)
        print(f"Q: {query}")
        print(f"A: {result['answer'][:100]}...")
        print(f"Sources: {len(result['sources'])}\n")


if __name__ == "__main__":
    example_usage()