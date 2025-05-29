import azure.functions as func
import json
import logging
import tempfile
import os
from typing import Dict, Any, List
import traceback


from RAGClient import RAGClient
from PDFprocessor import DocumentProcessor

# Initialize the function app
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Global RAG client instance (will be initialized on first use)
_rag_client = None
_document_processor = None

def get_rag_client():
    """Get or create RAG client instance."""
    global _rag_client
    if _rag_client is None:
        _rag_client = RAGClient(
            log_level="INFO",
            enable_notebook_logging=False,  # Disable for Azure Functions
            enable_memory=False,  # Start without memory for stateless functions
            local=False,  # Use Azure Search instead of local Chroma
            verbose=False
        )
    return _rag_client

def get_document_processor():
    """Get or create document processor instance."""
    global _document_processor
    if _document_processor is None:
        rag_client = get_rag_client()
        _document_processor = DocumentProcessor(rag_client)
    return _document_processor

@app.route(route="rag/query", methods=["POST"])
def rag_query(req: func.HttpRequest) -> func.HttpResponse:
    """
    Handle RAG queries.
    
    Expected JSON payload:
    {
        "query": "Your question here",
        "verbose": false (optional)
    }
    """
    logging.info('RAG query function processed a request.')
    
    try:
        # Parse request body
        req_body = req.get_json()
        
        if not req_body:
            return func.HttpResponse(
                json.dumps({"error": "Request body is required"}),
                status_code=400,
                mimetype="application/json"
            )
        
        query = req_body.get('query')
        if not query:
            return func.HttpResponse(
                json.dumps({"error": "Query parameter is required"}),
                status_code=400,
                mimetype="application/json"
            )
        
        verbose = req_body.get('verbose', False)
        
        # Get RAG client and process query
        rag_client = get_rag_client()
        result = rag_client.ask_rag(query, verbose=verbose)
        
        return func.HttpResponse(
            json.dumps(result, ensure_ascii=False),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Error processing RAG query: {str(e)}")
        logging.error(traceback.format_exc())
        
        return func.HttpResponse(
            json.dumps({
                "error": "Internal server error",
                "message": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="rag/upload", methods=["POST"])
def upload_pdf(req: func.HttpRequest) -> func.HttpResponse:
    """
    Handle PDF file uploads for indexing.
    
    Expects multipart/form-data with PDF files.
    """
    logging.info('PDF upload function processed a request.')
    
    try:
        # Check if files were uploaded
        files = req.files
        if not files:
            return func.HttpResponse(
                json.dumps({"error": "No files uploaded"}),
                status_code=400,
                mimetype="application/json"
            )
        
        # Process uploaded files
        temp_files = []
        processed_files = []
        
        try:
            for file_key in files:
                file = files[file_key]
                
                # Validate file type
                if not file.filename.lower().endswith('.pdf'):
                    continue
                
                # Create temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                    temp_file.write(file.read())
                    temp_files.append(temp_file.name)
                    processed_files.append(file.filename)
            
            if not temp_files:
                return func.HttpResponse(
                    json.dumps({"error": "No valid PDF files found"}),
                    status_code=400,
                    mimetype="application/json"
                )
            
            # Process PDFs with document processor
            processor = get_document_processor()
            result = processor.index_pdf_files(temp_files)
            
            # Add original filenames to result
            result["uploaded_files"] = processed_files
            
            return func.HttpResponse(
                json.dumps(result),
                status_code=200,
                mimetype="application/json"
            )
            
        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except:
                    pass
                    
    except Exception as e:
        logging.error(f"Error processing PDF upload: {str(e)}")
        logging.error(traceback.format_exc())
        
        return func.HttpResponse(
            json.dumps({
                "error": "Internal server error",
                "message": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="rag/status", methods=["GET"])
def rag_status(req: func.HttpRequest) -> func.HttpResponse:
    """
    Get RAG system status and database information.
    """
    logging.info('RAG status function processed a request.')
    
    try:
        rag_client = get_rag_client()
        db_info = rag_client.get_database_info()
        
        status = {
            "status": "healthy",
            "database_info": db_info,
            "endpoints": {
                "query": "/api/rag/query (POST)",
                "upload": "/api/rag/upload (POST)",
                "status": "/api/rag/status (GET)",
                "clear": "/api/rag/clear (POST)"
            }
        }
        
        return func.HttpResponse(
            json.dumps(status),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Error getting RAG status: {str(e)}")
        
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "error": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="rag/clear", methods=["POST"])
def clear_database(req: func.HttpRequest) -> func.HttpResponse:
    """
    Clear the vector database.
    
    Expected JSON payload:
    {
        "confirm": true
    }
    """
    logging.info('Clear database function processed a request.')
    
    try:
        req_body = req.get_json()
        
        if not req_body or not req_body.get('confirm'):
            return func.HttpResponse(
                json.dumps({
                    "error": "Confirmation required",
                    "message": "Send {\"confirm\": true} to clear database"
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        rag_client = get_rag_client()
        rag_client.clear_database()
        
        return func.HttpResponse(
            json.dumps({
                "success": True,
                "message": "Database cleared successfully"
            }),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Error clearing database: {str(e)}")
        
        return func.HttpResponse(
            json.dumps({
                "error": "Internal server error",
                "message": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="rag/memory", methods=["POST"])
def toggle_memory(req: func.HttpRequest) -> func.HttpResponse:
    """
    Toggle conversation memory on/off.
    
    Expected JSON payload:
    {
        "enable": true/false
    }
    """
    logging.info('Toggle memory function processed a request.')
    
    try:
        req_body = req.get_json()
        
        if not req_body or 'enable' not in req_body:
            return func.HttpResponse(
                json.dumps({
                    "error": "Enable parameter required",
                    "message": "Send {\"enable\": true/false}"
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        enable = req_body.get('enable')
        rag_client = get_rag_client()
        
        if enable:
            from langchain.memory import ConversationBufferMemory
            rag_client.enable_memory = True
            if not rag_client.memory:
                rag_client.memory = ConversationBufferMemory(
                    memory_key="chat_history",
                    return_messages=True,
                    output_key="answer"
                )
        else:
            rag_client.enable_memory = False
            rag_client.memory = None
        
        return func.HttpResponse(
            json.dumps({
                "success": True,
                "memory_enabled": enable,
                "message": f"Memory {'enabled' if enable else 'disabled'}"
            }),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Error toggling memory: {str(e)}")
        
        return func.HttpResponse(
            json.dumps({
                "error": "Internal server error",
                "message": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )

# Health check endpoint
@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Basic health check endpoint."""
    return func.HttpResponse(
        json.dumps({
            "status": "healthy",
            "service": "RAG Function App"
        }),
        status_code=200,
        mimetype="application/json"
    )