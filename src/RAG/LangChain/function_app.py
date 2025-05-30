import azure.functions as func
import json
import logging
import tempfile
import os
import uuid
import traceback
from typing import Dict, Any, List
from datetime import datetime

from RAGClient import RAGClient
from PDFprocessor import DocumentProcessor


app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



# Global RAG client instance
_rag_client = None
_document_processor = None

def get_correlation_context(req: func.HttpRequest) -> Dict[str, str]:
    """Extract or generate correlation context for tracing."""
    trace_id = req.headers.get('X-Trace-ID', str(uuid.uuid4()))
    parent_span_id = req.headers.get('X-Parent-Span-ID', None)
    user_agent = req.headers.get('User-Agent', 'Unknown')
    
    return {
        'trace_id': trace_id,
        'parent_span_id': parent_span_id,
        'user_agent': user_agent,
        'timestamp': datetime.utcnow().isoformat()
    }


def log_structured(level: str, message: str, correlation_context: Dict[str, str], **kwargs):
    """Log with structured format for Azure Application Insights."""
    # Create structured log data that Azure Application Insights will capture
    log_data = {
        'message': message,
        'trace_id': correlation_context.get('trace_id'),
        'parent_span_id': correlation_context.get('parent_span_id'),
        'user_agent': correlation_context.get('user_agent'),
        'timestamp': correlation_context.get('timestamp'),
        **kwargs
    }
    
    # Azure Functions automatically captures custom properties when logging
    # Format message with structured data for Application Insights
    structured_message = f"{message} | TraceId: {log_data['trace_id']} | Data: {json.dumps(kwargs)}"
    
    if level.upper() == 'INFO':
        logger.info(structured_message, extra={'custom_dimensions': log_data})
    elif level.upper() == 'ERROR':
        logger.error(structured_message, extra={'custom_dimensions': log_data})
    elif level.upper() == 'WARNING':
        logger.warning(structured_message, extra={'custom_dimensions': log_data})
    elif level.upper() == 'DEBUG':
        logger.debug(structured_message, extra={'custom_dimensions': log_data})

def get_rag_client():
    """Get or create RAG client instance."""
    global _rag_client
    if _rag_client is None:
        _rag_client = RAGClient(
            log_level="INFO",
            enable_notebook_logging=False,
            enable_memory=False,
            local=False,
            verbose=True
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
    """Handle RAG queries with Azure Application Insights logging."""
    correlation_context = get_correlation_context(req)
    start_time = datetime.utcnow()
    
    log_structured('INFO', 'RAG query function started', correlation_context, 
                  operation='rag_query')
    
    try:
        # Parse request body
        req_body = req.get_json()
        
        if not req_body:
            log_structured('ERROR', 'Request body is missing', correlation_context,
                          operation='rag_query', error_type='validation_error')
            return func.HttpResponse(
                json.dumps({"error": "Request body is required", "trace_id": correlation_context['trace_id']}),
                status_code=400,
                mimetype="application/json"
            )
        
        query = req_body.get('query')
        if not query:
            log_structured('ERROR', 'Query parameter is missing', correlation_context,
                          operation='rag_query', error_type='validation_error')
            return func.HttpResponse(
                json.dumps({"error": "Query parameter is required", "trace_id": correlation_context['trace_id']}),
                status_code=400,
                mimetype="application/json"
            )
        
        verbose = req_body.get('verbose', False)
        
        log_structured('INFO', f'Processing RAG query: {query[:100]}...', correlation_context,
                      operation='rag_query', query_length=len(query), verbose=verbose)
        
        # Get RAG client and process query
        rag_client = get_rag_client()
        result = rag_client.ask_rag(query, verbose=verbose)
        
        # Add trace ID to response
        result['trace_id'] = correlation_context['trace_id']
        
        # Calculate response time
        response_time = (datetime.utcnow() - start_time).total_seconds()
        
        log_structured('INFO', 'RAG query completed successfully', correlation_context,
                      operation='rag_query', sources_count=result.get('num_sources', 0),
                      context_used=result.get('context_used', False), 
                      response_time_seconds=response_time)
        
        return func.HttpResponse(
            json.dumps(result, ensure_ascii=False),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        error_message = str(e)
        stack_trace = traceback.format_exc()
        response_time = (datetime.utcnow() - start_time).total_seconds()
        
        log_structured('ERROR', f'RAG query failed: {error_message}', correlation_context,
                      operation='rag_query', error_type='runtime_error', 
                      stack_trace=stack_trace, response_time_seconds=response_time)
        
        # Azure Application Insights will automatically capture this exception
        logger.exception("RAG query exception", extra={
            'custom_dimensions': {
                'trace_id': correlation_context['trace_id'],
                'operation': 'rag_query',
                'error_message': error_message,
                'error_type': type(e).__name__
            }
        })
        
        return func.HttpResponse(
            json.dumps({
                "error": "Internal server error",
                "message": error_message,
                "trace_id": correlation_context['trace_id']
            }),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="rag/upload", methods=["POST"])
def upload_pdf(req: func.HttpRequest) -> func.HttpResponse:
    """Handle PDF file uploads with tracing."""
    correlation_context = get_correlation_context(req)
    
    log_structured('INFO', 'PDF upload function started', correlation_context,
                  operation='pdf_upload')
    
    try:
        # Check if files were uploaded
        files = req.files
        if not files:
            log_structured('ERROR', 'No files uploaded', correlation_context,
                          operation='pdf_upload', error_type='validation_error')
            return func.HttpResponse(
                json.dumps({"error": "No files uploaded", "trace_id": correlation_context['trace_id']}),
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
                log_structured('ERROR', 'No valid PDF files found', correlation_context,
                              operation='pdf_upload', error_type='validation_error')
                return func.HttpResponse(
                    json.dumps({"error": "No valid PDF files found", "trace_id": correlation_context['trace_id']}),
                    status_code=400,
                    mimetype="application/json"
                )
            
            log_structured('INFO', f'Processing {len(temp_files)} PDF files', correlation_context,
                          operation='pdf_upload', file_count=len(temp_files),
                          files=processed_files)
            
            # Process PDFs with document processor
            processor = get_document_processor()
            result = processor.index_pdf_files(temp_files)
            
            # Add original filenames and trace ID to result
            result["uploaded_files"] = processed_files
            result["trace_id"] = correlation_context['trace_id']
            
            log_structured('INFO', 'PDF upload completed successfully', correlation_context,
                          operation='pdf_upload', chunks_created=result.get('chunks_created', 0))
            
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
        error_message = str(e)
        stack_trace = traceback.format_exc()
        
        log_structured('ERROR', f'PDF upload failed: {error_message}', correlation_context,
                      operation='pdf_upload', error_type='runtime_error',
                      stack_trace=stack_trace)
        
        logger.exception("PDF upload exception", extra={
            'custom_dimensions': {
                'trace_id': correlation_context['trace_id'],
                'operation': 'pdf_upload',
                'error_message': error_message
            }
        })
        
        return func.HttpResponse(
            json.dumps({
                "error": "Internal server error",
                "message": error_message,
                "trace_id": correlation_context['trace_id']
            }),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="rag/raise_error", methods=["POST"])
def raise_error(req: func.HttpRequest) -> func.HttpResponse:
    """Intentionally raise an error for testing Azure Application Insights monitoring."""
    correlation_context = get_correlation_context(req)
    
    log_structured('INFO', 'raise_error function called for testing', correlation_context,
                  operation='raise_error', purpose='testing')
    
    try:
        req_body = req.get_json()
        error_type = req_body.get('error_type', 'generic') if req_body else 'generic'
        
        log_structured('WARNING', f'About to raise {error_type} error for testing', correlation_context,
                      operation='raise_error', error_type=error_type)
        
        if error_type == 'division_by_zero':
            result = 1 / 0  # This will raise ZeroDivisionError
        elif error_type == 'key_error':
            test_dict = {}
            value = test_dict['nonexistent_key']  # This will raise KeyError
        elif error_type == 'type_error':
            result = "string" + 42  # This will raise TypeError
        else:
            raise ValueError(f"Test error raised intentionally with trace_id: {correlation_context['trace_id']}")
            
    except Exception as e:
        error_message = str(e)
        stack_trace = traceback.format_exc()
        
        # Log the error with structured logging for Application Insights
        log_structured('ERROR', f'Intentional test error: {error_message}', correlation_context,
                      operation='raise_error', error_type=type(e).__name__,
                      stack_trace=stack_trace, intentional=True)
        
        # Azure Application Insights will automatically capture this exception
        logger.exception("Intentional test exception for monitoring", extra={
            'custom_dimensions': {
                'trace_id': correlation_context['trace_id'],
                'operation': 'raise_error',
                'error_message': error_message,
                'error_type': type(e).__name__,
                'intentional': True
            }
        })
        
        return func.HttpResponse(
            json.dumps({
                "error": "Test error raised successfully",
                "message": error_message,
                "error_type": type(e).__name__,
                "trace_id": correlation_context['trace_id'],
                "intentional": True
            }),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="rag/status", methods=["GET"])
def rag_status(req: func.HttpRequest) -> func.HttpResponse:
    """Get RAG system status with tracing."""
    correlation_context = get_correlation_context(req)
    
    log_structured('INFO', 'RAG status function called', correlation_context,
                  operation='rag_status')
    
    try:
        rag_client = get_rag_client()
        db_info = rag_client.get_database_info()
        
        status = {
            "status": "healthy",
            "database_info": db_info,
            "trace_id": correlation_context['trace_id'],
            "endpoints": {
                "query": "/api/rag/query (POST)",
                "upload": "/api/rag/upload (POST)",
                "status": "/api/rag/status (GET)",
                "clear": "/api/rag/clear (POST)",
                "raise_error": "/api/rag/raise_error (POST)"
            }
        }
        
        log_structured('INFO', 'RAG status retrieved successfully', correlation_context,
                      operation='rag_status', database_status='healthy')
        
        return func.HttpResponse(
            json.dumps(status),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        error_message = str(e)
        log_structured('ERROR', f'RAG status check failed: {error_message}', correlation_context,
                      operation='rag_status', error_type='runtime_error')
        
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "error": error_message,
                "trace_id": correlation_context['trace_id']
            }),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="rag/clear", methods=["POST"])
def clear_database(req: func.HttpRequest) -> func.HttpResponse:
    """Clear the vector database with tracing."""
    correlation_context = get_correlation_context(req)
    
    log_structured('INFO', 'Clear database function called', correlation_context,
                  operation='clear_database')
    
    try:
        req_body = req.get_json()
        
        if not req_body or not req_body.get('confirm'):
            log_structured('WARNING', 'Database clear attempted without confirmation', correlation_context,
                          operation='clear_database', error_type='validation_error')
            return func.HttpResponse(
                json.dumps({
                    "error": "Confirmation required",
                    "message": "Send {\"confirm\": true} to clear database",
                    "trace_id": correlation_context['trace_id']
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        rag_client = get_rag_client()
        rag_client.clear_database()
        
        log_structured('WARNING', 'Database cleared successfully', correlation_context,
                      operation='clear_database', action='database_cleared')
        
        return func.HttpResponse(
            json.dumps({
                "success": True,
                "message": "Database cleared successfully",
                "trace_id": correlation_context['trace_id']
            }),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        error_message = str(e)
        log_structured('ERROR', f'Database clear failed: {error_message}', correlation_context,
                      operation='clear_database', error_type='runtime_error')
        
        return func.HttpResponse(
            json.dumps({
                "error": "Internal server error",
                "message": error_message,
                "trace_id": correlation_context['trace_id']
            }),
            status_code=500,
            mimetype="application/json"
        )

# Health check endpoint
@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Basic health check endpoint with tracing."""
    correlation_context = get_correlation_context(req)
    
    log_structured('INFO', 'Health check called', correlation_context,
                  operation='health_check')
    
    return func.HttpResponse(
        json.dumps({
            "status": "healthy",
            "service": "RAG Function App",
            "trace_id": correlation_context['trace_id']
        }),
        status_code=200,
        mimetype="application/json"
    )