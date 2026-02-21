#!/usr/bin/env python3
"""
Mathpix OCR Batch Processor for 3GPP Specifications

Features:
- Batch process multiple PDFs using Mathpix API
- LaTeX styled output for better LLM understanding
- Concurrent processing with rate limiting
- Progress saving and resuming
- Automatic retry on failures
- Detailed logging
- Cost estimation
"""

import os
import sys
import json
import time
import requests
import argparse
import logging
import pdfplumber
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import List, Dict, Optional, Tuple

# ==================== Configuration ====================

# Mathpix API Configuration
MATHPIX_APP_ID = "XXXXXX"  # Your actual app_id
MATHPIX_APP_KEY = "MATHPIX_APP_KEY"  # Your actual app_key

# Paths
INPUT_DIR = "../pdf_specifications"
OUTPUT_DIR = "../outputs/txt_specifications_mathpix"
PROGRESS_FILE = "../outputs/mathpix_progress.json"
LOG_FILE = "../outputs/mathpix_processor.log"

# Processing Configuration
MAX_WORKERS = 1  # Serial processing (changed from 2 for simpler CID-based strategy)
RETRY_ATTEMPTS = 3  # Retry failed pages
RATE_LIMIT_DELAY = 2.5  # Delay between API calls (seconds) - adjusted for 50 req/min limit

# CID Detection Configuration
CID_THRESHOLD = -1  # ALL pages use Mathpix (set to -1 to process everything with Mathpix)
                     # Original: 5 (only pages with CID > 5 use Mathpix)

# Rate Limit Configuration
# Your API limit: 50 requests/minute, 5000 pages/month
# With ALL pages using Mathpix: 2213 API calls total (~4.3 hours)

# Cost Configuration (Your account specifics)
COST_PER_PAGE = 0.0  # FREE! You have 5000 pages/month included
FREE_TIER_PAGES = 5000  # Your monthly quota
# Your 1,650 pages will cost: $0.00 (completely free!)

# ==================== Setup Logging ====================

def setup_logging(verbose: bool = True):
    """Setup logging configuration"""
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Create output directory if not exists
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    
    # Setup handlers
    handlers = [
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
    
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers
    )
    
    return logging.getLogger(__name__)

# ==================== Progress Management ====================

class ProgressManager:
    """Manage processing progress with file-based persistence"""
    
    def __init__(self, progress_file: str):
        self.progress_file = progress_file
        self.lock = Lock()
        self.data = self.load()
    
    def load(self) -> Dict:
        """Load progress from file"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logging.warning(f"Failed to load progress file: {e}")
                return {}
        return {}
    
    def save(self):
        """Save progress to file (assumes caller already holds lock)"""
        os.makedirs(os.path.dirname(self.progress_file), exist_ok=True)
        with open(self.progress_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def is_completed(self, pdf_name: str, page_num: int) -> bool:
        """Check if a page has been completed"""
        with self.lock:
            if pdf_name not in self.data:
                return False
            return page_num in self.data[pdf_name].get('completed_pages', [])
    
    def mark_completed(self, pdf_name: str, page_num: int):
        """Mark a page as completed"""
        with self.lock:
            if pdf_name not in self.data:
                self.data[pdf_name] = {
                    'completed_pages': [],
                    'failed_pages': [],
                    'started_at': datetime.now().isoformat(),
                    'last_updated': datetime.now().isoformat()
                }
            
            if page_num not in self.data[pdf_name]['completed_pages']:
                self.data[pdf_name]['completed_pages'].append(page_num)
            
            self.data[pdf_name]['last_updated'] = datetime.now().isoformat()
            self.save()
    
    def mark_failed(self, pdf_name: str, page_num: int, error: str):
        """Mark a page as failed"""
        with self.lock:
            if pdf_name not in self.data:
                self.data[pdf_name] = {
                    'completed_pages': [],
                    'failed_pages': [],
                    'started_at': datetime.now().isoformat()
                }
            
            failure_info = {
                'page': page_num,
                'error': error,
                'timestamp': datetime.now().isoformat()
            }
            
            self.data[pdf_name]['failed_pages'].append(failure_info)
            self.data[pdf_name]['last_updated'] = datetime.now().isoformat()
            self.save()
    
    def get_stats(self, pdf_name: str) -> Dict:
        """Get processing statistics for a PDF"""
        with self.lock:
            if pdf_name not in self.data:
                return {'completed': 0, 'failed': 0}
            
            return {
                'completed': len(self.data[pdf_name].get('completed_pages', [])),
                'failed': len(self.data[pdf_name].get('failed_pages', []))
            }

# ==================== Mathpix API Client ====================

class MathpixClient:
    """Client for Mathpix OCR API"""
    
    def __init__(self, app_id: str, app_key: str):
        self.app_id = app_id
        self.app_key = app_key
        self.api_url = "https://api.mathpix.com/v3/text"  # Changed from /v3/pdf to /v3/text
        self.rate_limiter = Lock()
        self.last_request_time = 0
    
    def process_pdf_page(self, pdf_path: str, page_num: int, 
                        output_format: str = 'text') -> Optional[str]:  # Changed default to 'text'
        """
        Process a single PDF page using Mathpix API
        
        Strategy: Extract single page as image, then send to API
        Uses /v3/text endpoint which returns 'text' field with LaTeX content
        
        Args:
            pdf_path: Path to PDF file
            page_num: Page number (1-indexed)
            output_format: Output format ('text' works, 'latex_styled' doesn't for free accounts)
        
        Returns:
            Processed content or None if failed
        """
        # Rate limiting
        with self.rate_limiter:
            time_since_last = time.time() - self.last_request_time
            if time_since_last < RATE_LIMIT_DELAY:
                time.sleep(RATE_LIMIT_DELAY - time_since_last)
            self.last_request_time = time.time()
        
        # Extract single page as image using pdfplumber
        import base64
        from io import BytesIO
        
        try:
            logging.debug(f"Extracting page {page_num} as image")
            
            with pdfplumber.open(pdf_path) as pdf:
                if page_num < 1 or page_num > len(pdf.pages):
                    logging.error(f"Invalid page number: {page_num}")
                    return None
                
                page = pdf.pages[page_num - 1]  # 0-indexed
                
                # Convert page to image (PIL Image)
                # Using 150 DPI with JPEG 85% - OCR industry standard for high quality
                img = page.to_image(resolution=150)  # 150 DPI - industry standard
                pil_img = img.original
                
                # Convert PIL image to base64 using JPEG with high quality (85%)
                buffered = BytesIO()
                pil_img.save(buffered, format="JPEG", quality=85)  # 85% quality - minimal compression loss
                img_data = base64.b64encode(buffered.getvalue()).decode('utf-8')
                mime_type = "image/jpeg"
                
                # Check image size - skip if too large
                img_size_mb = len(img_data) / (1024 * 1024)
                logging.info(f"  → Image size: {img_size_mb:.2f} MB")
                
                if img_size_mb > 3.0:  # Skip if larger than 3MB
                    logging.warning(f"  → Image too large ({img_size_mb:.2f} MB), skipping Mathpix")
                    return None
                
                logging.debug(f"Image size: {len(img_data)} chars")
                
        except Exception as e:
            logging.error(f"Failed to extract page as image: {str(e)}")
            return None
        
        # Prepare API request
        headers = {
            'app_id': self.app_id,
            'app_key': self.app_key
        }
        
        data = {
            'src': f'data:{mime_type};base64,{img_data}',  # Now using PNG
            'formats': [output_format],  # Will be 'text'
            'format_options': {
                'math_inline_delimiters': ['$', '$'],
                'math_display_delimiters': ['$$', '$$']
            }
        }
        
        # Make API request
        try:
            logging.debug(f"Sending request to Mathpix API for page {page_num}")
            response = requests.post(
                self.api_url,
                json=data,
                headers=headers,
                timeout=60
            )
            
            logging.debug(f"Mathpix API response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                # Log full response for debugging
                logging.info(f"  → Mathpix API response keys: {list(result.keys())}")
                
                content = result.get(output_format, '')
                if content:
                    logging.info(f"  → Mathpix succeeded! Got {len(content)} chars in '{output_format}' field")
                    return content
                else:
                    logging.warning(f"  → API returned 200 but no content in '{output_format}' field")
                    logging.info(f"  → Full response: {result}")
                    return None
            else:
                # Detailed error logging
                error_msg = f"API error: {response.status_code}"
                try:
                    error_details = response.json()
                    error_msg += f" - {error_details}"
                except:
                    error_msg += f" - {response.text[:200]}"
                
                logging.error(error_msg)
                return None
                
        except requests.exceptions.Timeout:
            logging.error(f"Request timeout (60s) for page {page_num}")
            return None
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Connection error: {str(e)}")
            return None
        except Exception as e:
            logging.error(f"Request failed: {str(e)}")
            return None

# ==================== pdfplumber Fallback ====================

def extract_with_pdfplumber(pdf_path: str, page_num: int) -> Optional[str]:
    """
    Extract page content using pdfplumber
    
    Args:
        pdf_path: Path to PDF file
        page_num: Page number (1-indexed)
    
    Returns:
        Extracted text or None if failed
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_num < 1 or page_num > len(pdf.pages):
                logging.error(f"Invalid page number: {page_num}")
                return None
            
            page = pdf.pages[page_num - 1]  # pdfplumber uses 0-indexed
            text = page.extract_text()
            
            if text:
                return text
            else:
                return None
                
    except Exception as e:
        logging.error(f"pdfplumber extraction failed: {str(e)}")
        return None

# ==================== PDF Processing ====================

def get_pdf_page_count(pdf_path: str) -> int:
    """Get total page count of a PDF"""
    try:
        import PyPDF2
        with open(pdf_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            return len(pdf_reader.pages)
    except:
        # Fallback: use pdfplumber
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                return len(pdf.pages)
        except Exception as e:
            logging.error(f"Failed to get page count for {pdf_path}: {e}")
            return 0

def process_single_page(
    client: MathpixClient,
    pdf_path: str,
    pdf_name: str,
    page_num: int,
    output_dir: str,
    progress_mgr: ProgressManager
) -> Tuple[bool, str]:
    """
    Process a single page with NEW strategy: pdfplumber first + CID detection
    
    Strategy:
    1. Extract with pdfplumber (fast & reliable)
    2. Count CID occurrences
    3. If CID > 5 → try Mathpix for better quality
    4. If Mathpix fails or CID ≤ 5 → keep pdfplumber result
    
    Returns:
        (success, message)
    """
    import re
    
    # Check if already completed
    if progress_mgr.is_completed(pdf_name, page_num):
        return True, "Already completed"
    
    # ═══════════════════════════════════════════
    # Phase 1: Extract with pdfplumber (always)
    # ═══════════════════════════════════════════
    
    logging.info(f"Processing {pdf_name} page {page_num} with pdfplumber")
    
    try:
        pdfplumber_content = extract_with_pdfplumber(pdf_path, page_num)
        
        if not pdfplumber_content:
            # pdfplumber failed (rare)
            error_msg = "pdfplumber extraction failed"
            logging.error(f"✗ {pdf_name} page {page_num}: {error_msg}")
            progress_mgr.mark_failed(pdf_name, page_num, error_msg)
            return False, error_msg
        
        # Count CID occurrences
        cid_pattern = r'\(cid:\d+\)'
        cid_matches = re.findall(cid_pattern, pdfplumber_content)
        cid_count = len(cid_matches)
        
        logging.info(f"  → pdfplumber extracted, CID count: {cid_count}")
        
    except Exception as e:
        error_msg = f"pdfplumber error: {str(e)}"
        logging.error(f"✗ {pdf_name} page {page_num}: {error_msg}")
        progress_mgr.mark_failed(pdf_name, page_num, error_msg)
        return False, error_msg
    
    # ═══════════════════════════════════════════
    # Phase 2: Decide whether to use Mathpix
    # ═══════════════════════════════════════════
    
    if cid_count <= CID_THRESHOLD:
        # CID count is low, pdfplumber result is good enough
        processing_method = "pdfplumber"
        final_content = pdfplumber_content
        
        logging.info(f"  → CID count ≤ {CID_THRESHOLD}, using pdfplumber result")
    
    else:
        # CID count is high, try Mathpix for better quality
        logging.info(f"  → CID count > {CID_THRESHOLD}, trying Mathpix for better quality")
        
        mathpix_success = False
        
        # Try Mathpix with retries
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                logging.info(f"  → Mathpix attempt {attempt}/{RETRY_ATTEMPTS}")
                
                mathpix_content = client.process_pdf_page(pdf_path, page_num)
                
                if mathpix_content:
                    # Mathpix succeeded!
                    processing_method = "mathpix"
                    final_content = mathpix_content
                    mathpix_success = True
                    
                    logging.info(f"  → Mathpix succeeded!")
                    break
                else:
                    if attempt < RETRY_ATTEMPTS:
                        logging.warning(f"  → Mathpix attempt {attempt} failed, retrying...")
                        time.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        logging.warning(f"  → Mathpix failed after {RETRY_ATTEMPTS} attempts")
            
            except Exception as e:
                logging.error(f"  → Mathpix error on attempt {attempt}: {str(e)}")
                if attempt < RETRY_ATTEMPTS:
                    time.sleep(2 ** attempt)
        
        if not mathpix_success:
            # Mathpix failed, fall back to pdfplumber result
            processing_method = "pdfplumber_fallback"
            final_content = pdfplumber_content
            
            logging.info(f"  → Mathpix failed, keeping pdfplumber result (with {cid_count} CIDs)")
    
    # ═══════════════════════════════════════════
    # Phase 3: Save result
    # ═══════════════════════════════════════════
    
    logging.info(f"  → Phase 3: Saving result...")
    
    try:
        output_file = os.path.join(output_dir, f"{pdf_name}_page_{page_num:04d}.md")
        os.makedirs(output_dir, exist_ok=True)
        
        # Add metadata comment
        method_label = {
            "pdfplumber": "pdfplumber",
            "mathpix": "Mathpix OCR",  # All pages processed with Mathpix
            "pdfplumber_fallback": f"pdfplumber fallback (Mathpix failed, {cid_count} CIDs)"
        }.get(processing_method, processing_method)
        
        logging.info(f"  → Writing {len(final_content)} chars to {output_file}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            # f.write(f"<!-- Page {page_num} of {pdf_name} | Processed with {method_label} -->\n\n")
            f.write(f"<!-- Page {page_num} of {pdf_name} -->\n\n")
            f.write(final_content)
        
        logging.info(f"  → File saved, marking progress...")
        
        # Mark as completed
        progress_mgr.mark_completed(pdf_name, page_num)
        
        # Log success with processing method
        logging.info(f"✓ {pdf_name} page {page_num} completed ({processing_method}, {cid_count} CIDs)")
        
        return True, f"Success ({processing_method})"
        
    except Exception as e:
        error_msg = f"Failed to save result: {str(e)}"
        logging.error(f"✗ {pdf_name} page {page_num}: {error_msg}")
        progress_mgr.mark_failed(pdf_name, page_num, error_msg)
        return False, error_msg

def merge_pages_to_single_file(output_dir: str, pdf_name: str, total_pages: int):
    """Merge all page files into a single output file with processing method indicators"""
    output_file = os.path.join(OUTPUT_DIR, f"{pdf_name}_mathpix.md")
    
    logging.info(f"Merging pages for {pdf_name} into {output_file}")
    
    mathpix_count = 0
    pdfplumber_count = 0
    missing_count = 0
    
    with open(output_file, 'w', encoding='utf-8') as outf:
        outf.write(f"# {pdf_name}\n\n")
        outf.write(f"Processed with Mathpix OCR API + pdfplumber fallback\n")
        outf.write(f"Total pages: {total_pages}\n")
        outf.write(f"Generated: {datetime.now().isoformat()}\n\n")
        outf.write("="*80 + "\n\n")
        
        for page_num in range(1, total_pages + 1):
            page_file = os.path.join(output_dir, f"{pdf_name}_page_{page_num:04d}.md")
            
            if os.path.exists(page_file):
                with open(page_file, 'r', encoding='utf-8') as inf:
                    content = inf.read()
                    
                    # Determine processing method from comment
                    if 'Processed with Mathpix' in content:
                        mathpix_count += 1
                        method_marker = "(Mathpix)"
                    elif 'Processed with pdfplumber' in content:
                        pdfplumber_count += 1
                        method_marker = "(pdfplumber)"
                    else:
                        method_marker = ""
                    
                    outf.write(f"\n--- Page {page_num} {method_marker} ---\n\n")
                    
                    # Write content (skip the HTML comment line)
                    lines = content.split('\n')
                    for line in lines:
                        if not line.startswith('<!--'):
                            outf.write(line + '\n')
                    outf.write("\n")
            else:
                missing_count += 1
                outf.write(f"\n--- Page {page_num} ---\n")
                outf.write(f"[ERROR: Page not processed]\n\n")
    
    # Summary
    logging.info(f"✓ Merged output saved to {output_file}")
    logging.info(f"  Processing summary:")
    logging.info(f"    - Mathpix: {mathpix_count} pages")
    logging.info(f"    - pdfplumber: {pdfplumber_count} pages")
    logging.info(f"    - Missing: {missing_count} pages")

def process_pdf(
    client: MathpixClient,
    pdf_path: str,
    progress_mgr: ProgressManager,
    page_range: Optional[str] = None
) -> Dict:
    """
    Process a complete PDF file
    
    Args:
        client: Mathpix client
        pdf_path: Path to PDF file
        progress_mgr: Progress manager
        page_range: Optional page range (e.g., "1-50,100-150")
    
    Returns:
        Processing statistics
    """
    pdf_name = Path(pdf_path).stem
    total_pages = get_pdf_page_count(pdf_path)
    
    if total_pages == 0:
        logging.error(f"Could not determine page count for {pdf_path}")
        return {'success': 0, 'failed': 0, 'skipped': 0}
    
    logging.info(f"\n{'='*80}")
    logging.info(f"Processing: {pdf_name}")
    logging.info(f"Total pages: {total_pages}")
    logging.info(f"{'='*80}\n")
    
    # Determine pages to process
    if page_range:
        pages_to_process = parse_page_range(page_range, total_pages)
        logging.info(f"Processing pages: {page_range} ({len(pages_to_process)} pages)")
    else:
        pages_to_process = list(range(1, total_pages + 1))
    
    # Create temporary output directory for individual pages
    temp_output_dir = os.path.join(OUTPUT_DIR, f"{pdf_name}_temp")
    
    # Process pages serially (changed from concurrent for CID-based strategy)
    success_count = 0
    failed_count = 0
    skipped_count = 0
    
    # Track processing method statistics
    method_stats = {
        'pdfplumber': 0,
        'mathpix': 0,
        'pdfplumber_fallback': 0
    }
    
    # Process pages serially with manual progress logging
    for i, page_num in enumerate(pages_to_process, 1):
        logging.info(f"\n--- Progress: {i}/{len(pages_to_process)} ---")
        
        try:
            success, message = process_single_page(
                client,
                pdf_path,
                pdf_name,
                page_num,
                temp_output_dir,
                progress_mgr
            )
            
            if success:
                if message == "Already completed":
                    skipped_count += 1
                else:
                    success_count += 1
                    # Track method
                    if "pdfplumber_fallback" in message:
                        method_stats['pdfplumber_fallback'] += 1
                    elif "mathpix" in message:
                        method_stats['mathpix'] += 1
                    elif "pdfplumber" in message:
                        method_stats['pdfplumber'] += 1
            else:
                failed_count += 1
        except Exception as e:
            logging.error(f"Exception processing page {page_num}: {e}")
            import traceback
            logging.error(traceback.format_exc())
            failed_count += 1
    
    # Merge pages into single file
    merge_pages_to_single_file(temp_output_dir, pdf_name, total_pages)
    
    # Print summary with method breakdown
    logging.info(f"\n{'='*80}")
    logging.info(f"Summary for {pdf_name}:")
    logging.info(f"  Total pages: {total_pages}")
    logging.info(f"  Processed: {len(pages_to_process)}")
    logging.info(f"  Success: {success_count}")
    logging.info(f"  Failed: {failed_count}")
    logging.info(f"  Skipped: {skipped_count}")
    logging.info(f"")
    logging.info(f"  Processing method breakdown:")
    logging.info(f"    - pdfplumber (low CID): {method_stats['pdfplumber']} pages")
    logging.info(f"    - Mathpix (high CID): {method_stats['mathpix']} pages")
    logging.info(f"    - pdfplumber fallback: {method_stats['pdfplumber_fallback']} pages")
    logging.info(f"{'='*80}\n")
    
    return {
        'success': success_count,
        'failed': failed_count,
        'skipped': skipped_count
    }

# ==================== Utility Functions ====================

def parse_page_range(range_str: str, total_pages: int) -> List[int]:
    """
    Parse page range string into list of page numbers
    
    Examples:
        "1-10" -> [1,2,3,4,5,6,7,8,9,10]
        "1-5,10,15-20" -> [1,2,3,4,5,10,15,16,17,18,19,20]
    """
    pages = set()
    
    for part in range_str.split(','):
        part = part.strip()
        if '-' in part:
            start, end = part.split('-')
            start = int(start.strip())
            end = int(end.strip())
            pages.update(range(start, min(end + 1, total_pages + 1)))
        else:
            page = int(part.strip())
            if 1 <= page <= total_pages:
                pages.add(page)
    
    return sorted(list(pages))

def estimate_cost(total_pages: int) -> Tuple[float, str]:
    """
    Estimate processing cost
    
    Returns:
        (cost, description)
    """
    if total_pages <= FREE_TIER_PAGES:
        return 0.0, f"Free (within {FREE_TIER_PAGES} page free tier)"
    else:
        pages_to_pay = total_pages - FREE_TIER_PAGES
        cost = pages_to_pay * COST_PER_PAGE
        return cost, f"${cost:.2f} (Free tier: {FREE_TIER_PAGES} pages, Paid: {pages_to_pay} pages @ ${COST_PER_PAGE}/page)"

def find_pdfs(input_dir: str, pdf_names: Optional[List[str]] = None) -> List[str]:
    """Find PDF files in input directory"""
    input_path = Path(input_dir)
    
    if not input_path.exists():
        logging.error(f"Input directory not found: {input_dir}")
        return []
    
    if pdf_names:
        # Specific PDFs requested
        pdfs = []
        for name in pdf_names:
            if not name.endswith('.pdf'):
                name += '.pdf'
            pdf_path = input_path / name
            if pdf_path.exists():
                pdfs.append(str(pdf_path))
            else:
                logging.warning(f"PDF not found: {name}")
        return pdfs
    else:
        # Find all PDFs
        return sorted([str(p) for p in input_path.glob('*.pdf')])

# ==================== Main Function ====================

def main():
    """Main processing function"""
    
    # Parse arguments
    parser = argparse.ArgumentParser(
        description='Batch process PDFs using Mathpix OCR API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all PDFs
  python mathpix_processor.py
  
  # Process specific PDFs
  python mathpix_processor.py --pdfs ts_138211v180200p,ts_138213v170100p
  
  # Process specific page ranges
  python mathpix_processor.py --pages 1-50,100-150
  
  # Estimate cost without processing
  python mathpix_processor.py --estimate-only
  
  # Resume from last progress
  python mathpix_processor.py --resume
        """
    )
    
    parser.add_argument('--pdfs', type=str, help='Comma-separated list of PDF names to process')
    parser.add_argument('--pages', type=str, help='Page range to process (e.g., "1-50,100-150")')
    parser.add_argument('--estimate-only', action='store_true', help='Only estimate cost without processing')
    parser.add_argument('--resume', action='store_true', help='Resume from last progress')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts')
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.verbose)
    
    logger.info("="*80)
    logger.info("Mathpix OCR Batch Processor")
    logger.info("="*80)
    
    # Check API credentials
    if MATHPIX_APP_ID == "your_app_id_here" or MATHPIX_APP_KEY == "your_app_key_here":
        logger.error("\n❌ Please configure your Mathpix API credentials in the script!")
        logger.error("Update MATHPIX_APP_ID and MATHPIX_APP_KEY at the top of the file.\n")
        sys.exit(1)
    
    # Find PDFs
    pdf_list = args.pdfs.split(',') if args.pdfs else None
    pdfs = find_pdfs(INPUT_DIR, pdf_list)
    
    if not pdfs:
        logger.error(f"No PDFs found in {INPUT_DIR}")
        sys.exit(1)
    
    logger.info(f"\nFound {len(pdfs)} PDF(s):")
    for pdf in pdfs:
        logger.info(f"  - {Path(pdf).name}")
    
    # Calculate total pages and cost
    total_pages = 0
    pdf_info = []
    
    for pdf_path in pdfs:
        page_count = get_pdf_page_count(pdf_path)
        total_pages += page_count
        pdf_info.append({
            'path': pdf_path,
            'name': Path(pdf_path).stem,
            'pages': page_count
        })
    
    logger.info(f"\nTotal pages: {total_pages}")
    
    # Estimate cost
    cost, cost_desc = estimate_cost(total_pages)
    logger.info(f"Estimated cost: {cost_desc}")
    
    if args.estimate_only:
        logger.info("\n✓ Cost estimation complete (--estimate-only mode)")
        sys.exit(0)
    
    # Confirm before processing
    if not args.yes:
        logger.info("\n" + "="*80)
        response = input(f"Continue with processing {total_pages} pages? (y/n): ")
        if response.lower() != 'y':
            logger.info("Aborted by user")
            sys.exit(0)
    
    # Initialize components
    logger.info("\nInitializing...")
    client = MathpixClient(MATHPIX_APP_ID, MATHPIX_APP_KEY)
    progress_mgr = ProgressManager(PROGRESS_FILE)
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Process PDFs
    start_time = time.time()
    total_stats = {'success': 0, 'failed': 0, 'skipped': 0}
    
    for info in pdf_info:
        stats = process_pdf(
            client,
            info['path'],
            progress_mgr,
            args.pages
        )
        
        for key in total_stats:
            total_stats[key] += stats.get(key, 0)
    
    # Final summary
    elapsed_time = time.time() - start_time
    
    logger.info("\n" + "="*80)
    logger.info("FINAL SUMMARY")
    logger.info("="*80)
    logger.info(f"Total PDFs processed: {len(pdfs)}")
    logger.info(f"Total pages: {total_pages}")
    logger.info(f"Successful: {total_stats['success']}")
    logger.info(f"Failed: {total_stats['failed']}")
    logger.info(f"Skipped: {total_stats['skipped']}")
    logger.info(f"Time elapsed: {elapsed_time/60:.1f} minutes")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info("="*80)
    
    if total_stats['failed'] > 0:
        logger.warning(f"\n  {total_stats['failed']} pages failed. Check log file for details.")
    else:
        logger.info("\n✓ All pages processed successfully!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("\n\n  Interrupted by user. Progress has been saved.")
        logging.info("Run with --resume to continue from where you left off.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"\n Fatal error: {e}", exc_info=True)
        sys.exit(1)