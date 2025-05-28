import azure.functions as func
import json
import logging
import os
import sys

# Add parent directory to import RAG client
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.RAG.LangChain.ChromaRAGClient import ChromaRAGClient

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

_rag_client = None

def get_rag_client():
    global _rag_client
    if _rag_client is None:
        _rag_client = ChromaRAGClient(
            log_level="INFO",
            enable_notebook_logging=False,
            enable_memory=True
        )
    return _rag_client

@app.route(route="ask_rag", methods=["POST"])
def ask_rag(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        if not req_body or not req_body.get('query'):
            return func.HttpResponse(
                json.dumps({"success": False, "error": "Missing query"}),
                status_code=400,
                headers={"Content-Type": "application/json"}
            )
        
        query = req_body.get('query')
        top_k = req_body.get('top_k', 3)
        verbose = req_body.get('verbose', False)
        
        rag_client = get_rag_client()
        rag_client.retriever.search_kwargs = {"k": top_k}

        result = rag_client.ask_rag(query, verbose=verbose)
        
        response = {
            "success": True,
            "query": result["query"],
            "answer": result["answer"],
            "sources": result["sources"],
            "context_used": result["context_used"],
            "num_sources": result["num_sources"]
        }
        
        return func.HttpResponse(
            json.dumps(response, ensure_ascii=False),
            status_code=200,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"success": False, "error": str(e)}),
            status_code=500,
            headers={"Content-Type": "application/json"}
        )

@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    try:
        rag_client = get_rag_client()
        db_info = rag_client.get_database_info()
        return func.HttpResponse(
            json.dumps({
                "status": "healthy",
                "database_documents": db_info.get("total_documents", 0)
            }),
            headers={"Content-Type": "application/json"}
        )
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"status": "unhealthy", "error": str(e)}),
            status_code=503,
            headers={"Content-Type": "application/json"}
        )