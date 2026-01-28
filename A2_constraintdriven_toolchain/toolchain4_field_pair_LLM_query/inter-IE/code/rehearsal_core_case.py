#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rehearsal Script - Test core requirement case using EXACT batch script logic
This ensures that if it works here, it WILL work in full batch run.

IMPORTANT: This script imports from generate_inter_ie_dsl_concurrent_improved.py
Make sure that file contains:
- MAX_EVIDENCES_PER_PAIR = 70 (updated to cover rank 56-57)
- ('association between', 40)
- temperature=0.0, seed=42
"""

import os
import json
import sys

# Import the batch script to use its EXACT functions
sys.path.insert(0, '.')
from generate_inter_ie_dsl_concurrent_improved import (
    process_field_pair,
    initialize_directories,
    AGGREGATED_FILE,
    OUTPUT_DIR
)

TARGET_KEY = "pdcch-configcommon_commoncontrolresourceset___controlresourcesetid___pdcch-configcommon_commonsearchspacelist___controlresourcesetid"

def main():
    print("="*80)
    print("🎭 REHEARSAL - Testing core requirement with EXACT batch logic")
    print("="*80)
    print()
    print("This script uses the SAME functions as the batch script.")
    print("If this succeeds, the full batch run WILL succeed for this case.")
    print()
    
    # Initialize directories (same as batch)
    initialize_directories()
    
    # Load aggregated data (same as batch)
    print(f"📂 Loading: {AGGREGATED_FILE}")
    try:
        with open(AGGREGATED_FILE, 'r', encoding='utf-8') as f:
            aggregated_data = json.load(f)
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return
    
    # Check if target exists
    if TARGET_KEY not in aggregated_data:
        print(f"❌ Target key not found: {TARGET_KEY}")
        return
    
    print(f"✅ Target key found")
    
    field_pair_data = aggregated_data[TARGET_KEY]
    
    print(f"\n📊 Field pair info:")
    print(f"   IE pair: {field_pair_data['ie_pair']}")
    print(f"   Field pair: {field_pair_data['field_pair']}")
    print(f"   Total evidences: {len(field_pair_data['evidences'])}")
    print(f"   Confidence distribution: {field_pair_data['confidence_counts']}")
    
    print(f"\n{'='*80}")
    print("🚀 Processing with EXACT batch script logic...")
    print(f"{'='*80}")
    print()
    
    # Call the EXACT same function used in batch processing
    filepath, has_dsl = process_field_pair(TARGET_KEY, field_pair_data)
    
    print(f"\n{'='*80}")
    print("📊 Result")
    print(f"{'='*80}")
    
    if filepath:
        print(f"✅ File created: {filepath}")
        
        # Load and display result
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                result = json.load(f)
            
            print(f"\n📋 Summary:")
            print(f"   has_valid_rule: {result.get('has_valid_rule')}")
            print(f"   constraint_type: {result.get('constraint_type')}")
            print(f"   dsl_rule: {result.get('dsl_rule')}")
            print(f"   predicate: {result.get('predicate', '')[:100]}...")
            
            if result.get('has_valid_rule'):
                print(f"\n🎉 SUCCESS! DSL Generated!")
                print(f"   This means the full batch run WILL succeed for this case.")
            else:
                print(f"\n⚠️  NO_RULE generated")
                print(f"   Reason: {result.get('notes', 'Unknown')}")
                print(f"\n❌ This means the full batch run will ALSO fail for this case!")
                print(f"   Need to investigate further...")
                
        except Exception as e:
            print(f"❌ Error reading result file: {e}")
    else:
        print(f"❌ Processing failed - no file created")
    
    print(f"\n{'='*80}")

if __name__ == "__main__":
    main()