#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug Single Field Pair - Intra-IE DSL Generation
Standalone script for testing specific field pairs without running the full pipeline
"""

import os
import json
import glob
import argparse
from pathlib import Path

# Import functions from main script
from generate_intra_ie_dsl_updated_v2 import (
    call_chatgpt_api,
    format_evidences_for_prompt,
    find_asn_file,
    read_asn_content,
    PROMPT_TEMPLATE
)

# ============================================================================
# Configuration
# ============================================================================

API_KEY = "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"  # TODO: Replace with your API key
AGGREGATED_FILE = "../outputs/aggregated/aggregated_field_pairs.json"
ASN_DIR = "../TS38331ASN"

# ============================================================================
# Helper Functions
# ============================================================================

def load_aggregated_data():
    """Load aggregated field pairs data"""
    if not os.path.exists(AGGREGATED_FILE):
        print(f"❌ Aggregated file not found: {AGGREGATED_FILE}")
        return None
    
    try:
        with open(AGGREGATED_FILE, 'r') as f:
            data = json.load(f)
        return data.get('field_pairs', {})
    except Exception as e:
        print(f"❌ Error loading aggregated file: {e}")
        return None

def find_field_pair(field_pairs, field1, field2, ie_name=None):
    """Find field pair by field names and optional IE name"""
    matches = []
    
    for key, data in field_pairs.items():
        fields = data.get('fields', [])
        
        # Check if fields match (in either order)
        if (fields == [field1, field2]) or (fields == [field2, field1]):
            ie_names = data.get('ie_names', [])
            
            # If IE specified, check if it matches
            if ie_name:
                if ie_name in ie_names or any(ie_name in name for name in ie_names):
                    matches.append((key, data))
            else:
                matches.append((key, data))
    
    return matches

def filter_evidences(evidences, min_confidence=None, max_count=None):
    """Filter evidences by confidence and limit count"""
    confidence_order = ['HIGH', 'MEDIUM', 'LOW', 'VERY_LOW', 'UNKNOWN']
    
    # Filter by min confidence
    if min_confidence:
        min_idx = confidence_order.index(min_confidence)
        valid_confidences = confidence_order[:min_idx + 1]
        filtered = [e for e in evidences if e.get('confidence', 'UNKNOWN') in valid_confidences]
    else:
        filtered = evidences[:]
    
    # Limit count (keeping highest confidence)
    if max_count and len(filtered) > max_count:
        # Sort by confidence
        confidence_priority = {c: i for i, c in enumerate(confidence_order)}
        filtered.sort(key=lambda e: confidence_priority.get(e.get('confidence', 'UNKNOWN'), 999))
        filtered = filtered[:max_count]
    
    return filtered

def print_evidence_stats(evidences, title="Evidences"):
    """Print evidence statistics"""
    print(f"\n{title}:")
    print(f"  Total: {len(evidences)}")
    
    # Count by confidence
    confidence_counts = {}
    for e in evidences:
        conf = e.get('confidence', 'UNKNOWN')
        confidence_counts[conf] = confidence_counts.get(conf, 0) + 1
    
    print(f"  Confidence distribution:")
    for conf in ['HIGH', 'MEDIUM', 'LOW', 'VERY_LOW', 'UNKNOWN']:
        count = confidence_counts.get(conf, 0)
        if count > 0:
            print(f"    - {conf}: {count}")
    
    # Count by source
    sources = set(e.get('source_file', '') for e in evidences)
    print(f"  Sources: {len(sources)}")
    for src in sorted(sources):
        count = sum(1 for e in evidences if e.get('source_file', '') == src)
        print(f"    - {src}: {count}")

def print_dsl_result(result):
    """Print DSL generation result"""
    print(f"\n{'='*60}")
    print("DSL GENERATION RESULT")
    print(f"{'='*60}")
    
    if not result:
        print("❌ API call failed - no result")
        return
    
    if result.get("result") == "DSL":
        print("✅ DSL RULE GENERATED")
        print(f"\nDSL: {result.get('dsl', 'N/A')}")
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
                for ex in examples['valid']:
                    print(f"  ✓ {ex}")
            if examples.get('invalid'):
                print(f"\nInvalid examples:")
                for ex in examples['invalid']:
                    print(f"  ✗ {ex}")
        
        if result.get('notes'):
            print(f"\nNotes: {result['notes']}")
        
        if result.get('version_tags'):
            print(f"Version tags: {', '.join(result['version_tags'])}")
    else:
        print("⭕ NO_RULE")
        if result.get('notes'):
            print(f"\nReason: {result['notes']}")
        if result.get('advisory'):
            print(f"Advisory: {result['advisory']}")

# ============================================================================
# Main Debug Function
# ============================================================================

def debug_field_pair(field1, field2, ie_name=None, min_confidence=None, 
                    max_evidences=None, verbose=False, output_file=None):
    """Debug a specific field pair"""
    
    print("="*60)
    print("🔍 INTRA-IE DSL GENERATION DEBUG")
    print("="*60)
    
    # Load aggregated data
    print(f"\n📁 Loading aggregated data...")
    field_pairs = load_aggregated_data()
    if not field_pairs:
        return
    
    print(f"   Loaded {len(field_pairs)} unique field pairs")
    
    # Find matching field pair
    print(f"\n🔎 Searching for: {field1} ↔ {field2}")
    if ie_name:
        print(f"   IE filter: {ie_name}")
    
    matches = find_field_pair(field_pairs, field1, field2, ie_name)
    
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
    
    # Use first match
    key, pair_data = matches[0]
    
    print(f"\n✅ Found field pair: {key}")
    
    # Extract data
    fields = pair_data['fields']
    field_ids = pair_data['field_ids']
    evidences = pair_data['evidences']
    ie_names = pair_data.get('ie_names', [])
    
    print(f"\n{'='*60}")
    print("FIELD PAIR INFO")
    print(f"{'='*60}")
    print(f"Key: {key}")
    print(f"Fields: {fields}")
    print(f"Field IDs: {field_ids}")
    print(f"IE Names: {', '.join(ie_names)}")
    print(f"Original evidence count: {len(evidences)}")
    print(f"Best confidence: {pair_data.get('best_confidence', 'N/A')}")
    
    # Print original evidence stats
    print_evidence_stats(evidences, "Original Evidence Statistics")
    
    # Filter evidences
    filtered_evidences = filter_evidences(evidences, min_confidence, max_evidences)
    
    if len(filtered_evidences) < len(evidences):
        print(f"\n{'='*60}")
        print("EVIDENCE FILTERING")
        print(f"{'='*60}")
        if min_confidence:
            print(f"Min confidence: {min_confidence}")
        if max_evidences:
            print(f"Max evidences: {max_evidences}")
        print_evidence_stats(filtered_evidences, "Filtered Evidence Statistics")
    
    if not filtered_evidences:
        print(f"\n❌ No evidences remaining after filtering")
        return
    
    # Load ASN.1 content
    ie_name_for_asn = ie_names[0] if ie_names else "UnknownIE"
    asn_file = find_asn_file(ie_name_for_asn)
    
    if asn_file:
        print(f"\n📄 Loading ASN.1 definition from: {os.path.basename(asn_file)}")
        asn_content = read_asn_content(asn_file)
    else:
        print(f"\n⚠️  ASN.1 file not found for IE: {ie_name_for_asn}")
        asn_content = "ASN.1 definition not found"
    
    # Format prompt
    evidence_text = format_evidences_for_prompt(filtered_evidences)
    
    field1_name = fields[0]
    field2_name = fields[1]
    field1_ids = field_ids[0] if len(field_ids) > 0 else []
    field2_ids = field_ids[1] if len(field_ids) > 1 else []
    
    prompt = PROMPT_TEMPLATE.format(
        ie_name=ie_name_for_asn,
        asn_content=asn_content,
        field1=field1_name,
        field1_ids=str(field1_ids),
        field2=field2_name,
        field2_ids=str(field2_ids),
        evidence_text=evidence_text
    )
    
    if verbose:
        print(f"\n{'='*60}")
        print("PROMPT (first 1000 chars)")
        print(f"{'='*60}")
        print(prompt[:1000])
        print("..." if len(prompt) > 1000 else "")
    
    # Estimate tokens
    estimated_tokens = len(prompt) // 4
    print(f"\n📊 Estimated prompt tokens: ~{estimated_tokens}")
    
    # Call API
    print(f"\n{'='*60}")
    print("CALLING GPT-4o API...")
    print(f"{'='*60}")
    
    api_response = call_chatgpt_api(prompt)
    
    if verbose and api_response:
        print(f"\n{'='*60}")
        print("RAW API RESPONSE")
        print(f"{'='*60}")
        print(json.dumps(api_response, indent=2))
    
    # Print result
    print_dsl_result(api_response)
    
    # Save output if requested
    if output_file and api_response:
        output_data = {
            "field_pair_key": key,
            "fields": fields,
            "field_ids": field_ids,
            "ie_names": ie_names,
            "original_evidence_count": len(evidences),
            "filtered_evidence_count": len(filtered_evidences),
            "filter_config": {
                "min_confidence": min_confidence,
                "max_evidences": max_evidences
            },
            "api_response": api_response,
            "evidences_used": filtered_evidences
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved to: {output_file}")

# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Debug DSL generation for a specific field pair'
    )
    
    parser.add_argument('--fields', nargs=2, required=True,
                       help='Two field names (e.g., --fields nrofSymbols startPosition)')
    parser.add_argument('--ie', 
                       help='IE name to filter (if multiple matches found)')
    parser.add_argument('--min-confidence',
                       choices=['HIGH', 'MEDIUM', 'LOW', 'VERY_LOW'],
                       help='Minimum confidence level for evidences')
    parser.add_argument('--max-evidences', type=int,
                       help='Maximum number of evidences to use')
    parser.add_argument('--verbose', action='store_true',
                       help='Show detailed information (prompt, raw response)')
    parser.add_argument('--output',
                       help='Save results to JSON file')
    
    args = parser.parse_args()
    
    # Run debug
    debug_field_pair(
        field1=args.fields[0],
        field2=args.fields[1],
        ie_name=args.ie,
        min_confidence=args.min_confidence,
        max_evidences=args.max_evidences,
        verbose=args.verbose,
        output_file=args.output
    )

if __name__ == "__main__":
    main()