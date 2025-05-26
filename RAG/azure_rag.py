
import argparse
from dotenv import load_dotenv

from RagClient import AzureRAGClient

def main():
    """Main CLI interface."""

    DEFAULT_TOP_K = 5
    parser = argparse.ArgumentParser(
        description="Azure RAG Client - Retrieval Augmented Generation"
    )

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
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help="Number of documents to retrieve (default: 5)"
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)"
    )

    args = parser.parse_args()

    # Initialize RAG client with logging
    rag_client = AzureRAGClient(log_level=args.log_level)

    # Override top_k if they were specified in the arguments
    if args.top_k != DEFAULT_TOP_K:
        rag_client.top_k_results = args.top_k

    if args.interactive:
        # Interactive mode will take over the console
        rag_client.interactive_mode()

    elif args.query:
        # Single query mode
        result = rag_client.ask(args.query, verbose=args.verbose)

        print("=" * 60)
        print(f"Query: {result['query']}")
        print("=" * 60)
        print(f"Answer: {result['answer']}")

        if result['sources']:
            print(f"\nSources ({len(result['sources'])}):")
            for i, source in enumerate(result['sources'], 1):
                print(f"  {i}. {source['title']} - {source['source']}")

    else:
        # No arguments provided
        print("Please provide either --query or --interactive flag")
        print("Use --help for more information")


if __name__ == "__main__":
    load_dotenv()
    main()