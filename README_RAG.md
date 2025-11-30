# RAG Service with Masumi Payment Integration

This project implements a RAG (Retrieval-Augmented Generation) service that allows users to upload PDFs and ask questions about them. The PDF upload is free, but asking questions requires payment via the Masumi blockchain payment system.

## Architecture

- **Free Service**: PDF upload and indexing (`/upload-pdf`)
- **Paid Service**: Question answering with RAG (`/start_job`)
- **Payment System**: Masumi blockchain payments on Cardano

## Prerequisites

1. **Python Dependencies**
   ```bash
   uv pip install -r requirements.txt
   ```

2. **Environment Variables** (`.env` file)
   ```env
   # Gemini API
   GEMINI_API_KEY=your_gemini_api_key
   
   # Masumi Payment Configuration
   PAYMENT_SERVICE_URL=http://localhost:3001/api/v1
   PAYMENT_API_KEY=your_payment_api_key
   NETWORK=Preprod
   AGENT_IDENTIFIER=your_agent_identifier
   SELLER_VKEY=your_seller_vkey
   
   # Service Configuration
   API_PORT=8002
   API_HOST=127.0.0.1
   PAYMENT_AMOUNT=10000000
   PAYMENT_UNIT=lovelace
   
   # For testing purchases (optional)
   PURCHASER_API_KEY=your_purchaser_api_key
   PURCHASER_IDENTIFIER=your_purchaser_id
   ```

3. **Cardano Testnet Wallet** (for testing)
   - Get test ADA from: https://docs.cardano.org/cardano-testnets/tools/faucet
   - Or: https://dispenser.masumi.network/

## Quick Start

### 1. Start the Service

```bash
python main.py api
```

The service will start on `http://127.0.0.1:8002`

Available endpoints:
- `GET /docs` - API documentation
- `GET /availability` - Check service status
- `GET /health` - Health check
- `GET /input_schema` - Get input schema for questions
- `POST /upload-pdf` - Upload PDF (FREE)
- `POST /start_job` - Ask question (PAID via Masumi)
- `GET /status` - Check job status

### 2. Upload a PDF (Free)

**Option A: Using the test script**
```bash
python test_pdf_upload.py path/to/your/document.pdf
```

**Option B: Using curl**
```bash
curl -X POST http://127.0.0.1:8002/upload-pdf \
  -F "file=@document.pdf"
```

**Option C: Using Python**
```python
import requests

with open('document.pdf', 'rb') as f:
    files = {'file': f}
    response = requests.post('http://127.0.0.1:8002/upload-pdf', files=files)
    print(response.json())
```

### 3. Ask Questions (Paid with Masumi)

**Option A: Using the test script (Real Blockchain Payment)**
```bash
python test_real_purchase.py
```

This script will:
1. Create a payment request
2. Use your testnet wallet to pay on blockchain
3. Monitor the transaction
4. Show the answer after payment confirmation

**Option B: Manual API calls**

1. Create a job and payment request:
```bash
curl -X POST http://127.0.0.1:8002/start_job \
  -H "Content-Type: application/json" \
  -d '{
    "identifier_from_purchaser": "your_identifier",
    "input_data": {
      "question": "What is the main topic of the document?"
    }
  }'
```

2. Pay using the Masumi payment service

3. Check status:
```bash
curl "http://127.0.0.1:8002/status?job_id=YOUR_JOB_ID"
```

## Testing Workflow

### Complete Test Flow

1. **Start the service**
   ```bash
   python main.py api
   ```

2. **Upload a test PDF**
   ```bash
   python test_pdf_upload.py sample.pdf
   ```

3. **Test with real blockchain payment**
   ```bash
   python test_real_purchase.py
   ```

### Standalone Testing (No API)

Test the RAG functionality directly without the API:

```bash
python main.py
```

This will run a test question against the indexed PDFs.

## API Endpoints

### Free Endpoints

#### `POST /upload-pdf`
Upload and index a PDF document.

**Request:**
- Content-Type: `multipart/form-data`
- Field: `file` (PDF file)

**Response:**
```json
{
  "message": "PDF uploaded and indexed successfully",
  "chunks_processed": 42
}
```

#### `GET /availability`
Check if service is available.

**Response:**
```json
{
  "status": "available",
  "type": "masumi-agent",
  "message": "Server operational."
}
```

#### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy"
}
```

#### `GET /input_schema`
Get the input schema for questions.

**Response:**
```json
{
  "input_data": [
    {
      "id": "question",
      "type": "string",
      "name": "Question",
      "data": {
        "description": "Your question about the uploaded PDF document",
        "placeholder": "What is the main topic of the document?"
      }
    }
  ]
}
```

### Paid Endpoints (Masumi Integration)

#### `POST /start_job`
Create a job to ask a question (requires payment).

**Request:**
```json
{
  "identifier_from_purchaser": "unique_purchaser_id",
  "input_data": {
    "question": "What is the main topic of the document?"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "job_id": "uuid",
  "blockchainIdentifier": "blockchain_contract_id",
  "amounts": [{"amount": "10000000", "unit": "lovelace"}],
  "payByTime": "2025-11-30T12:00:00Z",
  ...
}
```

#### `GET /status?job_id=<job_id>`
Check job and payment status.

**Response:**
```json
{
  "job_id": "uuid",
  "status": "completed",
  "payment_status": "completed",
  "result": "{\"answer\": \"The document discusses...\"}"
}
```

## How It Works

### PDF Upload Flow (Free)

1. User uploads PDF via `/upload-pdf`
2. System extracts text from PDF
3. Text is chunked into 1000-character segments
4. Each chunk is embedded using Google's text-embedding-004 model
5. Embeddings are stored in FAISS vector store
6. User receives confirmation

### Question Answering Flow (Paid)

1. User calls `/start_job` with a question
2. System creates a Masumi payment request
3. User pays on Cardano blockchain
4. System monitors blockchain for payment confirmation
5. Once confirmed:
   - Question is embedded
   - Similar chunks are retrieved from vector store
   - Gemini AI generates answer using retrieved context
   - Answer is returned to user
   - Payment is released to seller

## Project Structure

```
Cardano_Rag/
├── main.py                    # Main FastAPI application
├── app.py                     # Original Flask app (reference)
├── logging_config.py          # Logging configuration
├── requirements.txt           # Python dependencies
├── test_pdf_upload.py         # Test PDF upload
├── test_real_purchase.py      # Test blockchain payment
├── rag/
│   ├── __init__.py
│   ├── pdf_loader.py         # PDF text extraction
│   ├── embedder.py           # Text embedding
│   └── vector_store.py       # FAISS vector storage
└── uploads/                   # Uploaded PDFs storage
```

## Troubleshooting

### Service Won't Start

1. Check if all dependencies are installed:
   ```bash
   uv pip install -r requirements.txt
   ```

2. Verify environment variables in `.env`

3. Check if port 8002 is available

### PDF Upload Fails

1. Ensure the service is running
2. Check file is a valid PDF
3. Verify sufficient disk space
4. Check logs for specific error

### Payment/Question Fails

1. Verify Masumi configuration in `.env`
2. Check wallet has sufficient test ADA
3. Ensure PDF was uploaded first
4. Check payment service is running
5. Monitor logs for detailed errors

### No Results Returned

1. Verify PDF was successfully uploaded and indexed
2. Check if question is relevant to uploaded PDF
3. Try more specific questions
4. Check Gemini API key is valid

## Development

### Running in Development Mode

```bash
# Start with auto-reload
uvicorn main:app --reload --port 8002

# Or use the script
python main.py api
```

### Testing Without Blockchain

For testing the RAG functionality without blockchain payments:

```bash
python main.py
```

This runs in standalone mode with a test question.

## Security Notes

⚠️ **Important for Production:**

1. The current implementation uses in-memory storage for jobs (not persistent)
2. No authentication on `/upload-pdf` endpoint
3. No rate limiting implemented
4. Consider adding:
   - User authentication
   - Rate limiting
   - Persistent job storage (database)
   - File size limits
   - Virus scanning for uploads
   - HTTPS/TLS

## Support

For issues related to:
- **Masumi Payments**: Check Masumi documentation
- **Cardano Blockchain**: Visit Cardano testnets documentation
- **Gemini API**: Refer to Google AI documentation

## License

[Your License Here]
