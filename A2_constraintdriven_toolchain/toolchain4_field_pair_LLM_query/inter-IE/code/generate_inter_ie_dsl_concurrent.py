#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inter-IE DSL Generation - Based on Intra-IE Design
Cross-IE Constraint DSL Generator - Based on Intra-IE Design

- Same DSL syntax specification
- Same output format
- Same constraint type system
- Only adjust special scenarios across IE
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
from collections import Counter
from typing import Dict, List, Tuple, Optional
import argparse

# ============================================================================
# Configuration
# ============================================================================

API_KEY = "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"   # 👈 Enter your API Key

if API_KEY == "YOUR_API_KEY_HERE" or not API_KEY:
    API_KEY = os.getenv("OPENAI_API_KEY")

MODEL = "gpt-4o"

# Path Configuration
AGGREGATED_FILE = "../output/inter_ie_aggregated/aggregated_inter_ie_field_pairs.json"
OUTPUT_DIR = "../output/inter_ie_dsl_rules_gpt4o"
CHECKPOINT_FILE = "../output/inter_ie_dsl_rules_gpt4o/checkpoint.json"
DIAGNOSIS_FILE = "../diagnosis/inter_ie_diagnosis.txt"

# Evidence sampling configuration (using smart strategy: prioritize high confidence + ensure chapter diversity)
MAX_EVIDENCES_PER_PAIR = 12

# Concurrency Configuration
MAX_CONCURRENT_REQUESTS = 8
ENABLE_RETRY = True
MAX_RETRIES = 3
RETRY_DELAY = 2

# Filter configuration (no filtering by default, processes all field pairs)
FILTER_STRATEGY = "none"  # none/conservative/balanced/aggressive
MIN_EVIDENCE_COUNT = 5  # Only effective under balanced/conservative strategies

# Debug Configuration
DEBUG_MODE = False
VERBOSE = True
DRY_RUN = False

# ============================================================================
# Prompt Template - Based on Intra-IE design, adjusted to Inter-IE
# ============================================================================

PROMPT_TEMPLATE = """You are a 3GPP specification expert and protocol testing engineer.

Goal: Decide if there is a VALID semantic constraint of type {{CrossReference, ValueDependency, RangeAlignment, Association, Conditional}} between two fields from DIFFERENT IEs for 5G RRC message mutation. If not strictly supported by evidence, output NO_RULE.

CRITICAL: This is INTER-IE constraint. The two fields come from DIFFERENT Information Elements.

Inputs:
- IE Pair: {ie1} ↔ {ie2}
- Target fields (from DIFFERENT IEs): 
  - field1 = {field1} (from {ie1})
  - field2 = {field2} (from {ie2})
- Evidence snippets (verbatim from 3GPP): 
{evidence_text}

## CRITICAL REQUIREMENT
This is an INTER-IE constraint. The constraint MUST relate field1 (from {ie1}) to field2 (from {ie2}).
If evidence only describes single-IE behavior → NO_RULE

Strict Rules:
1) EVIDENCE-ONLY. Use ONLY the provided snippets. No external memory.
2) NORMATIVE CHECK. Accept only constraints backed by explicit normative wording (shall/shall not/only/only if/must) OR explicit math/table relations. If wording is "should", mark advisory=true and still return NO_RULE unless a non-advisory relation also exists.
3) INTER-IE SCOPE. The constraint MUST relate field1 (from {ie1}) to field2 (from {ie2}). If evidence only describes single IE behavior, output NO_RULE.
4) DIRECTION & TRIGGER. Identify the correct trigger condition(s) and avoid reversing implication.
5) MACHINE-CHECKABLE. The DSL must use the canonical grammar below and be directly checkable (no vague words).
6) UNITS & ENUMS. Normalize any required units or enum-to-number mapping explicitly (e.g., n1→1, n2→2). If unknown, output NO_RULE.
7) VERSION/SCOPE GUARDS. If the rule only applies under specific releases/options, include them in `preconditions`.
8) LOGICAL CONSISTENCY 
- Check for contradictions before outputting DSL
- Verify constraint is logically feasible
- If impossible or contradictory → NO_RULE

Allowed Types and Canonical DSL Grammar:

For Inter-IE constraints, use field1 and field2 to refer to the two fields:

- CrossReference (ID/reference matching):
  - MATCH(field1, field2)          // IDs must match
  - EQ(field1, field2)              // Values must be equal
  
- ValueDependency (value determines valid values):
  - IMPLIES(EQ(field1, value), EQ(field2, value))
  - IMPLIES(IN(field1, {{v1,v2}}), IN(field2, {{v1,v2}}))
  - MAP(field1, field2, {{a->b, c->d}})
  
- RangeAlignment (coordinated ranges):
  - IMPLIES(EQ(field1, X), AND(GE(field2, min), LE(field2, max)))
  - LT(field1, field2) | LE(field1, field2) | GT(field1, field2) | GE(field1, field2)
  
- Association (logical association):
  - ASSOCIATED(field1, field2, condition)
  - IMPLIES(condition_on_field1, requirement_on_field2)
  
- Conditional (conditional constraints):
  - CONDITIONAL(EQ(field1, X), action_on_field2)

Basic Operators:
- EQ(X,Y) | NE(X,Y)
- IN(X,{{v1,v2,...}})
- LT(X,Y) | LE(X,Y) | GT(X,Y) | GE(X,Y)
- AND(...) | OR(...) | NOT(...)
- IMPLIES(condition, result)
- MATCH(field1, field2)

Output JSON ONLY:
{{
  "result": "DSL | NO_RULE",
  "type": "CrossReference | ValueDependency | RangeAlignment | Association | Conditional",
  "dsl": "formal DSL expression using operators above",
  "preconditions": ["list any preconditions"],
  "predicate": "human-readable predicate description",
  "advisory": false,
  "examples": {{
    "valid": ["concrete assignment example"],
    "invalid": ["concrete assignment example"]
  }},
  "notes": "1-2 lines explaining why NO_RULE or edge-guards",
  "version_tags": ["r16","r17"]
}}

Decision rules for NO_RULE:
- Evidence lacks both target fields or doesn't relate them across IEs.
- Evidence is purely definitional without cross-field relation.
- Only 'should' guidance with no non-advisory constraint.
- Requires external assumptions not present in evidence.
- Evidence only describes single-IE behavior.

Examples:

1. CrossReference (ID matching):
   DSL: "MATCH(field1, field2)"
   Type: CrossReference
   
2. ValueDependency:
   DSL: "IMPLIES(EQ(field1, 'typeD'), EQ(field2, 'enabled'))"
   Type: ValueDependency
   
3. Conditional with range:
   DSL: "IMPLIES(IN(field1, {{1,2,3}}), AND(GE(field2, 0), LE(field2, 9)))"
   Type: RangeAlignment
"""

# ============================================================================
# Utility functions (reused from Intra-IE)
# ============================================================================

def initialize_directories():
    """Create necessary directories"""
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
    
    match = re.search(r'ts_1(\d{2})(\d{3,4})v', source_file)
    if match:
        series = match.group(1)
        number = match.group(2)
        doc_number = f"{series}.{number}"
        doc_name = f"3GPP TS {doc_number}"
        return {"doc": doc_name}
    
    log_diagnosis(f"Failed to parse source file name: {source_file}")
    return None

def sample_evidences_smart(evidences, max_count=12):
    """Intelligent sampling of evidence to avoid exceeding context length limits"""
    if len(evidences) <= max_count:
        return evidences
    
    confidence_priority = {'HIGH': 4, 'MEDIUM': 3, 'LOW': 2, 'VERY_LOW': 1, 'UNKNOWN': 0}
    
    sorted_evidences = sorted(
        evidences,
        key=lambda e: confidence_priority.get(e.get('confidence', 'UNKNOWN'), 0),
        reverse=True
    )
    
    sampled = []
    seen_sections = set()
    
    for evidence in sorted_evidences:
        section = evidence.get('section_number', 'N/A')
        if section not in seen_sections:
            sampled.append(evidence)
            seen_sections.add(section)
            if len(sampled) >= max_count:
                break
    
    if len(sampled) < max_count:
        for evidence in sorted_evidences:
            if evidence not in sampled:
                sampled.append(evidence)
                if len(sampled) >= max_count:
                    break
    
    return sampled

def get_best_confidence(evidences):
    """Get the highest confidence from the evidence list"""
    if not evidences:
        return 'UNKNOWN'
    
    confidence_priority = {'HIGH': 4, 'MEDIUM': 3, 'LOW': 2, 'VERY_LOW': 1, 'UNKNOWN': 0}
    
    best = max(evidences, 
               key=lambda e: confidence_priority.get(e.get('confidence', 'UNKNOWN'), 0))
    return best.get('confidence', 'UNKNOWN')

def estimate_prompt_tokens(text):
    """Rough estimation of token count"""
    return len(text) // 4

def format_evidences_for_prompt(evidences):
    """Format multiple evidence into prompt text"""
    formatted_blocks = []
    
    for idx, evidence in enumerate(evidences, 1):
        section = evidence.get('section_number', 'N/A')
        title = evidence.get('section_title', 'Unknown')
        source = evidence.get('source_file', 'Unknown')
        confidence = evidence.get('confidence', 'UNKNOWN')
        sentence = evidence.get('text', '')  # Use the 'text' field after aggregation
        
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
    """Call ChatGPT API and parse JSON response (with retry)"""
    try:
        client = OpenAI(api_key=API_KEY)
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a 3GPP specification expert. Always respond with valid JSON using the exact format specified."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
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

def parse_key(key_str: str) -> Tuple[str, str, str, str]:
    """Parse quadruple key"""
    parts = key_str.split("___")
    if len(parts) != 4:
        raise ValueError(f"Invalid key format: {key_str}")
    return tuple(parts)

def save_dsl_file(ie1, field1, ie2, field2, field_ids, api_response, evidences, all_citations, original_evidence_count=None):
    """Save JSON file - Fully consistent with Intra-IE format"""
    
    # Use IE pair as subdirectory
    ie_pair_name = f"{ie1}_{ie2}"
    ie_dir = os.path.join(OUTPUT_DIR, ie_pair_name)
    os.makedirs(ie_dir, exist_ok=True)
    
    filename = f"{ie1}_{field1}_{ie2}_{field2}.json"
    filepath = os.path.join(ie_dir, filename)
    
    try:
        evidence_text = "\n---\n".join([e.get('text', '') for e in evidences])
        
        if original_evidence_count is None:
            original_evidence_count = len(evidences)
        
        evidence_info = {
            "used_count": len(evidences),
            "original_count": original_evidence_count,
            "sampled": original_evidence_count > len(evidences)
        }
        
        # Same output format as Intra-IE
        if api_response and api_response.get("result") == "DSL":
            content = {
                "dsl_rule": api_response.get("dsl"),
                "constraint_type": api_response.get("type"),
                "has_valid_rule": True,
                "field_ids": field_ids,
                "predicate": api_response.get("predicate"),
                "preconditions": api_response.get("preconditions", []),
                "advisory": api_response.get("advisory", False),
                "citations": all_citations,
                "examples": api_response.get("examples", {"valid": [], "invalid": []}),
                "notes": api_response.get("notes", ""),
                "version_tags": api_response.get("version_tags", []),
                "meta": {
                    "ie1_name": ie1,
                    "field1": field1,
                    "ie2_name": ie2,
                    "field2": field2,
                    "is_inter_ie": True,  # Marked as Inter-IE
                    "evidence_info": evidence_info,
                    "all_sources": list(set(e.get('source_file', '') for e in evidences)),
                    "all_sections": list(set(e.get('section_number', '') for e in evidences)),
                    "best_confidence": get_best_confidence(evidences),
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
                "field_ids": field_ids,
                "reason": "NO_RULE - insufficient evidence or no valid constraint found",
                "notes": api_response.get("notes", "") if api_response else "API call failed",
                "advisory": api_response.get("advisory", False) if api_response else False,
                "citations": all_citations,
                "meta": {
                    "ie1_name": ie1,
                    "field1": field1,
                    "ie2_name": ie2,
                    "field2": field2,
                    "is_inter_ie": True,
                    "evidence_info": evidence_info,
                    "all_sources": list(set(e.get('source_file', '') for e in evidences)),
                    "all_sections": list(set(e.get('section_number', '') for e in evidences)),
                    "best_confidence": get_best_confidence(evidences),
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

def filter_field_pairs(aggregated_data: Dict, strategy: str = "balanced",
                      min_evidence: int = 5) -> Dict:
    """Filter field pairs"""
    if strategy == "none":
        return aggregated_data
    
    filtered = {}
    
    for key, entry in aggregated_data.items():
        high_count = entry["confidence_counts"].get("HIGH", 0)
        medium_count = entry["confidence_counts"].get("MEDIUM", 0)
        evidence_count = len(entry["evidences"])
        
        keep = False
        
        if strategy == "conservative":
            keep = (high_count > 0 and evidence_count >= 10)
        elif strategy == "balanced":
            keep = ((high_count + medium_count > 0) and evidence_count >= min_evidence)
        elif strategy == "aggressive":
            keep = (high_count + medium_count > 0)
        
        if keep:
            filtered[key] = entry
    
    return filtered

def process_field_pair(field_pair_key, field_pair_data):
    """Processing individual field pairs"""
    
    try:
        # Parsing key
        ie1, field1, ie2, field2 = parse_key(field_pair_key)
        
        ie_pair = field_pair_data['ie_pair']
        field_pair = field_pair_data['field_pair']
        field_ids = field_pair_data['field_ids']
        evidences = field_pair_data['evidences']
        
        print(f"    🔄 {ie1}.{field1} ↔ {ie2}.{field2}", end="")
        
        # Smart Sampling
        original_count = len(evidences)
        if len(evidences) > MAX_EVIDENCES_PER_PAIR:
            evidences = sample_evidences_smart(evidences, MAX_EVIDENCES_PER_PAIR)
            print(f" (sampled {len(evidences)}/{original_count})", end="")
        
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
        
        # Format evidence
        evidence_text = format_evidences_for_prompt(evidences)
        
        # Build prompt
        prompt = PROMPT_TEMPLATE.format(
            ie1=ie1,
            ie2=ie2,
            field1=field1,
            field2=field2,
            evidence_text=evidence_text
        )
        
        # Estimate tokens
        estimated_tokens = estimate_prompt_tokens(prompt)
        if estimated_tokens > 7000:
            print(f" ⚠️{estimated_tokens}tok", end="")
            log_diagnosis(f"Large prompt for {ie1}.{field1} ↔ {ie2}.{field2} - estimated {estimated_tokens} tokens")
        
        # Call API
        if DRY_RUN:
            api_response = {
                "result": "DSL",
                "type": "CrossReference",
                "dsl": "MATCH(field1, field2)",
                "predicate": "Dry run test",
                "notes": "Dry run mode",
                "advisory": False
            }
        else:
            api_response = call_chatgpt_api(prompt)
        
        if api_response:
            filepath = save_dsl_file(ie1, field1, ie2, field2, field_ids, 
                                    api_response, evidences, all_citations, 
                                    original_evidence_count=original_count)
            
            if api_response.get("result") == "DSL":
                constraint_type = api_response.get("type", "Unknown")
                print(f" → ✅ {constraint_type}")
            else:
                print(f" → ⭕ NO_RULE")
            
            return filepath, api_response.get("result") == "DSL"
        else:
            print(f" → ❌ FAILED")
            log_diagnosis(f"Failed to get response for {ie1}.{field1} ↔ {ie2}.{field2}")
            return None, False
            
    except Exception as e:
        print(f" → ❌ ERROR: {e}")
        log_diagnosis(f"Error processing {field_pair_key}: {e}")
        return None, False

def process_aggregated_file(aggregated_path, limit=None):
    """Processing aggregate files (concurrent version)"""
    print(f"\nLoading aggregated data from: {aggregated_path}")
    
    try:
        with open(aggregated_path, 'r', encoding='utf-8') as f:
            aggregated_data = json.load(f)
    except Exception as e:
        print(f"❌ Error loading aggregated file: {e}")
        return
    
    print(f"\n{'='*60}")
    print("Inter-IE Aggregated Data")
    print(f"{'='*60}")
    print(f"Total field pairs: {len(aggregated_data)}")
    
    # Application Filter
    if FILTER_STRATEGY != "none":
        print(f"\n🔍 Applying filter strategy: {FILTER_STRATEGY}")
        print(f"   Minimum evidence: {MIN_EVIDENCE_COUNT}")
        
        filtered_data = filter_field_pairs(aggregated_data, 
                                          strategy=FILTER_STRATEGY,
                                          min_evidence=MIN_EVIDENCE_COUNT)
        
        print(f"✅ After filtering: {len(filtered_data)} field pairs")
        print(f"   Filter rate: {(1 - len(filtered_data)/len(aggregated_data))*100:.1f}%")
        
        aggregated_data = filtered_data
    
    # Limit processing quantity
    if limit:
        keys = list(aggregated_data.keys())[:limit]
        aggregated_data = {k: aggregated_data[k] for k in keys}
        print(f"⚠️  Limited to {limit} pairs for testing")
    
    print(f"\n{'='*60}")
    print(f"Processing {len(aggregated_data)} field pairs...")
    print(f"Concurrency: {MAX_CONCURRENT_REQUESTS} parallel requests")
    print(f"{'='*60}")
    
    # Statistics
    success_count = 0
    dsl_count = 0
    no_rule_count = 0
    failed_count = 0
    
    start_time = time.time()
    
    tasks = list(aggregated_data.items())
    
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
        future_to_task = {
            executor.submit(process_field_pair, key, data): (idx, key)
            for idx, (key, data) in enumerate(tasks, 1)
        }
        
        for future in as_completed(future_to_task):
            idx, key = future_to_task[future]
            
            elapsed = time.time() - start_time
            progress_pct = (idx / len(tasks)) * 100
            avg_time = elapsed / idx if idx > 0 else 0
            eta_seconds = avg_time * (len(tasks) - idx)
            
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
                log_diagnosis(f"Task execution error: {e}")
    
    total_time = time.time() - start_time
    
    print(f"\n{'='*60}")
    print("Processing Results")
    print(f"{'='*60}")
    print(f"⏱️  Total time: {total_time/60:.1f} minutes")
    print(f"⚡ Average: {total_time/len(tasks):.1f}s per field pair")
    print(f"📈 Total processed: {success_count}/{len(tasks)}")
    print(f"   ✅ Valid DSL rules: {dsl_count}")
    print(f"   ⭕ No rules found: {no_rule_count}")
    print(f"   ❌ Failed: {failed_count}")
    if success_count > 0:
        print(f"   🎯 DSL Success rate: {dsl_count/success_count*100:.1f}%")

def main():
    global FILTER_STRATEGY, MIN_EVIDENCE_COUNT, DRY_RUN, VERBOSE, DEBUG_MODE
    
    parser = argparse.ArgumentParser(description="Generate Inter-IE DSL rules (based on Intra-IE design)")
    parser.add_argument("--strategy", choices=["conservative", "balanced", "aggressive", "none"],
                       default="none", help="Filtering strategy")
    parser.add_argument("--min-evidence", type=int, default=5)
    parser.add_argument("--limit", type=int, default=None, help="Limit number of pairs (for testing)")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--debug", action="store_true")
    
    args = parser.parse_args()
    
    FILTER_STRATEGY = args.strategy
    MIN_EVIDENCE_COUNT = args.min_evidence
    DRY_RUN = args.dry_run
    VERBOSE = not args.quiet
    DEBUG_MODE = args.debug
    
    print("="*60)
    print("🎯 INTER-IE DSL GENERATION (Based on Intra-IE Design)")
    print(f"Model: {MODEL}")
    print("="*60)
    
    initialize_directories()
    open(DIAGNOSIS_FILE, 'w').close()
    
    if not API_KEY and not DRY_RUN:
        print("❌ Error: OPENAI_API_KEY not set")
        return
    
    if not os.path.exists(AGGREGATED_FILE):
        print(f"\n❌ Aggregated file not found: {AGGREGATED_FILE}")
        return
    
    start_time = datetime.now()
    
    process_aggregated_file(AGGREGATED_FILE, limit=args.limit)
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    print("\n" + "="*60)
    print("🎉 PROCESSING COMPLETED!")
    print(f"⏱️  Total time: {duration}")
    print(f"📂 Results saved in: {OUTPUT_DIR}")
    print(f"📋 Diagnosis log: {DIAGNOSIS_FILE}")
    print("="*60)

if __name__ == "__main__":
    main()