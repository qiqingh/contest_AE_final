#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug Pair with Prompt Experimentation
Simple sandbox for testing different prompts on nrofSymbols-startPosition constraint

Usage:
  1. Modify EXPERIMENTAL_PROMPT below
  2. Run: python3 debug_pair_prompt.py --fields nrofSymbols startPosition --ie srs-Config
  3. Check results, adjust prompt, repeat
"""

import os
import json
import argparse
from pathlib import Path

# Import functions from main script
from generate_intra_ie_dsl_updated_v2 import (
    find_asn_file,
    read_asn_content
)

# For API call, we'll implement inline to avoid dependency issues
from openai import OpenAI

# ============================================================================
# 🔧 EXPERIMENTAL PROMPT - MODIFY THIS TO TEST DIFFERENT VARIATIONS
# ============================================================================

EXPERIMENTAL_PROMPT = """You are a 3GPP specification expert and protocol testing engineer.

Goal: Decide if there is a VALID semantic constraint of type {{ValueDependency, RangeAlignment}} between two fields WITHIN THE SAME IE for 5G RRC message mutation. If not strictly supported by evidence, output NO_RULE.

In your DSL output, use "field1" and "field2" as placeholders (not the actual field names like "{field1}" or "{field2}").

Example:
- CORRECT: IMPLIES(EQ(field1, 'nonCodebook'), EQ(field2, 1))
- WRONG: IMPLIES(EQ({field1}, 'nonCodebook'), EQ({field2}, 1))

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
4) DIRECTION & TRIGGER. Identify the correct trigger condition(s) (e.g., resourceMapping-r17 present) and avoid reversing implication.
5) MACHINE-CHECKABLE. The DSL must use the canonical grammar below and be directly checkable (no vague words). Use field1/field2 as placeholders in the DSL.
6) UNITS & ENUMS. Normalize any required units or enum-to-number mapping explicitly (e.g., n1→1, n2→2). If unknown, output NO_RULE.
7) VERSION/SCOPE GUARDS. If the rule only applies under specific releases/options (e.g., r17 fields; DCI format exclusions), include them in `preconditions`.
8) LOGICAL CONSISTENCY. Check for contradictions. If logically impossible, output NO_RULE.

Allowed Types and Canonical DSL Grammar (using field1/field2):
- ValueDependency:
  - EQ(field1, field2) | NE(field1, field2)
  - EQ(field1, concrete_value) | NE(field1, concrete_value)
  - MAP(field1, {{a->b, c->d, ...}})
  - MOD(field1, field2)==0
  - IN(field1, {{v1,v2,...}})
  - IMPLIES(COND, ATOM) where COND is a boolean over field1/field2; ATOM from this list
- RangeAlignment:
  - LT(field1, field2) | LE(field1, field2) | GT(field1, field2) | GE(field1, field2)
  - LE(field1 + k, CONST) / LE(field1 + field2, CONST)
  - WITHIN(field1, [min,max])

Output JSON ONLY:
{{
  "result": "DSL | NO_RULE",
  "type": "ValueDependency | RangeAlignment",
  "dsl": "IMPLIES( <preconditions>, <constraint_atom> ) using field1/field2",
  "preconditions": ["..."],
  "predicate": "..." ,
  "advisory": false,
  "examples": {{
    "valid": ["...concrete assignment..."],
    "invalid": ["...concrete assignment..."]
  }},
  "notes": "1-2 lines explaining why NO_RULE or edge-guards (e.g., DCI format exclusions).",
  "version_tags": ["r16","r17"]
}}

Decision rules for NO_RULE:
- Evidence lacks both target fields or doesn't relate them.
- Evidence is purely definitional (e.g., 'belongs to' the same object) or default-only without cross-field relation.
- Only 'should' guidance with no non-advisory constraint.
- Requires external assumptions (units/enums/tables not present).
- Contains abstract variables (X, Y, Z) instead of concrete values.
- Logically contradictory or impossible.

Examples of CORRECT DSL (using field1/field2):
- IMPLIES(EQ(field1, 'nonCodebook'), EQ(field2, 1))
- IMPLIES(IN(field1, {{2, 3}}), GT(field2, 1))
- IMPLIES(field1 present, LE(field1 + field2, 14))
- MOD(field1, field2) == 0

Examples of WRONG DSL:
- IMPLIES(EQ(usage, 'nonCodebook'), EQ(nrofSRS-Ports, 1))  # Using actual field names
- IMPLIES(EQ(field1, X), EQ(field2, Y))  # Using variables X, Y"""

# ============================================================================
# Configuration
# ============================================================================

API_KEY = "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"  # TODO: Replace with your API key
AGGREGATED_FILE = "../outputs/aggregated/aggregated_field_pairs.json"
ASN_DIR = "../TS38331ASN"
MODEL = "gpt-4o"

# ============================================================================
# Helper Functions
# ============================================================================

def call_api(prompt):
    """Call GPT-4o API"""
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
        
        # Parse JSON
        if response_text.startswith('```json'):
            response_text = response_text.strip('```json').strip('```').strip()
        elif response_text.startswith('```'):
            response_text = response_text.strip('```').strip()
        
        result = json.loads(response_text)
        return result
    except Exception as e:
        print(f"❌ API call error: {e}")
        return None

def load_aggregated_data():
    """Load aggregated field pairs"""
    if not os.path.exists(AGGREGATED_FILE):
        print(f"❌ Aggregated file not found: {AGGREGATED_FILE}")
        return None
    
    with open(AGGREGATED_FILE, 'r') as f:
        data = json.load(f)
    return data.get('field_pairs', {})

def find_field_pair(field_pairs, field1, field2, ie_name=None):
    """Find field pair"""
    matches = []
    
    for key, data in field_pairs.items():
        fields = data.get('fields', [])
        
        if (fields == [field1, field2]) or (fields == [field2, field1]):
            ie_names = data.get('ie_names', [])
            
            if ie_name:
                if ie_name in ie_names or any(ie_name in name for name in ie_names):
                    matches.append((key, data))
            else:
                matches.append((key, data))
    
    return matches

def filter_evidences(evidences, min_confidence=None, max_count=None):
    """Filter evidences"""
    confidence_order = ['HIGH', 'MEDIUM', 'LOW', 'VERY_LOW', 'UNKNOWN']
    
    if min_confidence:
        min_idx = confidence_order.index(min_confidence)
        valid_confidences = confidence_order[:min_idx + 1]
        filtered = [e for e in evidences if e.get('confidence', 'UNKNOWN') in valid_confidences]
    else:
        filtered = evidences[:]
    
    if max_count and len(filtered) > max_count:
        confidence_priority = {c: i for i, c in enumerate(confidence_order)}
        filtered.sort(key=lambda e: confidence_priority.get(e.get('confidence', 'UNKNOWN'), 999))
        filtered = filtered[:max_count]
    
    return filtered

def format_evidences(evidences):
    """Format evidences for prompt"""
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

def print_evidence_stats(evidences, title="Evidence Statistics"):
    """Print evidence statistics"""
    print(f"\n{title}:")
    print(f"  Total: {len(evidences)}")
    
    # Confidence distribution
    confidence_counts = {}
    for e in evidences:
        conf = e.get('confidence', 'UNKNOWN')
        confidence_counts[conf] = confidence_counts.get(conf, 0) + 1
    
    print(f"  Confidence distribution:")
    for conf in ['HIGH', 'MEDIUM', 'LOW', 'VERY_LOW', 'UNKNOWN']:
        count = confidence_counts.get(conf, 0)
        if count > 0:
            print(f"    - {conf}: {count}")
    
    # Sources
    sources = set(e.get('source_file', '') for e in evidences)
    print(f"  Sources: {len(sources)}")
    for src in sorted(sources):
        count = sum(1 for e in evidences if e.get('source_file', '') == src)
        print(f"    - {src}: {count}")

def print_dsl_result(result):
    """Print DSL result"""
    print(f"\n{'='*60}")
    print("DSL GENERATION RESULT")
    print(f"{'='*60}")
    
    if not result:
        print("❌ API call failed")
        return
    
    if result.get("result") == "DSL":
        print("✅ DSL RULE GENERATED\n")
        print(f"DSL: {result.get('dsl', 'N/A')}")
        print(f"Type: {result.get('type', 'N/A')}")
        print(f"Predicate: {result.get('predicate', 'N/A')}")
        print(f"Advisory: {result.get('advisory', False)}")
        
        if result.get('preconditions'):
            print(f"\nPreconditions:")
            for pc in result['preconditions']:
                print(f"  - {pc}")
        
        if result.get('examples'):
            examples = result['examples']
            if examples.get('valid'):
                print(f"\nValid examples:")
                for ex in examples['valid'][:3]:  # Show first 3
                    print(f"  ✓ {ex}")
            if examples.get('invalid'):
                print(f"\nInvalid examples:")
                for ex in examples['invalid'][:3]:  # Show first 3
                    print(f"  ✗ {ex}")
        
        if result.get('notes'):
            print(f"\nNotes: {result['notes']}")
        
        if result.get('version_tags'):
            print(f"Version tags: {', '.join(result['version_tags'])}")
    else:
        print("⭕ NO_RULE\n")
        if result.get('notes'):
            print(f"Reason: {result['notes']}")
        if result.get('advisory'):
            print(f"Advisory: {result['advisory']}")

# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Prompt experimentation sandbox for DSL generation'
    )
    
    parser.add_argument('--fields', nargs=2, required=True,
                       help='Two field names')
    parser.add_argument('--ie',
                       help='IE name filter')
    parser.add_argument('--min-confidence',
                       choices=['HIGH', 'MEDIUM', 'LOW', 'VERY_LOW'],
                       help='Filter evidences by minimum confidence')
    parser.add_argument('--max-evidences', type=int,
                       help='Limit number of evidences')
    parser.add_argument('--verbose', action='store_true',
                       help='Show full prompt and API response')
    parser.add_argument('--output',
                       help='Save result to JSON file')
    
    args = parser.parse_args()
    
    print("="*60)
    print("🔬 PROMPT EXPERIMENTATION SANDBOX")
    print("="*60)
    
    # Load data
    print(f"\n📁 Loading aggregated data...")
    field_pairs = load_aggregated_data()
    if not field_pairs:
        return
    print(f"   Loaded {len(field_pairs)} unique field pairs")
    
    # Find field pair
    print(f"\n🔎 Searching for: {args.fields[0]} ↔ {args.fields[1]}")
    if args.ie:
        print(f"   IE filter: {args.ie}")
    
    matches = find_field_pair(field_pairs, args.fields[0], args.fields[1], args.ie)
    
    if not matches:
        print(f"\n❌ No matching field pair found")
        return
    
    if len(matches) > 1:
        print(f"\n⚠️  Found {len(matches)} matches:")
        for i, (key, data) in enumerate(matches, 1):
            ie_names = data.get('ie_names', [])
            evidence_count = data.get('evidence_count', 0)
            print(f"   {i}. {', '.join(ie_names)}: {key} ({evidence_count} evidences)")
        print(f"\n   Using first match. Use --ie to specify which one.")
    
    key, pair_data = matches[0]
    
    print(f"\n✅ Found field pair: {key}")
    
    # Extract info
    fields = pair_data['fields']
    field_ids = pair_data['field_ids']
    evidences = pair_data['evidences']
    ie_names = pair_data.get('ie_names', [])
    
    print(f"\n{'='*60}")
    print("FIELD PAIR INFO")
    print(f"{'='*60}")
    print(f"Fields: {fields}")
    print(f"Field IDs: {field_ids}")
    print(f"IE Names: {', '.join(ie_names)}")
    print(f"Best confidence: {pair_data.get('best_confidence', 'N/A')}")
    
    # Evidence statistics
    print_evidence_stats(evidences, "Original Evidence Statistics")
    
    # Filter evidences
    filtered_evidences = filter_evidences(evidences, args.min_confidence, args.max_evidences)
    
    if len(filtered_evidences) < len(evidences):
        print(f"\n{'='*60}")
        print("EVIDENCE FILTERING")
        print(f"{'='*60}")
        if args.min_confidence:
            print(f"Min confidence: {args.min_confidence}")
        if args.max_evidences:
            print(f"Max evidences: {args.max_evidences}")
        print_evidence_stats(filtered_evidences, "Filtered Evidence Statistics")
    
    if not filtered_evidences:
        print(f"\n❌ No evidences remaining after filtering")
        return
    
    # Load ASN.1
    ie_name_for_asn = ie_names[0] if ie_names else "UnknownIE"
    asn_file = find_asn_file(ie_name_for_asn)
    
    if asn_file:
        print(f"\n📄 Loading ASN.1: {os.path.basename(asn_file)}")
        asn_content = read_asn_content(asn_file)
    else:
        print(f"\n⚠️  ASN.1 file not found for: {ie_name_for_asn}")
        asn_content = "ASN.1 definition not found"
    
    # Build prompt
    evidence_text = format_evidences(filtered_evidences)
    
    field1_name = fields[0]
    field2_name = fields[1]
    field1_ids = field_ids[0] if len(field_ids) > 0 else []
    field2_ids = field_ids[1] if len(field_ids) > 1 else []
    
    prompt = EXPERIMENTAL_PROMPT.format(
        ie_name=ie_name_for_asn,
        asn_content=asn_content,
        field1=field1_name,
        field1_ids=str(field1_ids),
        field2=field2_name,
        field2_ids=str(field2_ids),
        evidence_text=evidence_text
    )
    
    estimated_tokens = len(prompt) // 4
    print(f"\n📊 Estimated prompt tokens: ~{estimated_tokens}")
    
    if args.verbose:
        print(f"\n{'='*60}")
        print("FULL PROMPT")
        print(f"{'='*60}")
        print(prompt)
    
    # Call API
    print(f"\n{'='*60}")
    print(f"CALLING {MODEL} API...")
    print(f"{'='*60}")
    
    api_response = call_api(prompt)
    
    if args.verbose and api_response:
        print(f"\n{'='*60}")
        print("RAW API RESPONSE")
        print(f"{'='*60}")
        print(json.dumps(api_response, indent=2))
    
    # Print result
    print_dsl_result(api_response)
    
    # Save output
    if args.output and api_response:
        output_data = {
            "field_pair_key": key,
            "fields": fields,
            "field_ids": field_ids,
            "ie_names": ie_names,
            "evidence_count": len(filtered_evidences),
            "api_response": api_response
        }
        
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved to: {args.output}")

if __name__ == "__main__":
    main()