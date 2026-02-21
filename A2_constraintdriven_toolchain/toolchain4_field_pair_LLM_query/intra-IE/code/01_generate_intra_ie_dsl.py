#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced DSL Constraint Generation Tool for Intra-IE
Updated Version 4:
- Relaxed normative requirements (accept mathematical constraints)
- Aggressive evidence filtering (prioritize HIGH/MEDIUM, avoid VERY_LOW)
- Aligned with Inter-IE format (using field1/field2 in DSL)
"""

import os
import json
import glob
import re
import time
from openai import OpenAI
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps

# ============================================================================
# Configuration
# ============================================================================

API_KEY = "XXXXXXXXXXXXXXXX"  # Replace with your OpenAI API key
MODEL = "gpt-4o"

# Path Configuration
AGGREGATED_FILE = "../outputs/aggregated/aggregated_field_pairs.json"
ASN_DIR = "../TS38331ASN"
OUTPUT_DIR = "../outputs/intra-IE_DSL_results_gpt4o"
DIAGNOSIS_FILE = "../diagnosis/intra_ie_diagnosis_gpt4o.txt"

# Evidence Sampling Configuration
MAX_EVIDENCES_PER_PAIR = 12
EVIDENCE_FILTER_MODE = "aggressive"  # "aggressive" | "moderate" | "off"
MIN_HIGH_MEDIUM_COUNT = 3  # Minimum HIGH/MEDIUM evidences to trigger aggressive filtering

# Concurrent Configuration
MAX_CONCURRENT_REQUESTS = 8
ENABLE_RETRY = True
MAX_RETRIES = 3
RETRY_DELAY = 2

# API Configuration (consistent with inter-IE)
# temperature=0.0: Deterministic output for reproducibility
# seed=42: Ensures consistent results across runs (best-effort by OpenAI)
API_TEMPERATURE = 0.0
API_SEED = 42

# ============================================================================
# Prompt template - UPDATED v4: Clear DSL format rules
# ============================================================================

PROMPT_TEMPLATE = """You are a 3GPP specification expert and protocol testing engineer.

Goal: Decide if there is a VALID semantic constraint of type {{ValueDependency, RangeAlignment}} between two fields WITHIN THE SAME IE for 5G RRC message mutation. If not strictly supported by evidence, output NO_RULE.

In your DSL output, use "field1" and "field2" as placeholders (not the actual field names like "{field1}" or "{field2}").

Inputs:
- IE name: {ie_name}
- ASN.1 definition (exact): 
{asn_content}
- Target fields (two, in the SAME IE): 
  * field1 = {field1} (IDs: {field1_ids})
  * field2 = {field2} (IDs: {field2_ids})
- Evidence snippets (verbatim from 3GPP): 
{evidence_text}

Strict Rules:
1) EVIDENCE-ONLY. Use ONLY the ASN.1 and the provided snippets. No external memory.

2) NORMATIVE CHECK. Accept constraints backed by:
   - Explicit normative wording (shall/shall not/must/only if)
   - Mathematical/logical relations with clear technical meaning (>=, <=, ==, !=)
   - Conditional statements establishing mandatory relationships
   
   Mathematical expressions and logical relations are considered normative when they establish concrete constraints on field values.
   If wording is "should", mark advisory=true and still return NO_RULE unless a non-advisory relation also exists.

3) SAME-IE SCOPE. If the two fields are not both inside the given IE instance (or the relation is merely definitional/tautological like "belongs to its own config"), output NO_RULE.

4) DSL FORMAT RULES - CRITICAL:
   
   A) SIMPLE UNCONDITIONAL CONSTRAINTS → Use atomic constraint directly (NO IMPLIES wrapper):
      When the constraint is a direct relationship without real conditional logic:
      
      ✓ CORRECT:
        - GE(field2, field1 - 1)              # field2 >= field1 - 1
        - LE(field1 + field2, 14)             # field1 + field2 <= 14
        - EQ(field1, field2)                  # field1 == field2
        - MOD(field1, field2) == 0            # field1 % field2 == 0
      
      ✗ WRONG - DO NOT DO THIS:
        - IMPLIES(GT(field2, field1-1), GE(field2, 0))     # Putting constraint in condition position
        - IMPLIES(GE(field2, field1), ...)                  # Range constraint as precondition
        - IMPLIES(field1 present, GE(field2, field1-1))    # Unnecessary generic wrapper
   
   B) CONDITIONAL CONSTRAINTS → Use IMPLIES form (ONLY when there is genuine conditional logic):
      Use IMPLIES only when evidence shows explicit IF-THEN relationship:
      
      ✓ CORRECT:
        - IMPLIES(EQ(field1, 'nonCodebook'), EQ(field2, 1))  # IF field1='nonCodebook' THEN field2=1
        - IMPLIES(IN(field1, {{2, 3}}), GT(field2, field1))  # IF field1 in {{2,3}} THEN field2 > field1
        - IMPLIES(r17 enabled, LE(field2, 100))              # IF version=r17 THEN constraint applies
   
   C) VALID PRECONDITIONS (for IMPLIES only):
      - Field value conditions: EQ(field1, 'value'), IN(field1, {{values}})
      - Field presence: field1 present, field2 present
      - Version/feature flags: r17 enabled, featureX configured
      
   D) DECISION GUIDE:
      - Evidence says "field2 >= field1 - 1" with no condition → Use: GE(field2, field1 - 1)
      - Evidence says "IF field1='x' THEN field2=y" → Use: IMPLIES(EQ(field1, 'x'), EQ(field2, y))
      - Evidence says "field2 must be..." with no IF → Use simple atom, NOT IMPLIES

5) MACHINE-CHECKABLE. The DSL must use the canonical grammar below and be directly checkable (no vague words). Use field1/field2 as placeholders.

6) UNITS & ENUMS. Normalize any required units or enum-to-number mapping explicitly (e.g., n1→1, n2→2). If unknown, output NO_RULE.

7) VERSION/SCOPE GUARDS. If the rule only applies under specific releases/options, include them in `preconditions`.

8) LOGICAL CONSISTENCY. Check for contradictions. If logically impossible, output NO_RULE.

Allowed Types and Canonical DSL Grammar (using field1/field2):
- ValueDependency:
  - EQ(field1, field2) | NE(field1, field2)
  - EQ(field1, concrete_value) | NE(field1, concrete_value)
  - MAP(field1, {{a->b, c->d, ...}})
  - MOD(field1, field2)==0
  - IN(field1, {{v1,v2,...}})
  - IMPLIES(COND, ATOM) where COND is a specific value/presence condition; ATOM from above list
  
- RangeAlignment:
  - LT(field1, field2) | LE(field1, field2) | GT(field1, field2) | GE(field1, field2)
  - LT(field2, field1 + k) | LE(field1 + field2, CONST) | GE(field2, field1 - k)
  - WITHIN(field1, [min,max])
  - IMPLIES(COND, ATOM) where COND is a specific condition; ATOM from above list

Output JSON ONLY:
{{
  "result": "DSL | NO_RULE",
  "type": "ValueDependency | RangeAlignment",
  "dsl": "<atomic_constraint> or IMPLIES(<specific_condition>, <constraint_atom>) using field1/field2",
  "preconditions": ["..."],
  "predicate": "..." ,
  "advisory": false,
  "examples": {{
    "valid": ["...concrete assignment..."],
    "invalid": ["...concrete assignment..."]
  }},
  "notes": "1-2 lines explaining reasoning or edge-guards.",
  "version_tags": ["r16","r17"]
}}

Decision rules for NO_RULE:
- Evidence lacks both target fields or doesn't relate them.
- Evidence is purely definitional (e.g., 'belongs to' the same object) or default-only.
- Only 'should' guidance with no non-advisory constraint.
- Requires external assumptions (units/enums/tables not present).
- Contains abstract variables (X, Y, Z) instead of concrete values.
- Logically contradictory or impossible.

Examples of CORRECT DSL (using field1/field2):

GROUP A - Simple atomic constraints (NO IMPLIES):
1. GE(field2, field1 - 1)              # Direct: field2 >= field1 - 1
2. LE(field1 + field2, 14)             # Direct: field1 + field2 <= 14  
3. EQ(field1, field2)                  # Direct: field1 == field2
4. MOD(field1, field2) == 0            # Direct: field1 % field2 == 0
5. GT(field2, field1)                  # Direct: field2 > field1

GROUP B - Conditional constraints (WITH IMPLIES):
1. IMPLIES(EQ(field1, 'nonCodebook'), EQ(field2, 1))
2. IMPLIES(IN(field1, {{2, 3}}), GT(field2, field1))
3. IMPLIES(r17 enabled, LE(field2, 100))

Examples of WRONG DSL (DO NOT OUTPUT THESE):
✗ IMPLIES(GT(field2, field1 - 1), GE(field2, 0))           # Constraint in wrong place
✗ IMPLIES(GE(field2, field1), ...)                          # Range as precondition  
✗ IMPLIES(field1 present, GE(field2, field1 - 1))          # Unnecessary wrapper for simple constraint
✗ IMPLIES(EQ(usage, 'x'), EQ(nrofPorts, 1))                # Using actual field names instead of field1/field2
✗ IMPLIES(EQ(field1, X), EQ(field2, Y))                    # Using variables X, Y"""

# ============================================================================
# Utility functions
# ============================================================================

def initialize_directories():
    """Create the necessary directories"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DIAGNOSIS_FILE), exist_ok=True)
    
def log_diagnosis(message):
    """Record diagnostic information"""
    with open(DIAGNOSIS_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now()}] {message}\n")

def parse_source_file_to_citation(source_file):
    """Parse citation from source_file"""
    if not source_file:
        return None
    
    match = re.search(r'ts_1(\d{{2}})(\d{{3,4}})v', source_file)
    if match:
        series = match.group(1)
        number = match.group(2)
        doc_number = f"{series}.{number}"
        doc_name = f"3GPP TS {doc_number}"
        return {"doc": doc_name}
    
    log_diagnosis(f"Failed to parse source file name: {source_file}")
    return None

def normalize_name(name):
    """Standardized name for matching"""
    return name.lower().replace('-', '').replace('_', '')

def find_asn_file(ie_name):
    """Find the corresponding ASN.1 file"""
    normalized_ie = normalize_name(ie_name)
    
    asn_files = glob.glob(os.path.join(ASN_DIR, "*.asn1"))
    
    for asn_file in asn_files:
        filename = os.path.basename(asn_file)
        normalized_filename = normalize_name(os.path.splitext(filename)[0])
        
        if normalized_ie in normalized_filename or normalized_filename in normalized_ie:
            return asn_file
    
    return None

def read_asn_content(asn_file):
    """Read ASN.1 file content"""
    try:
        with open(asn_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        log_diagnosis(f"Error reading ASN file {asn_file}: {str(e)}")
        return None

def sample_evidences_smart(evidences, max_count=12, filter_mode=EVIDENCE_FILTER_MODE):
    """
    Smart Evidence Sampling with Aggressive Filtering
    
    Strategies:
    - "aggressive": Prioritize HIGH/MEDIUM, avoid VERY_LOW unless no choice
    - "moderate": Use HIGH/MEDIUM/LOW, minimize VERY_LOW
    - "off": No filtering, original behavior
    """
    if len(evidences) <= max_count and filter_mode == "off":
        return evidences
    
    # Group by confidence
    high_medium = [e for e in evidences if e.get('confidence') in ['HIGH', 'MEDIUM']]
    low = [e for e in evidences if e.get('confidence') == 'LOW']
    very_low = [e for e in evidences if e.get('confidence') in ['VERY_LOW', 'UNKNOWN']]
    
    # Decision logic based on mode
    if filter_mode == "aggressive":
        if len(high_medium) >= MIN_HIGH_MEDIUM_COUNT:
            # Sufficient high-quality evidences, use only these
            candidates = high_medium
            log_diagnosis(f"Aggressive filter: Using {len(high_medium)} HIGH/MEDIUM evidences (avoiding VERY_LOW)")
        elif len(high_medium) >= 1:
            # Have some HIGH/MEDIUM, use only these even if < MIN_HIGH_MEDIUM_COUNT
            # Better to have fewer high-quality evidences than mix in VERY_LOW
            candidates = high_medium
            log_diagnosis(f"Aggressive filter: Using {len(high_medium)} HIGH/MEDIUM evidences (insufficient but keeping quality)")
        elif len(high_medium) + len(low) >= 3:
            # No HIGH/MEDIUM, use LOW as fallback
            candidates = high_medium + low
            log_diagnosis(f"Aggressive filter: Using {len(high_medium)} H/M + {len(low)} LOW (no HIGH/MEDIUM available)")
        else:
            # Last resort: use all
            candidates = evidences
            log_diagnosis(f"Aggressive filter: Using all {len(evidences)} evidences (insufficient quality evidences)")
    
    elif filter_mode == "moderate":
        if len(high_medium) + len(low) >= 3:
            # Use HIGH/MEDIUM/LOW, minimize VERY_LOW
            candidates = high_medium + low
            log_diagnosis(f"Moderate filter: Using {len(high_medium)} H/M + {len(low)} LOW")
        else:
            # Not enough, use all
            candidates = evidences
            log_diagnosis(f"Moderate filter: Using all {len(evidences)} evidences")
    
    else:  # "off"
        candidates = evidences
    
    # Sample by diversity within candidates
    return sample_by_diversity(candidates, max_count)

def sample_by_diversity(evidences, max_count):
    """Sample evidences with section diversity"""
    confidence_priority = {'HIGH': 4, 'MEDIUM': 3, 'LOW': 2, 'VERY_LOW': 1, 'UNKNOWN': 0}
    
    # Sort by confidence
    sorted_evidences = sorted(
        evidences,
        key=lambda e: confidence_priority.get(e.get('confidence', 'UNKNOWN'), 0),
        reverse=True
    )
    
    sampled = []
    seen_sections = set()
    
    # Round 1: Different sections (maximize diversity)
    for evidence in sorted_evidences:
        section = evidence.get('section_number', 'N/A')
        if section not in seen_sections:
            sampled.append(evidence)
            seen_sections.add(section)
            if len(sampled) >= max_count:
                break
    
    # Round 2: Fill up to max_count (allow same sections)
    if len(sampled) < max_count:
        for evidence in sorted_evidences:
            if evidence not in sampled:
                sampled.append(evidence)
                if len(sampled) >= max_count:
                    break
    
    return sampled

def estimate_prompt_tokens(text):
    """Rough estimate of token count"""
    return len(text) // 4

def format_evidences_for_prompt(evidences):
    """Format multiple evidence into prompt text"""
    formatted_blocks = []
    
    for idx, evidence in enumerate(evidences, 1):
        section = evidence.get('section_number', 'N/A')
        title = evidence.get('section_title', 'Unknown')
        source = evidence.get('source_file', 'Unknown')
        confidence = evidence.get('confidence', 'UNKNOWN')
        sentence = evidence.get('original_sentence', '')
        
        block = f"""---EVIDENCE #{idx}---
[Source: {source} | Section {section}: {title} | Confidence: {confidence}]
{sentence}"""
        formatted_blocks.append(block)
    
    return "\n\n".join(formatted_blocks)

def retry_on_failure(max_retries=3, delay=2):
    """Retry Decorator"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_str = str(e)
                    
                    if 'rate_limit' in error_str.lower() or '429' in error_str:
                        wait_time = delay * (2 ** attempt)
                        log_diagnosis(f"Rate limit hit, waiting {wait_time}s before retry {attempt+1}/{max_retries}")
                        time.sleep(wait_time)
                    elif 'context_length_exceeded' in error_str.lower():
                        log_diagnosis(f"Context length exceeded, skipping retry: {error_str}")
                        return None
                    else:
                        if attempt < max_retries - 1:
                            time.sleep(delay)
            
            log_diagnosis(f"All {max_retries} retries failed: {last_exception}")
            return None
        return wrapper
    return decorator

@retry_on_failure(max_retries=MAX_RETRIES if ENABLE_RETRY else 1, delay=RETRY_DELAY)
def call_chatgpt_api(prompt):
    """Call ChatGPT API and parse JSON response"""
    try:
        client = OpenAI(api_key=API_KEY)
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a 3GPP specification expert. Always respond with valid JSON using the exact format specified."},
                {"role": "user", "content": prompt}
            ],
            temperature=API_TEMPERATURE,  # Consistent with inter-IE configuration
            seed=API_SEED,                # Consistent with inter-IE configuration for reproducibility
            max_tokens=1000
        )
        
        response_text = response.choices[0].message.content.strip()
        
        try:
            if response_text.startswith('```json'):
                response_text = response_text.strip('```json').strip('```').strip()
            elif response_text.startswith('```'):
                response_text = response_text.strip('```').strip()
            
            result = json.loads(response_text)
            return result
        except json.JSONDecodeError as e:
            log_diagnosis(f"JSON parse error: {str(e)}, raw response: {response_text}")
            return None
            
    except Exception as e:
        log_diagnosis(f"API call error: {str(e)}")
        raise

def convert_field_ids_to_inter_ie_format(field_ids):
    """
    Convert the field_ids format of Intra-IE to Inter-IE format
    
    Input (Intra-IE):
    [
        [214, 215],  # all IDs for field1
        [210, 219]   # all IDs for field2
    ]
    
    Output (Inter-IE):
    {
        "field1_all": [214, 215],
        "field2_all": [210, 219],
        "actual_pairs": [
            [[214, 215], [210, 219]]
        ]
    }
    """
    if not field_ids or len(field_ids) < 2:
        return {
            "field1_all": [],
            "field2_all": [],
            "actual_pairs": []
        }
    
    field1_ids = field_ids[0] if isinstance(field_ids[0], list) else [field_ids[0]]
    field2_ids = field_ids[1] if isinstance(field_ids[1], list) else [field_ids[1]]
    
    return {
        "field1_all": field1_ids,
        "field2_all": field2_ids,
        "actual_pairs": [
            [field1_ids, field2_ids]
        ]
    }

def save_dsl_file(ie_name, field1, field2, field_ids, api_response, evidences, all_citations, original_evidence_count=None):
    """Save JSON File - Align with Inter-IE Format"""
    ie_dir = os.path.join(OUTPUT_DIR, ie_name)
    os.makedirs(ie_dir, exist_ok=True)
    
    filename = f"{ie_name}_{field1}_{field2}.json"
    filepath = os.path.join(ie_dir, filename)
    
    try:
        evidence_text = "\n---\n".join([e.get('original_sentence', '') for e in evidences])
        
        if original_evidence_count is None:
            original_evidence_count = len(evidences)
        
        evidence_info = {
            "used_count": len(evidences),
            "original_count": original_evidence_count,
            "sampled": original_evidence_count > len(evidences),
            "filter_mode": EVIDENCE_FILTER_MODE
        }
        
        # Convert field_ids format (align with Inter-IE)
        formatted_field_ids = convert_field_ids_to_inter_ie_format(field_ids)
        
        if api_response and api_response.get("result") == "DSL":
            content = {
                "dsl_rule": api_response.get("dsl"),
                "constraint_type": api_response.get("type"),
                "has_valid_rule": True,
                "field_ids": formatted_field_ids,
                "predicate": api_response.get("predicate"),
                "preconditions": api_response.get("preconditions", []),
                "advisory": api_response.get("advisory", False),
                "citations": all_citations,
                "examples": api_response.get("examples", {"valid": [], "invalid": []}),
                "notes": api_response.get("notes", ""),
                "version_tags": api_response.get("version_tags", []),
                "meta": {
                    "ie_name": ie_name,
                    "field1": field1,
                    "field2": field2,
                    "is_intra_ie": True,
                    "evidence_info": evidence_info,
                    "all_sources": list(set(e.get('source_file', '') for e in evidences)),
                    "all_sections": list(set(e.get('section_number', '') for e in evidences)),
                    "best_confidence": evidences[0].get('confidence', 'UNKNOWN') if evidences else 'UNKNOWN',
                    "evidence": evidence_text,
                    "generated_at": datetime.now().isoformat(),
                    "model": MODEL,
                    "full_api_response": api_response
                }
            }
        else:
            content = {
                "dsl_rule": None,
                "constraint_type": None,
                "has_valid_rule": False,
                "field_ids": formatted_field_ids,
                "reason": "NO_RULE - insufficient evidence or no valid constraint found",
                "notes": api_response.get("notes", "") if api_response else "API call failed",
                "advisory": api_response.get("advisory", False) if api_response else False,
                "citations": all_citations,
                "meta": {
                    "ie_name": ie_name,
                    "field1": field1,
                    "field2": field2,
                    "is_intra_ie": True,
                    "evidence_info": evidence_info,
                    "all_sources": list(set(e.get('source_file', '') for e in evidences)),
                    "all_sections": list(set(e.get('section_number', '') for e in evidences)),
                    "best_confidence": evidences[0].get('confidence', 'UNKNOWN') if evidences else 'UNKNOWN',
                    "evidence": evidence_text,
                    "generated_at": datetime.now().isoformat(),
                    "model": MODEL,
                    "full_api_response": api_response
                }
            }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(content, f, indent=2, ensure_ascii=False)
        
        return filepath
        
    except Exception as e:
        log_diagnosis(f"Error saving DSL file {filepath}: {str(e)}")
        return filepath

def process_field_pair(field_pair_key, field_pair_data, asn_content_cache):
    """Process single field pair - concurrency-friendly version"""
    fields = field_pair_data['fields']
    field_ids = field_pair_data['field_ids']
    evidences = field_pair_data['evidences']
    ie_names = field_pair_data.get('ie_names', [])
    
    field1, field2 = fields
    
    # Extract field IDs (for prompt)
    field1_ids = field_ids[0] if len(field_ids) > 0 else []
    field2_ids = field_ids[1] if len(field_ids) > 1 else []
    
    field1_ids_str = str(field1_ids)
    field2_ids_str = str(field2_ids)
    
    ie_name = ie_names[0] if ie_names else "UnknownIE"
    
    print(f"    🔄 {field1} ↔ {field2}", end="")
    
    # Smart Sampling with Aggressive Filtering
    original_count = len(evidences)
    if len(evidences) > MAX_EVIDENCES_PER_PAIR or EVIDENCE_FILTER_MODE != "off":
        evidences = sample_evidences_smart(evidences, MAX_EVIDENCES_PER_PAIR, EVIDENCE_FILTER_MODE)
        if len(evidences) < original_count:
            print(f" (filtered {len(evidences)}/{original_count})", end="")
    
    # Extract citations
    all_citations = []
    seen_docs = set()
    for evidence in evidences:
        source_file = evidence.get('source_file', '')
        if source_file:
            citation = parse_source_file_to_citation(source_file)
            if citation and citation['doc'] not in seen_docs:
                all_citations.append(citation)
                seen_docs.add(citation['doc'])
    
    # Retrieve or read ASN.1 content
    if ie_name not in asn_content_cache:
        asn_file = find_asn_file(ie_name)
        if asn_file:
            asn_content_cache[ie_name] = read_asn_content(asn_file)
        else:
            asn_content_cache[ie_name] = "ASN.1 definition not found"
            log_diagnosis(f"Cannot find ASN file for IE: {ie_name}")
    
    asn_content = asn_content_cache[ie_name]
    
    # Format evidence
    evidence_text = format_evidences_for_prompt(evidences)
    
    # Build prompt (including field IDs)
    prompt = PROMPT_TEMPLATE.format(
        ie_name=ie_name,
        asn_content=asn_content,
        field1=field1,
        field1_ids=field1_ids_str,
        field2=field2,
        field2_ids=field2_ids_str,
        evidence_text=evidence_text
    )
    
    # Estimate token count
    estimated_tokens = estimate_prompt_tokens(prompt)
    if estimated_tokens > 7000:
        print(f" {estimated_tokens}tok", end="")
        log_diagnosis(f"Large prompt for {ie_name}: {field1} ↔ {field2} - estimated {estimated_tokens} tokens")
    
    # Call API
    api_response = call_chatgpt_api(prompt)
    
    if api_response:
        # Save results (pass in original field_ids)
        filepath = save_dsl_file(ie_name, field1, field2, field_ids, 
                                 api_response, evidences, all_citations, 
                                 original_evidence_count=original_count)
        
        if api_response.get("result") == "DSL":
            constraint_type = api_response.get("type", "Unknown")
            print(f" →  {constraint_type}")
        else:
            print(f" → NO_RULE")
        
        return filepath, api_response.get("result") == "DSL"
    else:
        print(f" → FAILED")
        log_diagnosis(f"Failed to get response for {ie_name}: {field1} ↔ {field2}")
        return None, False

def process_aggregated_file(aggregated_path):
    """Processing Aggregate Files - Concurrent Version"""
    print(f"\nLoading aggregated data from: {aggregated_path}")
    
    try:
        with open(aggregated_path, 'r', encoding='utf-8') as f:
            aggregated_data = json.load(f)
    except Exception as e:
        print(f" Error loading aggregated file: {e}")
        return
    
    summary = aggregated_data.get('summary', {})
    field_pairs = aggregated_data.get('field_pairs', {})
    
    print(f"\n{'='*60}")
    print("Aggregated Data Summary")
    print(f"{'='*60}")
    print(f"Total constraint entries: {summary.get('total_constraint_entries', 0)}")
    print(f"Unique field pairs: {summary.get('unique_field_pairs', 0)}")
    print(f"Reduction rate: {summary.get('reduction_rate', 'N/A')}")
    
    print(f"\n{'='*60}")
    print(f"Processing {len(field_pairs)} unique field pairs...")
    print(f"Evidence filter mode: {EVIDENCE_FILTER_MODE}")
    print(f"Min HIGH/MEDIUM count: {MIN_HIGH_MEDIUM_COUNT}")
    print(f"Concurrency: {MAX_CONCURRENT_REQUESTS} parallel requests")
    print(f"Retry enabled: {ENABLE_RETRY}")
    print(f"{'='*60}")
    
    # Preload ASN.1 content cache
    asn_content_cache = {}
    
    # Prepare all tasks
    tasks = list(field_pairs.items())
    
    # Statistics
    success_count = 0
    dsl_count = 0
    no_rule_count = 0
    failed_count = 0
    
    # Concurrent Processing
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
        future_to_task = {
            executor.submit(
                process_field_pair, 
                field_pair_key, 
                field_pair_data, 
                asn_content_cache
            ): (idx, field_pair_key, field_pair_data)
            for idx, (field_pair_key, field_pair_data) in enumerate(tasks, 1)
        }
        
        for future in as_completed(future_to_task):
            idx, field_pair_key, field_pair_data = future_to_task[future]
            
            elapsed = time.time() - start_time
            progress_pct = (idx / len(tasks)) * 100
            avg_time_per_task = elapsed / idx if idx > 0 else 0
            eta_seconds = avg_time_per_task * (len(tasks) - idx)
            
            print(f"\n[{idx}/{len(tasks)}] ({progress_pct:.1f}%) | "
                  f"Elapsed: {elapsed/60:.1f}min | "
                  f"ETA: {eta_seconds/60:.1f}min")
            
            try:
                result, has_dsl = future.result()
                
                if result:
                    success_count += 1
                    if has_dsl:
                        dsl_count += 1
                    else:
                        no_rule_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                failed_count += 1
                fields = field_pair_data.get('fields', ['unknown', 'unknown'])
                print(f"     Task failed: {fields[0]} ↔ {fields[1]}")
                log_diagnosis(f"Task execution error: {e}")
    
    total_time = time.time() - start_time
    
    print(f"\n{'='*60}")
    print("Processing Results")
    print(f"{'='*60}")
    print(f" Total time: {total_time/60:.1f} minutes")
    print(f"⚡ Average: {total_time/len(tasks):.1f}s per field pair")
    print(f" Total processed: {success_count}/{len(field_pairs)}")
    print(f"   Valid DSL rules: {dsl_count}")
    print(f"   No rules found: {no_rule_count}")
    print(f"   Failed: {failed_count}")
    if success_count > 0:
        print(f"   DSL Success rate: {dsl_count/success_count*100:.1f}%")

def generate_summary_report():
    """Generate summary report"""
    print("\nGenerating summary report...")
    
    summary = {
        "generation_time": datetime.now().isoformat(),
        "model": MODEL,
        "evidence_filter_mode": EVIDENCE_FILTER_MODE,
        "min_high_medium_count": MIN_HIGH_MEDIUM_COUNT,
        "total_files": 0,
        "valid_dsl_rules": 0,
        "no_rule_cases": 0,
        "advisory_rules": 0,
        "constraint_type_stats": {},
        "version_tag_stats": {},
        "by_ie": {}
    }
    
    for ie_dir in os.listdir(OUTPUT_DIR):
        if ie_dir == 'summary.json':
            continue
            
        ie_path = os.path.join(OUTPUT_DIR, ie_dir)
        if os.path.isdir(ie_path):
            json_files = glob.glob(os.path.join(ie_path, "*.json"))
            
            ie_stats = {
                "total_files": len(json_files),
                "valid_rules": 0,
                "no_rules": 0,
                "advisory_rules": 0,
                "constraint_types": {},
                "version_tags": {}
            }
            
            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        content = json.load(f)
                        if content.get("has_valid_rule", False):
                            ie_stats["valid_rules"] += 1
                            summary["valid_dsl_rules"] += 1
                            
                            if content.get("advisory", False):
                                ie_stats["advisory_rules"] += 1
                                summary["advisory_rules"] += 1
                            
                            constraint_type = content.get("constraint_type", "Unknown")
                            ie_stats["constraint_types"][constraint_type] = ie_stats["constraint_types"].get(constraint_type, 0) + 1
                            summary["constraint_type_stats"][constraint_type] = summary["constraint_type_stats"].get(constraint_type, 0) + 1
                            
                            version_tags = content.get("version_tags", [])
                            for tag in version_tags:
                                ie_stats["version_tags"][tag] = ie_stats["version_tags"].get(tag, 0) + 1
                                summary["version_tag_stats"][tag] = summary["version_tag_stats"].get(tag, 0) + 1
                        else:
                            ie_stats["no_rules"] += 1
                            summary["no_rule_cases"] += 1
                except Exception as e:
                    log_diagnosis(f"Error processing summary for {json_file}: {str(e)}")
                    pass
            
            summary["by_ie"][ie_dir] = ie_stats
            summary["total_files"] += len(json_files)
    
    summary_path = os.path.join(OUTPUT_DIR, "summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    
    print(f"  Total files processed: {summary['total_files']}")
    print(f"  Valid DSL rules: {summary['valid_dsl_rules']}")
    if summary['advisory_rules'] > 0:
        print(f"  Advisory rules: {summary['advisory_rules']}")
    print(f"  No rule cases: {summary['no_rule_cases']}")
    print(f"  Success rate: {summary['valid_dsl_rules']/max(summary['total_files'],1)*100:.1f}%")
    
    if summary['constraint_type_stats']:
        print(f"  Constraint types:")
        for ctype, count in summary['constraint_type_stats'].items():
            print(f"    - {ctype}: {count}")
    
    if summary['version_tag_stats']:
        print(f"  Version tags found:")
        for tag, count in summary['version_tag_stats'].items():
            print(f"    - {tag}: {count}")
    
    print(f"  Summary saved to: {summary_path}")
    return summary

def main():
    """main function"""
    print("="*60)
    print(" INTRA-IE DSL GENERATION v4")
    print(f"Model: {MODEL} | Format: field1/field2")
    print(f"API Config: temperature={API_TEMPERATURE}, seed={API_SEED}")
    print(f"Evidence Filter: {EVIDENCE_FILTER_MODE} (min H/M: {MIN_HIGH_MEDIUM_COUNT})")
    print("="*60)
    
    initialize_directories()
    open(DIAGNOSIS_FILE, 'w').close()
    
    if not os.path.exists(AGGREGATED_FILE):
        print(f"\n Aggregated file not found: {AGGREGATED_FILE}")
        print(f"Please run aggregate_intra_ie_constraints.py first!")
        return
    
    start_time = datetime.now()
    
    process_aggregated_file(AGGREGATED_FILE)
    
    summary = generate_summary_report()
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    print("\n" + "="*60)
    print(" PROCESSING COMPLETED!")
    print(f" Total time: {duration}")
    print(f" DSL Rules generated: {summary.get('valid_dsl_rules', 0)}")
    if summary.get('advisory_rules', 0) > 0:
        print(f" Advisory rules: {summary.get('advisory_rules', 0)}")
    print(f" Results saved in: {OUTPUT_DIR}")
    print(f" Diagnosis log: {DIAGNOSIS_FILE}")
    print("="*60)

if __name__ == "__main__":
    main()