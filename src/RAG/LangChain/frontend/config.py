# config.py
"""Configuration file for the Streamlit RAG Frontend"""

# Azure Function App Configuration
AZURE_FUNCTION_BASE_URL = "http://localhost:7075/api"

# Streamlit Page Configuration
APP_TITLE = "RAG Chat Assistant"
APP_ICON = "🤖"
LAYOUT = "wide"
INITIAL_SIDEBAR_STATE = "expanded"

# File Upload Configuration
MAX_FILE_SIZE_MB = 10
ALLOWED_FILE_TYPES = ["pdf"]
UPLOAD_HELP_TEXT = "Upload PDF documents to add to the knowledge base"

# Chat Configuration
MAX_CHAT_HISTORY = 50
DEFAULT_VERBOSE_MODE = False
CHAT_INPUT_PLACEHOLDER = "Ask a question about your documents..."

# API Timeouts (seconds)
HEALTH_CHECK_TIMEOUT = 10
RAG_QUERY_TIMEOUT = 60
UPLOAD_TIMEOUT = 60
CLEAR_DB_TIMEOUT = 30

# UI Text Configuration
MESSAGES = {
    "backend_healthy": "✅ Backend is healthy",
    "backend_error": "❌ Backend error",
    "upload_success": "✅ Successfully uploaded",
    "upload_failed": "❌ Upload failed",
    "clear_success": "✅ Database cleared successfully!",
    "clear_failed": "❌ Clear failed",
    "thinking": "🤔 Thinking...",
    "uploading": "📤 Uploading",
    "clearing": "🗑️ Clearing database...",
    "checking": "🔄 Checking backend..."
}

# Styling
PRIMARY_COLOR = "#0277bd"
SECONDARY_COLOR = "#7b1fa2"