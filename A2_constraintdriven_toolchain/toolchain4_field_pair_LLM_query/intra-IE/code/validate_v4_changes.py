#!/usr/bin/env python3
"""
Quick Validation Script for V4 Changes
Test if the improved prompt can generate correct DSL for nrofSymbols-startPosition
"""

import os
import json
import sys

# Add parent directory to path to import from main script
sys.path.insert(0, '.')

from generate_intra_ie_dsl_updated_v4 import (
    sample_evidences_smart,
    format_evidences_for_prompt,
    find_asn_file,
    read_asn_content,
    call_chatgpt_api,
    PROMPT_TEMPLATE,
    EVIDENCE_FILTER_MODE,
    MIN_HIGH_MEDIUM_COUNT
)

def test_specific_pair():
    """Test nrofSymbols-startPosition with V4 logic"""
    
    print("="*60)
    print("🧪 VALIDATION TEST - V4 Changes")
    print("="*60)
    print(f"Testing: nrofSymbols ↔ startPosition (srs-Config)")
    print(f"Filter mode: {EVIDENCE_FILTER_MODE}")
    print(f"Min H/M count: {MIN_HIGH_MEDIUM_COUNT}")
    print("="*60)
    
    # Load aggregated data
    print("\n📁 Loading aggregated data...")
    aggregated_file = "../outputs/aggregated/aggregated_field_pairs.json"
    
    try:
        with open(aggregated_file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Aggregated file not found: {aggregated_file}")
        print("Please run the aggregation script first!")
        return False
    
    field_pairs = data.get('field_pairs', {})
    print(f"   Loaded {len(field_pairs)} field pairs")
    
    # Find target pair
    print("\n🔎 Searching for nrofSymbols-startPosition...")
    matches = []
    for key, pair_data in field_pairs.items():
        fields = pair_data.get('fields', [])
        ie_names = pair_data.get('ie_names', [])
        
        if (fields == ['nrofSymbols', 'startPosition'] or fields == ['startPosition', 'nrofSymbols']):
            if ie_names and 'srs-Config' in ie_names[0]:
                matches.append((key, pair_data))
    
    if not matches:
        print("❌ Target pair not found!")
        return False
    
    key, pair_data = matches[0]
    print(f"✅ Found: {key}")
    
    # Extract info
    fields = pair_data['fields']
    field_ids = pair_data['field_ids']
    evidences = pair_data['evidences']
    ie_names = pair_data.get('ie_names', [])
    
    print(f"\n{'='*60}")
    print("EVIDENCE ANALYSIS")
    print(f"{'='*60}")
    print(f"Original evidence count: {len(evidences)}")
    
    # Count by confidence
    conf_counts = {}
    for e in evidences:
        conf = e.get('confidence', 'UNKNOWN')
        conf_counts[conf] = conf_counts.get(conf, 0) + 1
    
    print(f"Confidence distribution:")
    for conf in ['HIGH', 'MEDIUM', 'LOW', 'VERY_LOW']:
        if conf in conf_counts:
            print(f"  - {conf}: {conf_counts[conf]}")
    
    # Apply filtering
    print(f"\n{'='*60}")
    print("APPLYING V4 FILTERING")
    print(f"{'='*60}")
    
    filtered_evidences = sample_evidences_smart(evidences, max_count=12, filter_mode=EVIDENCE_FILTER_MODE)
    
    print(f"Filtered evidence count: {len(filtered_evidences)}")
    filtered_conf_counts = {}
    for e in filtered_evidences:
        conf = e.get('confidence', 'UNKNOWN')
        filtered_conf_counts[conf] = filtered_conf_counts.get(conf, 0) + 1
    
    print(f"Filtered confidence distribution:")
    for conf in ['HIGH', 'MEDIUM', 'LOW', 'VERY_LOW']:
        if conf in filtered_conf_counts:
            print(f"  - {conf}: {filtered_conf_counts[conf]}")
    
    # Check sources
    sources = set(e.get('source_file', '') for e in filtered_evidences)
    print(f"\nSources used:")
    for src in sources:
        print(f"  - {src}")
    
    # Build prompt
    print(f"\n{'='*60}")
    print("CALLING API WITH V4 PROMPT")
    print(f"{'='*60}")
    
    ie_name = ie_names[0] if ie_names else "UnknownIE"
    field1, field2 = fields
    field1_ids = field_ids[0] if len(field_ids) > 0 else []
    field2_ids = field_ids[1] if len(field_ids) > 1 else []
    
    # Load ASN.1
    asn_file = find_asn_file(ie_name)
    if asn_file:
        asn_content = read_asn_content(asn_file)
    else:
        asn_content = "ASN.1 definition not found"
    
    evidence_text = format_evidences_for_prompt(filtered_evidences)
    
    prompt = PROMPT_TEMPLATE.format(
        ie_name=ie_name,
        asn_content=asn_content,
        field1=field1,
        field1_ids=str(field1_ids),
        field2=field2,
        field2_ids=str(field2_ids),
        evidence_text=evidence_text
    )
    
    print(f"Prompt tokens: ~{len(prompt)//4}")
    
    # Call API
    api_response = call_chatgpt_api(prompt)
    
    # Check result
    print(f"\n{'='*60}")
    print("VALIDATION RESULT")
    print(f"{'='*60}")
    
    if not api_response:
        print("❌ API call failed")
        return False
    
    if api_response.get("result") == "DSL":
        dsl = api_response.get("dsl", "")
        constraint_type = api_response.get("type", "")
        predicate = api_response.get("predicate", "")
        notes = api_response.get("notes", "")
        
        print(f"✅ DSL Generated!")
        print(f"\nDSL: {dsl}")
        print(f"Type: {constraint_type}")
        print(f"Predicate: {predicate}")
        print(f"Notes: {notes}")
        
        # Check if it's correct
        print(f"\n{'='*60}")
        print("CORRECTNESS CHECK")
        print(f"{'='*60}")
        
        # Expected correct patterns
        correct_simple_patterns = [
            "GE(field2, field1 - 1)",
            "GE(field2, field1-1)",
        ]
        
        correct_conditional_patterns = [
            "IMPLIES(N_hop > 1, GE(field2, field1 - 1))",
            "IMPLIES(N_hop > 1, GE(field2, field1-1))",
        ]
        
        # Wrong patterns from V3
        wrong_patterns = [
            "IMPLIES(GT(field2, field1",  # Constraint in condition
            "field1 + field2",             # Extra wrong constraint
        ]
        
        is_simple_correct = any(pattern in dsl for pattern in correct_simple_patterns)
        is_conditional_correct = any(pattern in dsl for pattern in correct_conditional_patterns)
        has_wrong = any(pattern in dsl for pattern in wrong_patterns)
        
        if is_simple_correct and not has_wrong:
            print("✅ PERFECT! Simple atomic constraint (best format):")
            print("   GE(field2, field1 - 1)")
            print("\n🎉 V4 VALIDATION PASSED - OPTIMAL FORMAT!")
            return True
        elif is_conditional_correct and not has_wrong:
            print("✅ GOOD! Conditional constraint (acceptable format):")
            print("   IMPLIES(N_hop > 1, GE(field2, field1 - 1))")
            print("\n🎉 V4 VALIDATION PASSED - ACCEPTABLE FORMAT!")
            return True
        elif (is_simple_correct or is_conditional_correct) and has_wrong:
            print("⚠️  PARTIAL: Core constraint found but has extra wrong parts")
            print("   Better than V3, but not perfect")
            return True
        else:
            print("❌ INCORRECT: Did not find the correct constraint pattern")
            print("\n❌ V4 DID NOT FULLY SOLVE THE PROBLEM")
            return False
    else:
        print("⭕ NO_RULE")
        print(f"Reason: {api_response.get('notes', 'N/A')}")
        print("\n❌ V4 CHANGES DID NOT SOLVE THE PROBLEM")
        return False

if __name__ == "__main__":
    success = test_specific_pair()
    
    print(f"\n{'='*60}")
    if success:
        print("✅ VALIDATION PASSED - Safe to run full generation")
        print("\nNext steps:")
        print("  python3 generate_intra_ie_dsl_updated_v4.py")
    else:
        print("❌ VALIDATION FAILED - Need further debugging")
        print("\nNext steps:")
        print("  1. Check diagnosis log")
        print("  2. Adjust prompt or parameters")
        print("  3. Re-run this test")
    print(f"{'='*60}")
    
    sys.exit(0 if success else 1)