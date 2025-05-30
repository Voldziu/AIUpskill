import streamlit as st
import requests
import json
import uuid
import logging
from typing import Dict, Any
from datetime import datetime
from config import *

# Configure structured logging for Streamlit
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - TraceID: %(trace_id)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('streamlit_app.log')
    ]
)

# Create logger
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout=LAYOUT,
    initial_sidebar_state=INITIAL_SIDEBAR_STATE
)

# Custom CSS with updated colors
st.markdown(f"""
<style>
    .main {{
        padding-top: 1rem;
    }}
    .stAlert {{
        margin-top: 1rem;
    }}
    .chat-message {{
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }}
    .chat-message.user {{
        background-color: #e1f5fe;
        border-left: 4px solid {PRIMARY_COLOR};
    }}
    .chat-message.assistant {{
        background-color: #f3e5f5;
        border-left: 4px solid {SECONDARY_COLOR};
    }}
    .chat-message .message {{
        margin-bottom: 0.5rem;
        font-size: 1rem;
    }}
    .chat-message .sources {{
        font-size: 0.85rem;
        color: #666;
        margin-top: 0.5rem;
    }}
    .upload-section {{
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }}
    .trace-info {{
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 0.25rem;
        padding: 0.5rem;
        margin: 0.5rem 0;
        font-size: 0.8rem;
        color: #856404;
    }}
    .error-section {{
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 0.5rem;
        padding: 1rem;
        margin-bottom: 1rem;
    }}
</style>
""", unsafe_allow_html=True)

def generate_trace_id() -> str:
    """Generate a unique trace ID for request correlation."""
    return str(uuid.uuid4())

def get_correlation_headers(trace_id: str = None) -> Dict[str, str]:
    """Generate correlation headers for API requests."""
    if not trace_id:
        trace_id = generate_trace_id()
    
    return {
        'X-Trace-ID': trace_id,
        'X-Parent-Span-ID': str(uuid.uuid4())[:8],
        'User-Agent': 'Streamlit-RAG-Frontend/1.0'
    }

def log_structured(level: str, message: str, trace_id: str = None, **kwargs):
    """Log with structured format for correlation."""
    extra_data = {
        'trace_id': trace_id or 'no-trace',
        'timestamp': datetime.utcnow().isoformat(),
        **kwargs
    }
    
    # Create custom LogRecord with trace_id
    class TraceAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            return msg, {**kwargs, 'extra': {'trace_id': extra_data['trace_id']}}
    
    trace_logger = TraceAdapter(logger, extra_data)
    
    log_message = f"{message} | {json.dumps(extra_data)}"
    
    if level.upper() == 'INFO':
        trace_logger.info(log_message)
    elif level.upper() == 'ERROR':
        trace_logger.error(log_message)
    elif level.upper() == 'WARNING':
        trace_logger.warning(log_message)
    elif level.upper() == 'DEBUG':
        trace_logger.debug(log_message)

def check_backend_health() -> tuple[bool, str]:
    """Check if the backend is healthy."""
    trace_id = generate_trace_id()
    headers = get_correlation_headers(trace_id)
    
    log_structured('INFO', 'Checking backend health', trace_id=trace_id, 
                  operation='health_check')
    
    try:
        response = requests.get(
            f"{AZURE_FUNCTION_BASE_URL}/health", 
            headers=headers,
            timeout=HEALTH_CHECK_TIMEOUT
        )
        
        if response.status_code == 200:
            log_structured('INFO', 'Backend health check successful', trace_id=trace_id,
                          status_code=response.status_code)
            return True, trace_id
        else:
            log_structured('ERROR', 'Backend health check failed', trace_id=trace_id,
                          status_code=response.status_code)
            return False, trace_id
            
    except Exception as e:
        log_structured('ERROR', f'Backend health check exception: {str(e)}', trace_id=trace_id,
                      error_type=type(e).__name__)
        return False, trace_id

def get_rag_status() -> tuple[Dict[str, Any], str]:
    """Get RAG system status."""
    trace_id = generate_trace_id()
    headers = get_correlation_headers(trace_id)
    
    log_structured('INFO', 'Getting RAG status', trace_id=trace_id,
                  operation='rag_status')
    
    try:
        response = requests.get(
            f"{AZURE_FUNCTION_BASE_URL}/rag/status", 
            headers=headers,
            timeout=HEALTH_CHECK_TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            log_structured('INFO', 'RAG status retrieved successfully', trace_id=trace_id,
                          backend_trace_id=result.get('trace_id'))
            return result, trace_id
        else:
            log_structured('ERROR', 'Failed to get RAG status', trace_id=trace_id,
                          status_code=response.status_code)
            return {"status": "error", "error": f"HTTP {response.status_code}"}, trace_id
            
    except Exception as e:
        log_structured('ERROR', f'RAG status exception: {str(e)}', trace_id=trace_id,
                      error_type=type(e).__name__)
        return {"status": "error", "error": str(e)}, trace_id

def query_rag(question: str, verbose: bool = False) -> tuple[Dict[str, Any], str]:
    """Send a question to the RAG system."""
    trace_id = generate_trace_id()
    headers = get_correlation_headers(trace_id)
    
    log_structured('INFO', f'Sending RAG query: {question[:50]}...', trace_id=trace_id,
                  operation='rag_query', question_length=len(question), verbose=verbose)
    
    try:
        payload = {
            "query": question,
            "verbose": verbose
        }
        response = requests.post(
            f"{AZURE_FUNCTION_BASE_URL}/rag/query",
            json=payload,
            headers=headers,
            timeout=RAG_QUERY_TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            log_structured('INFO', 'RAG query successful', trace_id=trace_id,
                          backend_trace_id=result.get('trace_id'),
                          sources_count=result.get('num_sources', 0))
            return result, trace_id
        else:
            log_structured('ERROR', 'RAG query failed', trace_id=trace_id,
                          status_code=response.status_code, response_text=response.text[:200])
            return {
                "error": f"Request failed with status {response.status_code}",
                "message": response.text
            }, trace_id
            
    except Exception as e:
        log_structured('ERROR', f'RAG query exception: {str(e)}', trace_id=trace_id,
                      error_type=type(e).__name__)
        return {"error": "Connection failed", "message": str(e)}, trace_id

def upload_pdf(uploaded_file) -> tuple[Dict[str, Any], str]:
    """Upload a PDF file to the RAG system."""
    trace_id = generate_trace_id()
    headers = get_correlation_headers(trace_id)
    
    log_structured('INFO', f'Uploading PDF: {uploaded_file.name}', trace_id=trace_id,
                  operation='pdf_upload', filename=uploaded_file.name, file_size=len(uploaded_file.getvalue()))
    
    try:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
        response = requests.post(
            f"{AZURE_FUNCTION_BASE_URL}/rag/upload",
            files=files,
            headers=headers,
            timeout=UPLOAD_TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            log_structured('INFO', 'PDF upload successful', trace_id=trace_id,
                          backend_trace_id=result.get('trace_id'),
                          chunks_created=result.get('chunks_created', 0))
            return result, trace_id
        else:
            log_structured('ERROR', 'PDF upload failed', trace_id=trace_id,
                          status_code=response.status_code, response_text=response.text[:200])
            return {
                "error": f"Upload failed with status {response.status_code}",
                "message": response.text
            }, trace_id
            
    except Exception as e:
        log_structured('ERROR', f'PDF upload exception: {str(e)}', trace_id=trace_id,
                      error_type=type(e).__name__)
        return {"error": "Upload failed", "message": str(e)}, trace_id

def clear_database() -> tuple[Dict[str, Any], str]:
    """Clear the RAG database."""
    trace_id = generate_trace_id()
    headers = get_correlation_headers(trace_id)
    
    log_structured('WARNING', 'Clearing database', trace_id=trace_id,
                  operation='clear_database')
    
    try:
        payload = {"confirm": True}
        response = requests.post(
            f"{AZURE_FUNCTION_BASE_URL}/rag/clear",
            json=payload,
            headers=headers,
            timeout=CLEAR_DB_TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            log_structured('WARNING', 'Database cleared successfully', trace_id=trace_id,
                          backend_trace_id=result.get('trace_id'))
            return result, trace_id
        else:
            log_structured('ERROR', 'Database clear failed', trace_id=trace_id,
                          status_code=response.status_code, response_text=response.text[:200])
            return {
                "error": f"Clear failed with status {response.status_code}",
                "message": response.text
            }, trace_id
            
    except Exception as e:
        log_structured('ERROR', f'Database clear exception: {str(e)}', trace_id=trace_id,
                      error_type=type(e).__name__)
        return {"error": "Clear failed", "message": str(e)}, trace_id

def test_error_endpoint(error_type: str = "generic") -> tuple[Dict[str, Any], str]:
    """Test the error endpoint for monitoring."""
    trace_id = generate_trace_id()
    headers = get_correlation_headers(trace_id)
    
    log_structured('INFO', f'Testing error endpoint: {error_type}', trace_id=trace_id,
                  operation='test_error', error_type=error_type, intentional=True)
    
    try:
        payload = {"error_type": error_type}
        response = requests.post(
            f"{AZURE_FUNCTION_BASE_URL}/rag/raise_error",
            json=payload,
            headers=headers,
            timeout=RAG_QUERY_TIMEOUT
        )
        
        result = response.json()
        
        if response.status_code == 500 and result.get('intentional'):
            log_structured('INFO', 'Test error executed successfully', trace_id=trace_id,
                          backend_trace_id=result.get('trace_id'), 
                          error_type=result.get('error_type'), intentional=True)
            return result, trace_id
        else:
            log_structured('ERROR', 'Unexpected response from error endpoint', trace_id=trace_id,
                          status_code=response.status_code)
            return {
                "error": f"Unexpected response: {response.status_code}",
                "message": response.text
            }, trace_id
            
    except Exception as e:
        log_structured('ERROR', f'Error endpoint test exception: {str(e)}', trace_id=trace_id,
                      error_type=type(e).__name__)
        return {"error": "Test failed", "message": str(e)}, trace_id

def display_trace_info(trace_id: str, backend_trace_id: str = None):
    """Display trace information for debugging."""
    st.markdown(f"""
    <div class="trace-info">
        <strong>🔍 Trace Information:</strong><br>
        Frontend Trace ID: <code>{trace_id}</code><br>
        {f'Backend Trace ID: <code>{backend_trace_id}</code><br>' if backend_trace_id else ''}
        Timestamp: <code>{datetime.utcnow().isoformat()}Z</code>
    </div>
    """, unsafe_allow_html=True)

def display_chat_message(role: str, content: str, sources: list = None, trace_id: str = None):
    """Display a chat message with styling and trace info."""
    with st.container():
        st.markdown(f"""
        <div class="chat-message {role}">
            <div class="message">
                <strong>{"You" if role == "user" else "Assistant"}:</strong> {content}
            </div>
        """, unsafe_allow_html=True)
        
        if sources and role == "assistant":
            st.markdown(f"""
            <div class="sources">
                <strong>Sources:</strong><br>
                {', '.join([f"{source.get('title', 'Unknown')} (Page: {source.get('page', 'N/A')})" for source in sources])}
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "backend_status" not in st.session_state:
    st.session_state.backend_status = None

if "last_trace_id" not in st.session_state:
    st.session_state.last_trace_id = None

# Header
st.title(f"{APP_ICON} {APP_TITLE}")
st.markdown("Ask questions about your uploaded documents!")

# Sidebar
with st.sidebar:
    st.header("📊 System Status")
    
    # Check backend status
    if st.button("🔄 Refresh Status", use_container_width=True):
        with st.spinner(MESSAGES["checking"]):
            status, trace_id = get_rag_status()
            st.session_state.backend_status = status
            st.session_state.last_trace_id = trace_id
    
    # Display status
    if st.session_state.backend_status:
        status = st.session_state.backend_status
        if status.get("status") == "healthy":
            st.success(MESSAGES["backend_healthy"])
            if "database_info" in status:
                st.info(f"📚 Database: {status['database_info'].get('collection_name', 'N/A')}")
        else:
            st.error(f"{MESSAGES['backend_error']}: {status.get('error', 'Unknown')}")
        
        # Show trace info if available
        if st.session_state.last_trace_id:
            display_trace_info(st.session_state.last_trace_id, status.get('trace_id'))
    
    st.divider()
    
    # Error Testing Section
    st.header("🚨 Error Testing")
    st.markdown('<div class="error-section">', unsafe_allow_html=True)
    st.markdown("**Test monitoring system:**")
    
    error_types = {
        "Generic Error": "generic",
        "Division by Zero": "division_by_zero", 
        "Key Error": "key_error",
        "Type Error": "type_error"
    }
    
    selected_error = st.selectbox("Select error type:", list(error_types.keys()))
    
    if st.button("🔥 Trigger Test Error", use_container_width=True, type="secondary"):
        with st.spinner("Triggering test error..."):
            result, trace_id = test_error_endpoint(error_types[selected_error])
            
            if "error" in result and result.get("intentional"):
                st.success(f"✅ Test error triggered successfully!")
                st.info(f"Error Type: {result.get('error_type', 'Unknown')}")
                display_trace_info(trace_id, result.get('trace_id'))
                st.markdown(f"**Check Application Insights for trace:** `{result.get('trace_id')}`")
            else:
                st.error(f"❌ Test failed: {result.get('error', 'Unknown')}")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    
    # Document upload section
    st.header("📄 Upload Documents")
    st.markdown('<div class="upload-section">', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=ALLOWED_FILE_TYPES,
        help=UPLOAD_HELP_TEXT
    )
    
    if uploaded_file is not None:
        st.info(f"📎 Selected: {uploaded_file.name}")
        
        if st.button("📤 Upload PDF", use_container_width=True, type="primary"):
            with st.spinner(f"{MESSAGES['uploading']} {uploaded_file.name}..."):
                result, trace_id = upload_pdf(uploaded_file)
                
                if "error" in result:
                    st.error(f"{MESSAGES['upload_failed']}: {result['error']}")
                    if "message" in result:
                        st.error(result["message"])
                else:
                    st.success(f"{MESSAGES['upload_success']} {uploaded_file.name}!")
                    if "chunks_created" in result:
                        st.success(f"📚 Created {result['chunks_created']} document chunks")
                
                # Show trace information
                display_trace_info(trace_id, result.get('trace_id'))
                
                # Refresh status after upload
                status, _ = get_rag_status()
                st.session_state.backend_status = status
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    
    # Database management
    st.header("🗃️ Database Management")

    # Initialize session state for clear confirmation
    if "show_clear_confirm" not in st.session_state:
        st.session_state.show_clear_confirm = False

    if not st.session_state.show_clear_confirm:
        # Show initial clear button
        if st.button("🗑️ Clear Database", use_container_width=True, type="secondary"):
            st.session_state.show_clear_confirm = True
            st.rerun()
    else:
        # Show confirmation buttons
        st.warning("⚠️ Are you sure you want to clear all documents?")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✅ Confirm Clear", use_container_width=True, type="primary"):
                with st.spinner(MESSAGES["clearing"]):
                    log_structured('WARNING', 'Clearing database initiated',
                                operation='clear_database', trace_id=generate_trace_id())
                    result, trace_id = clear_database()
                    
                    if "error" in result:
                        st.error(f"{MESSAGES['clear_failed']}: {result['error']}")
                    else:
                        st.success(MESSAGES["clear_success"])
                        st.session_state.messages = []  # Clear chat history
                    
                    # Show trace information
                    display_trace_info(trace_id, result.get('trace_id'))
                    
                    status, _ = get_rag_status()
                    st.session_state.backend_status = status
                    
                # Reset confirmation state
                st.session_state.show_clear_confirm = False
                st.rerun()
        
        with col2:
            if st.button("❌ Cancel", use_container_width=True, type="secondary"):
                st.session_state.show_clear_confirm = False
                st.rerun()
    
    st.divider()
    
    # Settings
    st.header("⚙️ Settings")
    verbose_mode = st.checkbox("🔍 Verbose mode", value=DEFAULT_VERBOSE_MODE, 
                              help="Show detailed processing information")
    show_traces = st.checkbox("🔍 Show trace IDs", value=True,
                             help="Display trace information for debugging")
    
    if st.button("💬 Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# Main chat interface
st.header("💬 Chat")

# Display chat messages
for message in st.session_state.messages:
    display_chat_message(
        message["role"], 
        message["content"], 
        message.get("sources"),
        message.get("trace_id")
    )

# Chat input
question = st.chat_input(CHAT_INPUT_PLACEHOLDER)

if question:
    # Add user message to chat
    user_trace_id = generate_trace_id()
    st.session_state.messages.append({
        "role": "user", 
        "content": question,
        "trace_id": user_trace_id
    })
    display_chat_message("user", question, trace_id=user_trace_id)
    
    # Get response from RAG
    with st.spinner(MESSAGES["thinking"]):
        response, trace_id = query_rag(question, verbose=verbose_mode)
    
    if "error" in response:
        error_msg = f"❌ Error: {response['error']}"
        if "message" in response:
            error_msg += f"\n\nDetails: {response['message']}"
        
        st.session_state.messages.append({
            "role": "assistant", 
            "content": error_msg,
            "trace_id": trace_id
        })
        display_chat_message("assistant", error_msg, trace_id=trace_id)
        
        # Show trace info for errors
        if show_traces:
            display_trace_info(trace_id, response.get('trace_id'))
    else:
        answer = response.get("answer", "No answer received")
        sources = response.get("sources", [])
        
        # Add assistant message to chat
        st.session_state.messages.append({
            "role": "assistant", 
            "content": answer,
            "sources": sources,
            "trace_id": trace_id
        })
        display_chat_message("assistant", answer, sources, trace_id=trace_id)
        
        # Show trace info
        if show_traces:
            display_trace_info(trace_id, response.get('trace_id'))
        
        # Show additional info in expander
        if verbose_mode:
            with st.expander("🔍 Detailed Information"):
                st.json({
                    "frontend_trace_id": trace_id,
                    "backend_trace_id": response.get("trace_id"),
                    "query": response.get("query"),
                    "context_used": response.get("context_used"),
                    "num_sources": response.get("num_sources"),
                    "sources": sources
                })

# Footer
st.divider()
st.markdown(f"""
<div style="text-align: center; color: #666; font-size: 0.8rem;">
    {APP_ICON} {APP_TITLE} powered by Azure Functions and Streamlit<br>
    <strong>Application Insights Integration Active</strong>
</div>
""", unsafe_allow_html=True)