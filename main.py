import os
import uvicorn
import uuid
import asyncio
import json
from dotenv import load_dotenv
from fastapi import FastAPI, Query, HTTPException, UploadFile, File
from pydantic import BaseModel, Field, field_validator
from masumi.config import Config
from masumi.payment import Payment, Amount
from logging_config import setup_logging
import google.generativeai as genai

from rag.pdf_loader import load_pdf
from rag.embedder import get_embedding
from rag.vector_store import vector_store


# Configure logging
logger = setup_logging()

# Load environment variables
load_dotenv(override=True)

# Retrieve API Keys and URLs
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL")
PAYMENT_API_KEY = os.getenv("PAYMENT_API_KEY")
NETWORK = os.getenv("NETWORK")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

logger.info("Starting application with configuration:")
logger.info(f"PAYMENT_SERVICE_URL: {PAYMENT_SERVICE_URL}")

# Initialize FastAPI
app = FastAPI(
    title="RAG API following the Masumi API Standard",
    description="API for RAG services with Masumi payment integration for question answering",
    version="1.0.0"
)

# Create uploads folder
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Temporary in-memory job store (DO NOT USE IN PRODUCTION)
# ─────────────────────────────────────────────────────────────────────────────
jobs = {}
payment_instances = {}

# ─────────────────────────────────────────────────────────────────────────────
# Initialize Masumi Payment Config
# ─────────────────────────────────────────────────────────────────────────────
config = Config(
    payment_service_url=PAYMENT_SERVICE_URL,
    payment_api_key=PAYMENT_API_KEY
)

# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────────────────────────
class StartJobRequest(BaseModel):
    identifier_from_purchaser: str
    input_data: dict[str, str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "identifier_from_purchaser": "example_purchaser_123",
                "input_data": {
                    "question": "What is the main topic of the document?"
                }
            }
        }

class ProvideInputRequest(BaseModel):
    job_id: str

# ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def execute_rag_task(input_data: dict) -> str:
    """ Execute RAG question answering task """
    logger.info(f"Starting RAG task with input: {input_data}")
    
    query = input_data.get("question")
    if not query:
        raise ValueError("Question missing from input_data")
    
    # 1. Embed question
    query_emb = get_embedding(query)
    
    # 2. Retrieve context chunks
    context_chunks = vector_store.search(query_emb, k=5)
    context = "\n\n".join(context_chunks)
    
    # 3. Ask Gemini with retrieved context
    prompt = f"""
You are a helpful assistant. Use ONLY the following PDF context:

{context}

Question: {query}

Required output format and rules:
- Return ONLY a single valid JSON object and nothing else (no markdown, no backticks, no commentary).
- The JSON must contain exactly one key: "answer" whose value is a string.
- The answer string MUST NOT contain newline characters (\\n), bullet characters ("*", "-", "•"), or any markdown formatting (no **, __, etc.).
- Do NOT use currency symbols. Replace the rupee symbol '₹' with the word " ruppees" (note the leading space) so amounts look like: "6,00,000 ruppees".
- Keep the answer concise and factual, based strictly on the provided PDF context.

Return the JSON only.
"""
    
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    
    # Try to parse the model output as JSON. If parsing fails, sanitize the text.
    try:
        parsed = json.loads(response.text)
        # Ensure the parsed object has the expected shape
        if isinstance(parsed, dict) and "answer" in parsed:
            return json.dumps(parsed)
    except Exception:
        pass
    
    # Fallback sanitization: remove newlines, bullets, markdown and replace rupee symbol
    ans = response.text
    ans = ans.replace('\n', ' ').replace('\r', ' ')
    for ch in ['*', '•']:
        ans = ans.replace(ch, '')
    ans = ans.replace('-', ' ')
    ans = ans.replace('₹', ' ruppees')
    # Collapse multiple spaces
    ans = ' '.join(ans.split())
    
    return json.dumps({"answer": ans})

# ─────────────────────────────────────────────────────────────────────────────
# PDF Upload Endpoint (No Masumi Integration)
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """ Upload and index PDF without payment requirement """
    try:
        logger.info(f"Received PDF upload: {file.filename}")
        
        # Save file
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 1. Extract PDF text
        text = load_pdf(file_path)
        
        # 2. Chunking (simple splitting)
        chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
        
        # 3. Embed & store
        for chunk in chunks:
            emb = get_embedding(chunk)
            vector_store.add(emb, chunk)
        
        logger.info(f"PDF {file.filename} uploaded and indexed successfully")
        return {"message": "PDF uploaded and indexed successfully", "chunks_processed": len(chunks)}
    
    except Exception as e:
        logger.error(f"Error uploading PDF: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

# ─────────────────────────────────────────────────────────────────────────────
# 1) Start Job (MIP-003: /start_job) - For Question Answering
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/start_job")
async def start_job(data: StartJobRequest):
    """ Initiates a RAG question answering job and creates a payment request """
    logger.info(f"Received data: {data}")
    logger.info(f"Received data.input_data: {data.input_data}")
    try:
        job_id = str(uuid.uuid4())
        agent_identifier = os.getenv("AGENT_IDENTIFIER")
        
        # Validate RAG-specific fields
        if "question" not in data.input_data:
            logger.error("Missing required field: question")
            raise HTTPException(
                status_code=400,
                detail="Missing required field: question"
            )
        
        # Log the question
        logger.info(f"Received RAG question: {data.input_data['question']}")
        logger.info(f"Starting job {job_id} with agent {agent_identifier}")

        # Define payment amounts
        payment_amount = os.getenv("PAYMENT_AMOUNT", "10000000")  # Default 10 ADA
        payment_unit = os.getenv("PAYMENT_UNIT", "lovelace") # Default lovelace

        amounts = [Amount(amount=payment_amount, unit=payment_unit)]
        logger.info(f"Using payment amount: {payment_amount} {payment_unit}")
        
        # Create a payment request using Masumi
        payment = Payment(
            agent_identifier=agent_identifier,
            #amounts=amounts,
            config=config,
            identifier_from_purchaser=data.identifier_from_purchaser,
            input_data=data.input_data,
            network=NETWORK
        )
        
        logger.info("Creating payment request...")
        payment_request = await payment.create_payment_request()
        blockchain_identifier = payment_request["data"]["blockchainIdentifier"]
        payment.payment_ids.add(blockchain_identifier)
        logger.info(f"Created payment request with blockchain identifier: {blockchain_identifier}")

        # Store job info (Awaiting payment)
        jobs[job_id] = {
            "status": "awaiting_payment",
            "payment_status": "pending",
            "blockchain_identifier": blockchain_identifier,
            "input_data": data.input_data,
            "result": None,
            "identifier_from_purchaser": data.identifier_from_purchaser
        }

        async def payment_callback(blockchain_identifier: str):
            await handle_payment_status(job_id, blockchain_identifier)

        # Start monitoring the payment status
        payment_instances[job_id] = payment
        logger.info(f"Starting payment status monitoring for job {job_id}")
        await payment.start_status_monitoring(payment_callback)

        # Return the response in the required format
        return {
            "status": "success",
            "job_id": job_id,
            "blockchainIdentifier": blockchain_identifier,
            "submitResultTime": payment_request["data"]["submitResultTime"],
            "unlockTime": payment_request["data"]["unlockTime"],
            "externalDisputeUnlockTime": payment_request["data"]["externalDisputeUnlockTime"],
            "agentIdentifier": agent_identifier,
            "sellerVKey": os.getenv("SELLER_VKEY"),
            "identifierFromPurchaser": data.identifier_from_purchaser,
            "amounts": amounts,
            "input_hash": payment.input_hash,
            "payByTime": payment_request["data"]["payByTime"],
        }
    except KeyError as e:
        logger.error(f"Missing required field in request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="Bad Request: If input_data or identifier_from_purchaser is missing, invalid, or does not adhere to the schema."
        )
    except Exception as e:
        logger.error(f"Error in start_job: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="Input_data or identifier_from_purchaser is missing, invalid, or does not adhere to the schema."
        )

# ─────────────────────────────────────────────────────────────────────────────
# 2) Process Payment and Execute RAG Task
# ─────────────────────────────────────────────────────────────────────────────
async def handle_payment_status(job_id: str, payment_id: str) -> None:
    """ Executes RAG task after payment confirmation """
    try:
        logger.info(f"Payment {payment_id} completed for job {job_id}, executing task...")
        
        # Update job status to running
        jobs[job_id]["status"] = "running"
        logger.info(f"Input data: {jobs[job_id]['input_data']}")

        # Execute the RAG task
        result = await execute_rag_task(jobs[job_id]["input_data"])
        logger.info(f"RAG task completed for job {job_id}")
        
        # Mark payment as completed on Masumi
        await payment_instances[job_id].complete_payment(payment_id, result)
        logger.info(f"Payment completed for job {job_id}")

        # Update job status
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["payment_status"] = "completed"
        jobs[job_id]["result"] = result

        # Stop monitoring payment status
        if job_id in payment_instances:
            payment_instances[job_id].stop_status_monitoring()
            del payment_instances[job_id]
    except Exception as e:
        logger.error(f"Error processing payment {payment_id} for job {job_id}: {str(e)}", exc_info=True)
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        
        # Still stop monitoring to prevent repeated failures
        if job_id in payment_instances:
            payment_instances[job_id].stop_status_monitoring()
            del payment_instances[job_id]

# ─────────────────────────────────────────────────────────────────────────────
# 3) Check Job and Payment Status (MIP-003: /status)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/status")
async def get_status(job_id: str):
    """ Retrieves the current status of a specific job """
    logger.info(f"Checking status for job {job_id}")
    if job_id not in jobs:
        logger.warning(f"Job {job_id} not found")
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    # Check latest payment status if payment instance exists
    if job_id in payment_instances:
        try:
            status = await payment_instances[job_id].check_payment_status()
            job["payment_status"] = status.get("data", {}).get("status")
            logger.info(f"Updated payment status for job {job_id}: {job['payment_status']}")
        except ValueError as e:
            logger.warning(f"Error checking payment status: {str(e)}")
            job["payment_status"] = "unknown"
        except Exception as e:
            logger.error(f"Error checking payment status: {str(e)}", exc_info=True)
            job["payment_status"] = "error"

    result_data = job.get("result")
    logger.info(f"Result data: {result_data}")

    return {
        "job_id": job_id,
        "status": job["status"],
        "payment_status": job["payment_status"],
        "result": result_data
    }

# ─────────────────────────────────────────────────────────────────────────────
# 4) Check Server Availability (MIP-003: /availability)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/availability")
async def check_availability():
    """ Checks if the server is operational """
    return {"status": "available", "type": "masumi-agent", "message": "Server operational."}

# ─────────────────────────────────────────────────────────────────────────────
# 5) Retrieve Input Schema (MIP-003: /input_schema)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/input_schema")
async def input_schema():
    """
    Returns the expected input schema for the /start_job endpoint.
    Fulfills MIP-003 /input_schema endpoint.
    """
    return {
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

# ─────────────────────────────────────────────────────────────────────────────
# 6) Health Check
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    """
    Returns the health of the server.
    """
    return {
        "status": "healthy"
    }

# ─────────────────────────────────────────────────────────────────────────────
# Main Logic if Called as a Script
# ─────────────────────────────────────────────────────────────────────────────
async def main():
    """Run the standalone RAG flow without the API"""
    import sys
    
    print("\n" + "=" * 70)
    print("🚀 Running RAG agent locally (standalone mode)...")
    print("=" * 70 + "\n")
    
    # Define test input
    input_data = {"question": "What is the main topic of the document?"}
    
    print(f"Question: {input_data['question']}")
    print("\nProcessing with RAG agent...\n")
    
    # Execute the RAG task
    result = await execute_rag_task(input_data)
    
    # Display the result
    print("\n" + "=" * 70)
    print("✅ RAG Output:")
    print("=" * 70 + "\n")
    print(result)
    print("\n" + "=" * 70 + "\n")
    
    # Ensure terminal is properly reset
    sys.stdout.flush()
    sys.stderr.flush()

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "api":
        # Run API mode
        port = int(os.environ.get("PORT", os.environ.get("API_PORT", 8081)))
        host = os.environ.get("API_HOST", "0.0.0.0")

        print("\n" + "=" * 70)
        print("🚀 Starting FastAPI server with Masumi integration...")
        print("=" * 70)
        print(f"API Documentation:        http://{host}:{port}/docs")
        print(f"Availability Check:       http://{host}:{port}/availability")
        print(f"Status Check:             http://{host}:{port}/status")
        print(f"Input Schema:             http://{host}:{port}/input_schema")
        print(f"Upload PDF:               http://{host}:{port}/upload-pdf\n")
        print("=" * 70 + "\n")

        uvicorn.run(app, host=host, port=port, log_level="info")
    else:
        # Run standalone mode
        asyncio.run(main())
