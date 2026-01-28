#!/usr/bin/env python3
"""
Inter-IE Coverage Check Tool
Verify the effectiveness of the greedy_inter algorithm

Key Indicators:
1. Referenced field coverage
2. Citation relationship coveraae
3. Number of IEs
4. Field Name Diversity
"""

import json
import os
import sys
import re
from collections import defaultdict

# ===============================
# Configuration
# ===============================

# Reference field identification keywords
REF_KEYWORDS = ['Id', 'ID']

def clean_field_name(field_name):
    """Remove array indices [0], [1], etc."""
    return re.sub(r'\[\d+\]', '', field_name)

def is_reference_field(field_name):
    """Determine if it is a reference field"""
    clean_name = clean_field_name(field_name)
    return any(clean_name.endswith(kw) for kw in REF_KEYWORDS)

# ===============================
# IE Data Loading
# ===============================

def load_ie_data(ie_dir):
    """
    Load IE data and generate statistics
    
    Return:
    - ie_count: Number of IEs
    - field_ids: collection of all field IDs
    - ref_field_names: Collection of all referenced field names
    - all_field_names: collection of all field names
    - ref_pair_count: Number of reference relationship pairs
    - ref_field_to_ies: Mapping of reference fields to IEs
    """
    if not os.path.exists(ie_dir):
        print(f"Error: Directory does not exist {ie_dir}")
        return None
    
    field_ids = set()
    all_field_names = set()
    ref_field_names = set()
    ref_field_to_ies = defaultdict(list)
    
    ie_files = [f for f in os.listdir(ie_dir) if f.endswith('.json')]
    ie_count = len(ie_files)
    
    print(f"Scanning {ie_count} IE files...")
    
    for filename in ie_files:
        filepath = os.path.join(ie_dir, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                records = json.load(f)
            
            if not isinstance(records, list):
                continue
            
            ie_ref_fields = set()
            
            for record in records:
                if isinstance(record, dict):
                    # Collect Field ID
                    if 'field_id' in record:
                        field_ids.add(record['field_id'])
                    
                    # Collect field names
                    if 'field_path' in record:
                        field_path = record['field_path']
                        
                        # Extract the last level field name
                        if '.' in field_path:
                            field_name = field_path.split('.')[-1]
                        else:
                            field_name = field_path
                        
                        all_field_names.add(field_name)
                        
                        # Determine whether it is a reference field
                        if is_reference_field(field_name):
                            ref_field_names.add(field_name)
                            ie_ref_fields.add(field_name)
            
            # Record which referenced fields this IE contains
            for ref_name in ie_ref_fields:
                ref_field_to_ies[ref_name].append(filename)
        
        except Exception as e:
            print(f"Warning: Error processing {filename}: {e}")
    
    # Calculate citation relationship logarithms
    ref_pair_count = 0
    ref_pair_details = {}
    
    for ref_name, ie_list in ref_field_to_ies.items():
        n = len(ie_list)
        if n >= 2:
            pairs = n * (n - 1) // 2
            ref_pair_count += pairs
            ref_pair_details[ref_name] = {
                'ie_count': n,
                'pair_count': pairs
            }
    
    return {
        'ie_count': ie_count,
        'field_ids': field_ids,
        'ref_field_names': ref_field_names,
        'all_field_names': all_field_names,
        'ref_pair_count': ref_pair_count,
        'ref_pair_details': ref_pair_details,
        'ref_field_to_ies': ref_field_to_ies
    }

# ===============================
# Statistics show
# ===============================

def print_stats(label, stats):
    """Print statistical results"""
    print("="*80)
    print(f"{label} Statistics")
    print("="*80)
    
    print(f"\nIE Count: {stats['ie_count']}")
    print(f"Total Field: {len(stats['field_ids'])}")
    print(f"All Field Names: {len(stats['all_field_names'])}")
    print(f"Referenced Field Names: {len(stats['ref_field_names'])}")
    print(f"Reference Relationship Count: {stats['ref_pair_count']:,}")
    
    # Display Top Citation Fields
    if stats['ref_pair_details']:
        top_ref = sorted(stats['ref_pair_details'].items(),
                        key=lambda x: x[1]['pair_count'],
                        reverse=True)[:10]
        
        print(f"Top 10 Cited Fields (by Relationship Logarithm):")
        for ref_name, info in top_ref:
            print(f"  {ref_name:30s}: {info['ie_count']:3d}个IE, {info['pair_count']:4d}对关系")

# ===============================
# Comparative Analysis
# ===============================

def compare_stats(before_stats, after_stats):
    """Compare Before and After"""
    print("\n" + "="*80)
    print("Comparative analysis")
    print("="*80)
    
    # IE Quantity Comparison
    ie_reduction = (1 - after_stats['ie_count'] / before_stats['ie_count']) * 100
    print(f"Number of IEs:")
    print(f"  Before: {before_stats['ie_count']}")
    print(f"  After:  {after_stats['ie_count']}")
    print(f"Reduction: {ie_reduction:.1f}%")
    
    # Reference Relationship Logarithmic Comparison
    ref_pair_reduction = (1 - after_stats['ref_pair_count'] / before_stats['ref_pair_count']) * 100 if before_stats['ref_pair_count'] > 0 else 0
    print(f"Logarithm of citation relationships:")
    print(f"  Before: {before_stats['ref_pair_count']:,}")
    print(f"  After:  {after_stats['ref_pair_count']:,}")
    print(f"Reduction: {ref_pair_reduction:.1f}%")
    
    # Referenced field coverage rate
    ref_field_coverage = (len(after_stats['ref_field_names']) / len(before_stats['ref_field_names']) * 100) if len(before_stats['ref_field_names']) > 0 else 0
    print(f"Reference field coverage:")
    print(f"  Before: 100.0% ({len(before_stats['ref_field_names'])}个)")
    print(f"  After:  {ref_field_coverage:.1f}% ({len(after_stats['ref_field_names'])}个)")
    print(f"Decrease: {100 - ref_field_coverage:.1f}%")
    
    # Citation relationship coverage
    ref_pair_coverage = (after_stats['ref_pair_count'] / before_stats['ref_pair_count'] * 100) if before_stats['ref_pair_count'] > 0 else 0
    print(f"Citation relationship coverage:")
    print(f"After covers Before: {ref_pair_coverage:.1f}%")
    
    # Field name diversity
    field_name_coverage = (len(after_stats['all_field_names']) / len(before_stats['all_field_names']) * 100) if len(before_stats['all_field_names']) > 0 else 0
    print(f"Field name diversity:")
    print(f"  Before: {len(before_stats['all_field_names'])}个唯一字段名")
    print(f"  After:  {len(after_stats['all_field_names'])}个唯一字段名")
    print(f"Coverage: {field_name_coverage:.1f}%")
    
    # Regular field coverage
    field_coverage = (len(after_stats['field_ids']) / len(before_stats['field_ids']) * 100) if len(before_stats['field_ids']) > 0 else 0
    print(f"Message field coverage:")
    print(f"  Before: 100.0% ({len(before_stats['field_ids'])}字段)")
    print(f"  After:  {field_coverage:.1f}% ({len(after_stats['field_ids'])}字段)")
    print(f"Down: {100 - field_coverage:.1f}%")
    
    # Efficiency Analysis
    print(f"\n" + "="*80)
    print("Efficiency Analysis")
    print("="*80)
    
    print(f"\nwith {ie_reduction:.1f}% IE reduction")
    print(f"→ Achieved {ref_field_coverage:.1f}% reference field coverage")
    print(f"→ Achieved {ref_pair_coverage:.1f}% reference relationship coverage")
    
    if ref_field_coverage >= 90 and ref_pair_coverage >= 85:
        print("✅ Excellent trade-off!")
    elif ref_field_coverage >= 85 and ref_pair_coverage >= 80:
        print("✅ Good trade-off")
    else:
        print("⚠️ Trade-offs Required")
    
    return {
        'ie_reduction': ie_reduction,
        'ref_pair_reduction': ref_pair_reduction,
        'ref_field_coverage': ref_field_coverage,
        'ref_pair_coverage': ref_pair_coverage,
        'field_coverage': field_coverage
    }

# ===============================
# Generate Slides table
# ===============================

def generate_slide_table(before_stats, after_stats, comparison):
    """Generate tables suitable for Slides"""
    print("\n" + "="*80)
    print("Slides table (for copy and paste)")
    print("="*80)
    
    print(f"""
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **IE Count** | {before_stats['ie_count']} | {after_stats['ie_count']} | **{comparison['ie_reduction']:.0f}%** ↓ |
| **Ref. Pairs** | {before_stats['ref_pair_count']:,} | {after_stats['ref_pair_count']:,} | **{comparison['ref_pair_reduction']:.0f}%** ↓ |
| **Ref. Fields** | {len(before_stats['ref_field_names'])} | {len(after_stats['ref_field_names'])} | {100-comparison['ref_field_coverage']:.1f}% ↓ |
| **Field Coverage** | 100% | {comparison['field_coverage']:.1f}% | {100-comparison['field_coverage']:.1f}% ↓ |

**Ref. Field Coverage:** {comparison['ref_field_coverage']:.1f}%  
**Ref. Pair Coverage:** {comparison['ref_pair_coverage']:.1f}%  
**Trade-off:** Achieve {comparison['ref_pair_coverage']:.0f}% reference relationship coverage with {comparison['ie_reduction']:.0f}% IE reduction
""")

# ===============================
# Detailed comparison
# ===============================

def detailed_comparison(before_stats, after_stats):
    """Detailed citation field comparison"""
    print("\n" + "="*80)
    print("Detailed comparison of reference fields")
    print("="*80)
    
    # Find missing reference fields
    missing_ref_fields = before_stats['ref_field_names'] - after_stats['ref_field_names']
    
    if missing_ref_fields:
        print(f"\n⚠️  Missing reference fields ({len(missing_ref_fields)}):")
        
        # Sort by importance (number of IEs in which it appears)
        missing_with_importance = []
        for ref_name in missing_ref_fields:
            ie_count = len(before_stats['ref_field_to_ies'].get(ref_name, []))
            missing_with_importance.append((ref_name, ie_count))
        
        missing_with_importance.sort(key=lambda x: x[1], reverse=True)
        
        for ref_name, ie_count in missing_with_importance[:20]:
            print(f"{ref_name:30s}: appears in {ie_count:3d} IEs")
        
        if len(missing_ref_fields) > 20:
            print(f"... and {len(missing_ref_fields) - 20} more")
    else:
        print("✅ All referenced fields have been covered!")
    
    # Reserved reference fields
    kept_ref_fields = before_stats['ref_field_names'] & after_stats['ref_field_names']
    print(f"\n✅ Kept Referenced Fields: {len(kept_ref_fields)}/{len(before_stats['ref_field_names'])} ({len(kept_ref_fields)/len(before_stats['ref_field_names'])*100:.1f}%)")

# ===============================
# main function
# ===============================

def main():
    # Path Configuration
    before_dir = "../outputs/01_existASN_IEs_id"
    after_dir = "../outputs/inter-IE_strategy/selected_ies"
    
    # Allow command line arguments
    if len(sys.argv) > 1:
        before_dir = sys.argv[1]
    if len(sys.argv) > 2:
        after_dir = sys.argv[2]
    
    print("="*80)
    print("Inter-IE Coverage Check")
    print("="*80)
    print(f"Before directory: {before_dir}")
    print(f"After directory: {after_dir}")
    print(f"Reference field keywords: {REF_KEYWORDS}")
    print()
    
    # Statistics Before
    before_stats = load_ie_data(before_dir)
    if not before_stats:
        return
    
    print_stats("Before (01_existASN_IEs_id_inter)", before_stats)
    
    # Statistics After
    print()
    after_stats = load_ie_data(after_dir)
    if not after_stats:
        print(f"⚠️ After directory does not exist or is empty, only showing Before statistics")
        return
    
    print_stats("After (selected_ies)", after_stats)
    
    # Comparative Analysis
    comparison = compare_stats(before_stats, after_stats)
    
    # Detailed Comparison
    detailed_comparison(before_stats, after_stats)
    
    # Generate Slides Table
    generate_slide_table(before_stats, after_stats, comparison)
    
    print("\n" + "="*80)
    print("Done!")
    print("="*80)

if __name__ == "__main__":
    main()
