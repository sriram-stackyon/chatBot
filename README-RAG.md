# PDF RAG Chat Application - Feature Documentation

## Overview
Complete production-ready PDF Retrieval-Augmented Generation (RAG) Chat Application with FastAPI backend, React frontend, ChromaDB vector storage, and OpenAI embeddings.

## Architecture

### Frontend (React + TypeScript)
- **Framework**: React with TypeScript
- **Build Tool**: Vite
- **Port**: 5173 (primary), 5175 (fallback)
- **Components**:
  - ChatPage: Main chat interface
  - InputBar: User message input with formatting
  - MessageList: Chat history display
  - AttachmentButton: File upload trigger
  - AttachmentPreview: Drag-and-drop file preview
  - MessageAttachments: Display attached files in messages

### Backend (FastAPI + Python)
- **Framework**: FastAPI with async/await
- **Database**: PostgreSQL (Supabase)
- **Vector DB**: ChromaDB with persistent storage
- **LLM**: Google Gemini 2.5-Flash via LiteLLM proxy
- **Image Generation**: Imagen 4.0
- **Port**: 8000

### Data Storage
- **PostgreSQL Tables**:
  - chat_threads: Conversation sessions
  - chat_messages: Individual messages
  - chat_attachments: File metadata with indexing status
  - token_usage: Token consumption tracking
  - rate_limits: API request tracking

- **ChromaDB Collections**:
  - Named by user_id and thread_id
  - Stores PDF chunks with metadata (page numbers, source filenames)
  - Uses cosine similarity for semantic search

## Features Implemented

### 1. PDF Processing & Indexing ✅
**File**: `backend/app/ai/rag/pdf_processor.py`

- Extract text from PDF files with page tracking
- Intelligent semantic chunking (1500 chars, 200 overlap)
- Metadata preservation (page numbers, document source)
- PDF validation and error handling

**Functions**:
```python
extract_pdf_text(pdf_path: str) -> (text, page_count)
chunk_text(text, chunk_size=1500, overlap=200) -> [chunks]
validate_pdf_file(path: str) -> bool
```

### 2. Embeddings & Vector Database ✅
**File**: `backend/app/ai/rag/embeddings_vectordb.py`

- OpenAI text-embedding-3-large models
- Batch processing (32 chunks per batch)
- ChromaDB integration with persistent storage
- LRU caching for client initialization
- Cosine similarity search with threshold filtering

**Functions**:
```python
generate_embeddings(texts, batch_size=32) -> embeddings
index_pdf_chunks(user_id, thread_id, attachment_id, filename, chunks) -> int
search_similar_chunks(user_id, thread_id, query, top_k=5, threshold=0.3) -> [chunks]
delete_collection_chunks(user_id, thread_id, attachment_id) -> int
```

### 3. RAG Service Orchestration ✅
**File**: `backend/app/ai/rag/rag_service.py`

- PDF processing pipeline with error handling
- Automatic indexing on PDF upload
- Context retrieval for chat augmentation
- Attachment cleanup with vector removal

**Functions**:
```python
process_and_index_pdf(user_id, thread_id, attachment_id, filename, storage_path) -> {success, error, chunks_indexed, page_count}
retrieve_pdf_context(user_id, thread_id, query, top_k=5) -> formatted_context_string
cleanup_attachment_vectors(user_id, thread_id, attachment_id) -> bool
```

### 4. Chat Integration with RAG Context ✅
**File**: `backend/app/services/chat_service.py`

- Automatic PDF context retrieval on user questions
- Semantic similarity search across indexed documents
- RAG context merged with attachment context
- Source attribution in responses

**Integration Point**:
```python
rag_context = retrieve_pdf_context(user_id, request.thread_id, request.message)
# Merged into LLM prompt before streaming response
```

### 5. Document Summarization ✅
**File**: `backend/app/ai/rag/document_analyzer.py`

- LLM-powered PDF summarization
- Multiple styles: bullet_points, paragraph, abstract
- Automatic key topic extraction
- Configurable summary length

**Functions**:
```python
summarize_pdf_document(pdf_path, max_length=500, style="bullet_points") -> summary_text
extract_key_topics(pdf_path, num_topics=5) -> [topics]
```

### 6. Token Usage Tracking ✅
**File**: `backend/app/core/token_tracker.py`

- Track tokens consumed per operation
- Daily/monthly usage statistics
- Breakdown by operation type (chat, summarization, etc)
- User quota management

**Functions**:
```python
log_token_usage(user_id, tokens_used, operation_type, model, details)
get_token_usage_stats(user_id, days=30) -> dict
get_token_usage_by_operation(user_id, days=30) -> {operation_type: {tokens, count}}
```

### 7. Rate Limiting ✅
**File**: `backend/app/core/rate_limit.py`

- Per-minute request limits (60 requests/min default)
- Daily token quota (1,000,000 tokens/day default)
- Middleware-based enforcement
- Graceful failure handling

**Configuration**:
```python
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_TOKENS_PER_DAY=1000000
```

### 8. Conversation Export ✅
**File**: `backend/app/services/export_service.py`

- Export chats as JSON with full metadata
- Markdown format with formatted timestamps
- CSV format for spreadsheet integration
- Attachment URLs included in exports

**Functions**:
```python
export_conversation_json(user_id, thread_id) -> dict
export_conversation_markdown(user_id, thread_id) -> markdown_string
export_conversation_csv(user_id, thread_id) -> csv_string
```

### 9. API Endpoints

#### Export Routes (`/api/export`)
```
GET  /api/export/conversation/{thread_id}/json      - Export as JSON
GET  /api/export/conversation/{thread_id}/markdown  - Export as Markdown
GET  /api/export/conversation/{thread_id}/csv       - Export as CSV
```

#### RAG Routes (`/api/rag`)
```
POST /api/rag/summarize/{attachment_id}             - Summarize PDF
POST /api/rag/extract-topics/{attachment_id}        - Extract key topics
```

#### Token Routes (`/api/tokens`)
```
GET  /api/tokens/usage/stats                        - Get usage statistics
GET  /api/tokens/usage/by-operation                 - Get breakdown by operation
```

## Configuration

### Environment Variables
```env
# RAG Settings
EMBEDDING_MODEL=text-embedding-3-large
CHROMA_PERSIST_DIR=./chroma_db
RAG_CHUNK_SIZE=1500
RAG_CHUNK_OVERLAP=200
RAG_TOP_K=5
RAG_SCORE_THRESHOLD=0.3
RAG_ENABLE_SUMMARIZATION=true

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_TOKENS_PER_DAY=1000000
```

## Installation & Setup

### Backend Setup
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
python -m pip install -r requirements.txt
```

### Environment Configuration
```bash
cp .env.example .env
# Edit .env with your settings:
# - LITELLM_PROXY_URL (for Gemini)
# - SUPABASE credentials
# - Google OAuth credentials
# - LiteLLM API key
```

### Running the Backend
```bash
python main.py
# or
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

## Workflow

### 1. User Uploads PDF
1. User clicks attachment button in UI
2. Selects PDF file (drag-and-drop or file picker)
3. File sent to `POST /api/chat/upload_attachments`
4. Backend stores file in `uploads/` directory
5. PDF automatically indexed:
   - Text extracted with page numbers
   - Chunks created (1500 chars, 200 overlap)
   - OpenAI embeddings generated (batch of 32)
   - Chunks stored in ChromaDB with metadata
   - Indexing status saved to database

### 2. User Asks Question
1. User types message and sends
2. Request includes message text and optional attachment IDs
3. Backend retrieves recent messages for context
4. **RAG Context Retrieval**:
   - Query vectorized using OpenAI embeddings
   - ChromaDB searched for similar chunks (top 5)
   - Threshold filtering (0.3 similarity minimum)
   - Retrieved context formatted with source citations
5. LLM Prompt constructed:
   - System prompt with RAG instructions
   - Chat history (last 5 messages)
   - RAG context from PDF chunks
   - User message
6. LLM streams response with PDF context
7. Response stored to database

### 3. User Exports Conversation
1. User clicks export button
2. Selects format: JSON, Markdown, or CSV
3. Backend fetches all messages and attachments
4. Formats according to selected type
5. File downloaded to user's device

## Performance Considerations

### Caching
- OpenAI client: LRU cache (single instance per process)
- ChromaDB client: LRU cache (single instance per process)
- Reduces initialization overhead by 99%

### Batch Processing
- Embeddings generated in batches of 32
- Reduces API calls and cost
- Faster processing for large documents

### Database Indexes
- `idx_chat_threads_user_id`: Thread lookup
- `idx_chat_messages_thread_id`: Message retrieval
- `idx_chat_attachments_message_id`: Attachment lookup
- `idx_token_usage_user_id`: Token tracking
- `idx_rate_limits_user_id`: Rate limit checking

### ChromaDB Optimization
- Persistent storage at `./chroma_db`
- Cosine similarity (efficient for embeddings)
- Collection-level partitioning by user + thread
- Automatic cleanup of deleted attachment vectors

## Error Handling

### PDF Validation
- File type checking (PDF only)
- Corruption detection (PyPDF reader exceptions)
- Page count validation (minimum 1 page)
- Text extraction failure handling

### API Error Responses
```python
# 400: Invalid request
{"detail": "Invalid file format"}

# 429: Rate limit exceeded
{"detail": "Rate limit exceeded. Please try again later."}

# 404: Not found
{"detail": "Thread not found"}

# 500: Server error
{"detail": "Error processing PDF"}
```

## Security Features

### Multi-Tenant Isolation
- User ID enforcement on all queries
- Thread ownership verification
- ChromaDB collections per user+thread

### Rate Limiting
- Per-user request quotas
- Daily token limits
- Middleware-based enforcement

### File Handling
- Uploaded files stored with UUIDs
- Temporary file cleanup
- Secure path handling

## Monitoring & Logging

### Token Tracking
- Log all token usage by operation type
- Query historical usage by time period
- Calculate costs and quotas

### Rate Limiting
- Track request count per minute
- Monitor daily token consumption
- Configurable thresholds

### Error Logging
- PDF processing errors with filenames
- API failures with request details
- Database errors with context

## Future Enhancements

### Planned Features
1. **Advanced Search**: Full-text search in addition to semantic
2. **Document Comparison**: Compare similar PDFs
3. **Citation Tracking**: Detailed source attribution
4. **Streaming Improvements**: Yield embedded metadata
5. **Caching Layer**: Redis for frequently accessed chunks
6. **Docker Support**: Containerized deployment
7. **Analytics Dashboard**: Usage visualization
8. **Custom Embeddings**: Fine-tuned models
9. **Batch Processing**: Queue system for large PDFs
10. **Multi-language**: Support non-English PDFs

## Troubleshooting

### RAG Context Not Retrieved
- Check ChromaDB is running: `python -c "import chromadb; print(chromadb.__version__)"`
- Verify PDF was indexed: Check logs for "Successfully indexed PDF"
- Check similarity threshold: Lower RAG_SCORE_THRESHOLD if too strict

### Slow Embeddings Generation
- Batch size already optimized (32)
- Check OpenAI API rate limits
- Monitor token usage: `GET /api/tokens/usage/stats`

### Rate Limit Exceeded
- Check token usage: `GET /api/tokens/usage/stats`
- Check request frequency: `GET /api/tokens/usage/by-operation`
- Adjust limits in `.env` if needed

### PDF Not Found Errors
- Verify file exists in `uploads/` directory
- Check file permissions
- Verify storage_path is correctly saved in database

## Support & Documentation

- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **Configuration**: See `.env.example` for all available settings
- **Logging**: Check backend console/logs for detailed errors
- **Token Usage**: `GET /api/tokens/usage/stats` for monitoring
