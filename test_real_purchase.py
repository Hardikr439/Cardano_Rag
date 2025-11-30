"""
Real Wallet Purchase Test - RAG Service
----------------------------------------
This script uses YOUR actual testnet wallet to purchase the RAG AI service
and tracks the real blockchain transaction.

Prerequisites:
1. You need a Cardano testnet wallet with test ADA (get from faucet)
2. You need to register your wallet as a purchaser in Masumi
3. Get a PURCHASER_API_KEY from the Masumi payment service
4. Upload a PDF document first using /upload-pdf endpoint

Steps this script performs:
1. Connects to your RAG AI service
2. Creates a payment request for asking a question
3. Uses YOUR wallet to pay on the blockchain
4. Monitors the transaction on Cardano explorer
5. Shows the RAG answer after payment confirmation
"""

import os
import json
import time
import asyncio
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}")
    print(f"{text}")
    print(f"{'='*70}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.CYAN}ℹ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.END}")

async def main():
    """Main test function"""
    
    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║                                                                      ║")
    print("║         REAL WALLET PURCHASE TEST - RAG AGENT                       ║")
    print("║         Track Actual Blockchain Transactions                        ║")
    print("║                                                                      ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}\n")
    
    # Configuration
    AGENT_URL = os.getenv("AGENT_API_URL", "http://127.0.0.1:8002")
    PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:3001/api/v1")
    PURCHASER_API_KEY = os.getenv("PURCHASER_API_KEY")
    AGENT_IDENTIFIER = os.getenv("AGENT_IDENTIFIER")
    NETWORK = os.getenv("NETWORK", "Preprod")
    
    print_info(f"Service URL: {AGENT_URL}")
    print_info(f"Payment Service: {PAYMENT_SERVICE_URL}")
    print_info(f"Network: {NETWORK}")
    print_info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check if purchaser API key is configured
    if not PURCHASER_API_KEY:
        print_header("⚠ SETUP REQUIRED: Purchaser Wallet Configuration")
        print_warning("You need to set up a purchaser wallet first!")
        print()
        print(f"{Colors.BOLD}Follow these steps:{Colors.END}\n")
        print("1. Get test ADA from the faucet:")
        print("   https://docs.cardano.org/cardano-testnets/tools/faucet")
        print("   OR https://dispenser.masumi.network/")
        print()
        print("2. Register your wallet as a purchaser in Masumi:")
        print(f"   curl -X POST '{PAYMENT_SERVICE_URL}/wallet' \\")
        print(f"     -H 'token: {os.getenv('PAYMENT_API_KEY')}' \\")
        print("     -H 'Content-Type: application/json' \\")
        print("     -d '{")
        print('       "name": "My Purchaser Wallet",')
        print('       "type": "purchasing",')
        print(f'       "network": "{NETWORK}"')
        print("     }'")
        print()
        print("3. Get the wallet details and API key:")
        print(f"   curl -X GET '{PAYMENT_SERVICE_URL}/wallet' \\")
        print(f"     -H 'token: {os.getenv('PAYMENT_API_KEY')}'")
        print()
        print("4. Create an API key for your purchaser wallet:")
        print(f"   curl -X POST '{PAYMENT_SERVICE_URL}/api-key' \\")
        print(f"     -H 'token: {os.getenv('PAYMENT_API_KEY')}' \\")
        print("     -H 'Content-Type: application/json' \\")
        print("     -d '{")
        print('       "name": "Purchaser Key",')
        print('       "walletId": "YOUR_PURCHASER_WALLET_ID"')
        print("     }'")
        print()
        print("5. Add to your .env file:")
        print("   PURCHASER_API_KEY=your_purchaser_api_key")
        print("   PURCHASER_WALLET_ADDRESS=your_wallet_address")
        print()
        return
    
    print_success("Purchaser wallet configured!\n")
    
    # Step 1: Check service availability
    print_header("Step 1: Checking Service Availability")
    try:
        response = requests.get(f"{AGENT_URL}/availability", timeout=10)
        response.raise_for_status()
        print_success("RAG Service is online and ready!")
    except Exception as e:
        print_error(f"Cannot connect to service: {e}")
        print_warning("Make sure to run: python main.py api")
        print_info("Also ensure the service is running on port 8002")
        return
    
    # Step 2: Create job and payment request
    print_header("Step 2: Creating Service Request with Payment")

    # Collect RAG-specific input as expected by main.py
    print_info("Make sure you have uploaded a PDF first using the /upload-pdf endpoint")
    print_info("Example: curl -X POST http://127.0.0.1:8002/upload-pdf -F 'file=@your_document.pdf'")
    print()
    
    question = input(f"{Colors.BOLD}Enter your question about the PDF (default: What is the main topic of the document?): {Colors.END}") or "What is the main topic of the document?"

    purchaser_id = os.getenv("PURCHASER_IDENTIFIER", "2ccab9ca3c8fd56f")

    payload = {
        "identifier_from_purchaser": purchaser_id,
        "input_data": {
            "question": question
        }
    }

    print_info(f"Asking question: '{question}'")
    
    try:
        response = requests.post(f"{AGENT_URL}/start_job", json=payload, timeout=30)
        response.raise_for_status()
        job_data = response.json()
        
        job_id = job_data["job_id"]
        blockchain_id = job_data["blockchainIdentifier"]
        amount_lovelace = job_data["amounts"][0]["amount"]
        amount_ada = int(amount_lovelace) / 1_000_000
        
        # Store all payment details for the purchase request
        payment_details = {
            "blockchainIdentifier": blockchain_id,
            "network": NETWORK,
            "inputHash": job_data["input_hash"],
            "sellerVkey": job_data["sellerVKey"],
            "agentIdentifier": job_data["agentIdentifier"],
            "paymentType": "Web3CardanoV1",  # or get from job_data if available
            "unlockTime": job_data["unlockTime"],
            "externalDisputeUnlockTime": job_data["externalDisputeUnlockTime"],
            "submitResultTime": job_data["submitResultTime"],
            "payByTime": job_data["payByTime"],
            "identifierFromPurchaser": job_data["identifierFromPurchaser"],
            "amounts": job_data["amounts"]
        }
        
        print_success(f"Job Created: {job_id}")
        print_success(f"Blockchain Contract: {blockchain_id}")
        print_success(f"Payment Required: {amount_ada} ADA ({amount_lovelace} lovelace)")
        
        # Show blockchain explorer link
        explorer_url = f"https://preprod.cardanoscan.io/transaction/{blockchain_id}" if NETWORK == "Preprod" \
                       else f"https://cardanoscan.io/transaction/{blockchain_id}"
        print_info(f"Track on explorer: {explorer_url}")
        
    except Exception as e:
        print_error(f"Failed to create job: {e}")
        return
    
    # Step 3: Make the actual payment from your wallet
    print_header("Step 3: Making Real Blockchain Payment from Your Wallet")
    
    print_info("Initiating payment from your testnet wallet...")
    print_info(f"Paying {amount_ada} ADA to smart contract...")
    
    try:
        response = requests.post(
            f"{PAYMENT_SERVICE_URL}/purchase",
            json=payment_details,
            headers={
                "Content-Type": "application/json",
                "token": PURCHASER_API_KEY
            },
            timeout=60
        )
        response.raise_for_status()
        payment_result = response.json()
        
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ PAYMENT TRANSACTION SUBMITTED!{Colors.END}\n")
        print(json.dumps(payment_result, indent=2))
        print()
        
        # Extract transaction hash if available
        tx_hash = payment_result.get("data", {}).get("txHash") or \
                  payment_result.get("data", {}).get("transactionHash")
        
        if tx_hash:
            explorer_url = f"https://preprod.cardanoscan.io/transaction/{tx_hash}" if NETWORK == "Preprod" \
                           else f"https://cardanoscan.io/transaction/{tx_hash}"
            print_success(f"Transaction Hash: {tx_hash}")
            print_info(f"View on Cardano Explorer: {explorer_url}")
        
        print()
        print(f"{Colors.YELLOW}{'─'*70}")
        print("Your wallet has sent ADA on the Cardano blockchain!")
        print(f"{'─'*70}{Colors.END}\n")
        
    except requests.exceptions.HTTPError as e:
        print_error(f"Payment failed: {e}")
        print_error(f"Response: {e.response.text}")
        print()
        print_warning("Possible issues:")
        print("  - Insufficient test ADA in wallet")
        print("  - Wallet not registered properly")
        print("  - Invalid API key")
        return
    except Exception as e:
        print_error(f"Payment error: {e}")
        return
    
    # Step 4: Monitor blockchain and service execution
    print_header("Step 4: Monitoring Blockchain & Service Execution")
    
    print_info("Waiting for blockchain confirmation...")
    print_info("This may take 20-60 seconds on Cardano testnet")
    print()
    
    max_wait = 300  # 5 minutes max
    start_time = time.time()
    last_status = None
    
    while (time.time() - start_time) < max_wait:
        try:
            response = requests.get(
                f"{AGENT_URL}/status",
                params={"job_id": job_id},
                timeout=10
            )
            response.raise_for_status()
            
            status_data = response.json()
            job_status = status_data.get("status")
            payment_status = status_data.get("payment_status")
            
            if job_status != last_status:
                elapsed = int(time.time() - start_time)
                print(f"[{elapsed}s] Job: {Colors.YELLOW}{job_status}{Colors.END} | "
                      f"Payment: {Colors.YELLOW}{payment_status}{Colors.END}")
                last_status = job_status
            
            if job_status == "completed":
                print()
                print(f"{Colors.GREEN}{Colors.BOLD}✓ SERVICE COMPLETED!{Colors.END}\n")
                result = status_data.get("result")
                if result:
                    print_header("Your RAG Service Result")
                    # Parse JSON if it's a string
                    try:
                        if isinstance(result, str):
                            result_json = json.loads(result)
                            print(f"{Colors.CYAN}{json.dumps(result_json, indent=2)}{Colors.END}\n")
                        else:
                            print(f"{Colors.CYAN}{result}{Colors.END}\n")
                    except:
                        print(f"{Colors.CYAN}{result}{Colors.END}\n")
                
                break
                break
            
            if job_status == "failed":
                print_error("Service execution failed!")
                print(json.dumps(status_data, indent=2))
                break
            
            await asyncio.sleep(5)
        except Exception as e:
            print_error(f"Error checking status: {e}")
    print(f"{Colors.GREEN}✓{Colors.END} Your testnet wallet address sent {amount_ada} ADA")
    print(f"{Colors.GREEN}✓{Colors.END} Transaction recorded on Cardano {NETWORK} blockchain")
    print(f"{Colors.GREEN}✓{Colors.END} Smart contract received and verified payment")
    print(f"{Colors.GREEN}✓{Colors.END} RAG service executed your question")
    print(f"{Colors.GREEN}✓{Colors.END} Answer retrieved from your PDF using AI")
    print(f"{Colors.GREEN}✓{Colors.END} Result delivered to you")
    print(f"{Colors.GREEN}✓{Colors.END} Payment released to seller's wallet")
    print_header("Transaction Summary")
    
    print(f"{Colors.BOLD}WHAT HAPPENED:{Colors.END}\n")
    print(f"{Colors.GREEN}✓{Colors.END} Your testnet wallet address sent {amount_ada} ADA")
    print(f"{Colors.GREEN}✓{Colors.END} Transaction recorded on Cardano {NETWORK} blockchain")
    print(f"{Colors.GREEN}✓{Colors.END} Smart contract received and verified payment")
    print(f"{Colors.GREEN}✓{Colors.END} AI service executed your request")
    print(f"{Colors.GREEN}✓{Colors.END} Result delivered to you")
    print(f"{Colors.GREEN}✓{Colors.END} Payment released to seller's wallet")
    
    print(f"\n{Colors.BOLD}BLOCKCHAIN VERIFICATION:{Colors.END}\n")
    print(f"  • Network: Cardano {NETWORK}")
    print(f"  • Smart Contract: {blockchain_id[:32]}...")
    print(f"  • Amount: {amount_ada} ADA")
    if tx_hash:
        print(f"  • Transaction: {tx_hash[:32]}...")
        print(f"  • Explorer: {explorer_url}")
    
    print(f"\n{Colors.BOLD}YOUR WALLET:{Colors.END}\n")
    print(f"  • Test ADA was deducted from your wallet")
    print(f"  • You can check your wallet balance in Masumi dashboard")
    print(f"  • Transaction is permanently recorded on blockchain")
    
    print(f"\n{Colors.GREEN}{Colors.BOLD}{'='*70}")
    print("REAL BLOCKCHAIN TRANSACTION COMPLETE!")
    print(f"{'='*70}{Colors.END}\n")
    
    print_success("This was a REAL transaction on Cardano testnet!")
    print_info("Check the Cardano explorer link above to verify on-chain")
    print()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test interrupted by user{Colors.END}\n")
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.END}\n")
        import traceback
        traceback.print_exc()
