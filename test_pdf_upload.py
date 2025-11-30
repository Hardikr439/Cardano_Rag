"""
PDF Upload Test Script
-----------------------
This script tests the PDF upload functionality of the RAG service.
Use this before testing the paid question-answering feature.
"""

import os
import requests
from pathlib import Path

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def test_upload_pdf(pdf_path: str, service_url: str = "http://127.0.0.1:8002"):
    """Test PDF upload to the RAG service"""
    
    print(f"\n{Colors.BOLD}{'='*70}")
    print("PDF Upload Test")
    print(f"{'='*70}{Colors.END}\n")
    
    # Check if file exists
    if not os.path.exists(pdf_path):
        print(f"{Colors.RED}✗ Error: File not found: {pdf_path}{Colors.END}")
        return False
    
    file_name = Path(pdf_path).name
    print(f"📄 Uploading: {file_name}")
    print(f"🔗 Service: {service_url}")
    print()
    
    try:
        # Open and upload the file
        with open(pdf_path, 'rb') as f:
            files = {'file': (file_name, f, 'application/pdf')}
            response = requests.post(
                f"{service_url}/upload-pdf",
                files=files,
                timeout=60
            )
        
        response.raise_for_status()
        result = response.json()
        
        print(f"{Colors.GREEN}✓ Upload successful!{Colors.END}")
        print(f"  Chunks processed: {result.get('chunks_processed', 'N/A')}")
        print(f"  Message: {result.get('message', 'N/A')}")
        print()
        print(f"{Colors.BOLD}Next Step:{Colors.END}")
        print(f"  Run: python test_real_purchase.py")
        print(f"  to ask paid questions about this PDF")
        print()
        return True
        
    except requests.exceptions.ConnectionError:
        print(f"{Colors.RED}✗ Error: Cannot connect to service{Colors.END}")
        print(f"{Colors.YELLOW}  Make sure the service is running: python main.py api{Colors.END}")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"{Colors.RED}✗ Upload failed: {e}{Colors.END}")
        print(f"  Response: {e.response.text}")
        return False
    except Exception as e:
        print(f"{Colors.RED}✗ Error: {e}{Colors.END}")
        return False

def main():
    """Main function"""
    import sys
    
    if len(sys.argv) < 2:
        print(f"\n{Colors.BOLD}Usage:{Colors.END}")
        print(f"  python test_pdf_upload.py <path_to_pdf>")
        print()
        print(f"{Colors.BOLD}Example:{Colors.END}")
        print(f"  python test_pdf_upload.py document.pdf")
        print(f"  python test_pdf_upload.py C:\\Users\\Documents\\report.pdf")
        print()
        return
    
    pdf_path = sys.argv[1]
    service_url = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8002"
    
    test_upload_pdf(pdf_path, service_url)

if __name__ == "__main__":
    main()
