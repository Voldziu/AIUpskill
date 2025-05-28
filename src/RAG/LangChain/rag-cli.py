import argparse
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

from ChromaRAGClient import ChromaRAGClient
from PDFprocessor import ChromaDocumentProcessor


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))


def main():
    """Main CLI interface for Chroma RAG system."""

    parser = argparse.ArgumentParser(
        description="Chroma RAG Client - Local Vector Database RAG System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -q "What destinations are available?"
  %(prog)s -i --memory
  %(prog)s --index-pdfs file1.pdf file2.pdf
  %(prog)s --index-dir data/pdfs/ 
  %(prog)s --clear-db --index-dir data/
  %(prog)s --info
        """
    )

    # Query options
    parser.add_argument(
        "-q", "--query",
        type=str,
        help="Single query to process"
    )

    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Start interactive mode"
    )

    parser.add_argument(
        "--memory",
        action="store_true",
        help="Enable conversation memory"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    # Document indexing
    parser.add_argument(
        "--index-pdfs",
        nargs="+",
        metavar="FILE",
        help="Index specific PDF files"
    )

    parser.add_argument(
        "--index-dir",
        type=str,
        metavar="DIR",
        help="Index all PDFs in directory"
    )



    # Database management
    parser.add_argument(
        "--clear-db",
        action="store_true",
        help="Clear the vector database"
    )

    parser.add_argument(
        "--info",
        action="store_true",
        help="Show database information"
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show detailed processing statistics"
    )

    # Configuration
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of documents to retrieve (default: 3)"
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Document chunk size (default: 1000)"
    )

    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Document chunk overlap (default: 200)"
    )

    parser.add_argument(
        "--db-path",
        type=str,
        default="db/chroma_db",
        help="Path to Chroma database directory"
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level"
    )

    parser.add_argument(
        "--no-notebook-log",
        action="store_true",
        help="Disable notebook logging"
    )

    # Testing
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run system tests"
    )

    args = parser.parse_args()

    # Load environment
    load_dotenv()

    try:
        # Initialize RAG client
        print("🔧 Initializing Chroma RAG Client...")
        rag_client = ChromaRAGClient(
            log_level=args.log_level,
            enable_notebook_logging=not args.no_notebook_log,
            enable_memory=args.memory,
            persist_directory=args.db_path
        )

        # Override retriever settings
        if hasattr(rag_client.retriever, 'k'):
            rag_client.retriever.k = args.top_k

        # Database info mode
        if args.info:
            show_database_info(rag_client)
            return

        # Clear database
        if args.clear_db:
            print("⚠️  Clearing vector database...")
            rag_client.clear_database()
            print("✅ Database cleared successfully")

            # If no other operations, exit
            if not (args.index_pdfs or args.index_dir or args.query or args.interactive):
                return

        # Document indexing
        if args.index_pdfs or args.index_dir:
            processor = ChromaDocumentProcessor(
                rag_client,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap
            )

            if args.index_pdfs:
                print(f"📝 Indexing {len(args.index_pdfs)} PDF files...")
                result = processor.index_pdf_files(args.index_pdfs)
                print_indexing_result(result)

            elif args.index_dir:
                print(f"📁 Indexing PDFs from directory: {args.index_dir}")
                if not os.path.exists(args.index_dir):
                    print(f"❌ Directory not found: {args.index_dir}")
                    sys.exit(1)

                result = processor.index_directory(args.index_dir)
                print_indexing_result(result)

            # Show updated database info
            if result['success']:
                show_database_info(rag_client)

        # Statistics mode
        if args.stats:
            show_detailed_stats(rag_client)
            return

        # Test mode
        if args.test:
            run_system_tests(rag_client, args.verbose)
            return

        # Interactive mode
        if args.interactive:
            rag_client.interactive_mode()
            return

        # Single query mode
        if args.query:
            print("🔍 Processing query...")
            result = rag_client.ask_rag(args.query, verbose=args.verbose)

            print("=" * 60)
            print(f"Query: {result['query']}")
            print("=" * 60)

            if result['context_used']:
                print(f"Answer: {result['answer']}")

                if result['sources']:
                    print(f"\n📚 Sources ({len(result['sources'])}):")
                    for i, source in enumerate(result['sources'], 1):
                        print(f"  {i}. {source['title']} (Page: {source['page']}, Score: {source['score']:.3f})")
            else:
                print("❗ No relevant information found.")
                if "No documents found" in result['answer']:
                    print("💡 Add documents using: --index-dir data/pdfs/")

            return

        # No arguments provided
        print("Chroma RAG CLI - Local Vector Database RAG System")
        print("\nQuick start:")
        print("  1. Index documents: --index-dir data/pdfs/")
        print("  2. Ask questions: -q 'What information do you have?'")
        print("  3. Interactive mode: -i")
        print("\nUse --help for all options")

    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def show_database_info(rag_client: ChromaRAGClient):
    """Display database information."""
    print("\n📊 Database Information:")

    db_info = rag_client.get_database_info()

    for key, value in db_info.items():
        if key == "persist_directory":
            print(f"  📁 {key}: {value}")
        elif key == "total_documents":
            print(f"  📄 {key}: {value}")
        else:
            print(f"  🔧 {key}: {value}")

    # Additional file system info
    db_path = Path(rag_client.persist_directory)
    if db_path.exists():
        try:
            size = sum(f.stat().st_size for f in db_path.rglob('*') if f.is_file())
            print(f"  💾 Database size: {size / (1024 * 1024):.1f} MB")
        except:
            pass


def print_indexing_result(result: dict):
    """Print indexing results."""
    if result['success']:
        print("✅ Indexing completed successfully!")
        print(f"   📄 Files processed: {result['files_processed']}")
        print(f"   📝 Chunks created: {result['chunks_created']}")
        print(f"   💾 Chunks indexed: {result['chunks_indexed']}")
    else:
        print(f"❌ Indexing failed: {result['message']}")


def show_detailed_stats(rag_client: ChromaRAGClient):
    """Show detailed processing statistics."""
    print("📈 Detailed Statistics:")

    # Database info
    db_info = rag_client.get_database_info()
    print(f"\n🗄️  Database Overview:")
    print(f"   Total documents: {db_info.get('total_documents', 0)}")
    print(f"   Storage path: {db_info.get('persist_directory', 'Unknown')}")

    # Try to get more details from Chroma
    try:
        collection = rag_client.vectorstore._collection

        # Sample a few documents to analyze
        sample_docs = collection.peek(limit=10)

        if sample_docs and sample_docs['documents']:
            doc_lengths = [len(doc) for doc in sample_docs['documents']]
            avg_length = sum(doc_lengths) / len(doc_lengths)

            print(f"\n📝 Document Analysis (sample of {len(doc_lengths)}):")
            print(f"   Average chunk length: {avg_length:.0f} characters")
            print(f"   Min length: {min(doc_lengths)} characters")
            print(f"   Max length: {max(doc_lengths)} characters")

        # Metadata analysis
        if sample_docs and sample_docs['metadatas']:
            sources = set()
            for metadata in sample_docs['metadatas']:
                if metadata and 'source' in metadata:
                    sources.add(metadata['source'])

            print(f"\n📚 Sources (sample):")
            for source in sorted(sources):
                print(f"   - {source}")

    except Exception as e:
        print(f"   ⚠️  Could not retrieve detailed stats: {e}")


   

if __name__ == "__main__":
    main()