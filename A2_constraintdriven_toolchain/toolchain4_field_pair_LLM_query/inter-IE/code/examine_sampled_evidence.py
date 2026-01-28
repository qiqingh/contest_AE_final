#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Examine Sampled Evidence - See what LLM actually receives
"""

import json
import sys

sys.path.insert(0, '.')
from generate_inter_ie_dsl_concurrent_improved import sample_evidences_smart

AGGREGATED_FILE = "../output/inter_ie_aggregated/aggregated_inter_ie_field_pairs.json"
TARGET_KEY = "pdcch-configcommon_commoncontrolresourceset___controlresourcesetid___pdcch-configcommon_commonsearchspacelist___controlresourcesetid"
MAX_EVIDENCES = 70

def main():
    print("="*80)
    print("🔍 Examining Actual Sampled Evidence")
    print("="*80)
    
    # Load data
    with open(AGGREGATED_FILE, 'r') as f:
        data = json.load(f)
    
    if TARGET_KEY not in data:
        print(f"❌ Key not found: {TARGET_KEY}")
        return
    
    field_pair_data = data[TARGET_KEY]
    evidences = field_pair_data['evidences']
    
    print(f"\n📊 Total evidences: {len(evidences)}")
    
    # Sample using the SAME function as batch script
    sampled = sample_evidences_smart(evidences, MAX_EVIDENCES)
    
    print(f"📝 Sampled evidences: {len(sampled)}")
    print()
    
    # Group by section
    from collections import Counter
    sections = Counter([e.get('section_number', 'N/A') for e in sampled])
    
    print("📂 Section distribution in sampled evidence:")
    for section, count in sections.most_common():
        print(f"   {section}: {count} evidences")
    print()
    
    # Show each evidence with analysis
    print("="*80)
    print("📝 Detailed Evidence List (All 70)")
    print("="*80)
    print()
    
    association_found = []
    
    for idx, e in enumerate(sampled, 1):
        section = e.get('section_number', 'N/A')
        conf = e.get('confidence', 'UNKNOWN')
        text = e.get('text', '')
        
        # Check for key phrases
        has_association = 'association between' in text.lower()
        has_search_space = 'search space' in text.lower()
        has_coreset = 'coreset' in text.lower()
        
        # Highlight key evidences
        marker = ""
        if has_association and has_search_space:
            marker = " 🎯 KEY!"
            association_found.append(idx)
        
        print(f"{idx:2d}. [Section={section:8s} | Conf={conf:6s}]{marker}")
        print(f"    {text[:200]}...")
        
        if has_association or (idx <= 10) or (idx in association_found):
            # Show more details for key evidences or first 10
            print(f"    Full text: {text[:500]}...")
        
        print()
    
    # Summary
    print("="*80)
    print("📊 Analysis Summary")
    print("="*80)
    
    if association_found:
        print(f"✅ Found {len(association_found)} 'association between' evidence(s) at positions: {association_found}")
    else:
        print("❌ NO 'association between' evidence found in sampled 70!")
        print("   This explains why LLM returns NO_RULE.")
    
    # Check if buried in noise
    if association_found:
        first_pos = min(association_found)
        print(f"\n📍 First key evidence at position: {first_pos}")
        if first_pos > 50:
            print(f"   ⚠️  Buried deep! LLM may miss it among 70 evidences.")
        elif first_pos > 30:
            print(f"   ⚠️  In the back half. May be overlooked.")
        else:
            print(f"   ✅ In front half. Should be visible.")
    
    # Analyze top 10
    print(f"\n🔝 Top 10 Evidence Types:")
    for idx in range(1, min(11, len(sampled)+1)):
        e = sampled[idx-1]
        text = e.get('text', '').lower()
        
        if 'definition' in text or 'consists of' in text or 'is defined' in text:
            print(f"   {idx}. Definitional (not a constraint)")
        elif 'configuration' in text or 'configured' in text:
            print(f"   {idx}. Configuration description")
        elif 'coreset' in text and 'search space' not in text:
            print(f"   {idx}. CORESET-only (single IE)")
        elif 'search space' in text and 'coreset' not in text:
            print(f"   {idx}. SearchSpace-only (single IE)")
        else:
            print(f"   {idx}. Other: {text[:80]}")

if __name__ == "__main__":
    main()