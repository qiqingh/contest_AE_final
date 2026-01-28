#!/usr/bin/env python3
"""
Summary and Analysis for Selected IEs
Reads greedy algorithm results and generates detailed analysis
"""
import json
import os
import sys
from collections import defaultdict

# ===============================
# 📁 PATH CONFIGURATION - MODIFY HERE
# ===============================

# Use relative path (script is in: intra-IE/code/intra-IE_strategy/)
OUTPUT_SELECTED_DIR = "../outputs/intra-IE_strategy/selected_ies"


# Convert to absolute path
if not os.path.isabs(OUTPUT_SELECTED_DIR):
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_SELECTED_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, OUTPUT_SELECTED_DIR))

# ===============================

def check_results():
    """Check if analysis results exist"""
    print(f"\n📁 Checking results directory:")
    print(f"   {OUTPUT_SELECTED_DIR}")
    
    if not os.path.exists(OUTPUT_SELECTED_DIR):
        print(f"\n❌ Error: Directory not found")
        return False
    
    summary_file = os.path.join(OUTPUT_SELECTED_DIR, '_summary.json')
    if not os.path.exists(summary_file):
        print(f"\n❌ Error: Summary file not found")
        print(f"   Expected: {summary_file}")
        return False
    
    print(f"   ✅ Found results")
    return True

def read_summary():
    """Read analysis summary"""
    summary_file = os.path.join(OUTPUT_SELECTED_DIR, '_summary.json')
    
    with open(summary_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Support different formats
    if 'statistics' in data:
        # v3 format
        stats = data['statistics']
        return {
            'label': data.get('label', 'Unknown'),
            'parameters': data.get('parameters', {}),
            'total_ies': stats['total_ies'],
            'total_pairs': stats['total_pairs'],
            'coverage': stats.get('coverage', 0),
            'covered_fields': stats.get('covered_fields', 0),
            'ie_list': data.get('ie_list', [])
        }
    else:
        # v2 format
        return data

def generate_summary(summary):
    """Generate summary report"""
    print("\n" + "="*80)
    print("📊 Selected IE Summary")
    print("="*80)
    
    print(f"\nStrategy: {summary['label']}")
    
    # Parameters
    if 'parameters' in summary and summary['parameters']:
        params = summary['parameters']
        print(f"Parameters: min_fields={params.get('min_fields', 'N/A')}, "
              f"max_fields={params.get('max_fields', 'N/A')}")
    
    # Core statistics
    total_ies = summary['total_ies']
    total_pairs = summary['total_pairs']
    
    print(f"\nCore Statistics:")
    print(f"  ✅ Selected IEs: {total_ies}")
    print(f"  ✅ Field pairs: {total_pairs:,}")
    print(f"  ✅ Avg pairs/IE: {total_pairs//total_ies if total_ies > 0 else 0}")
    
    if 'coverage' in summary and summary['coverage'] > 0:
        print(f"  ✅ Field coverage: {summary['coverage']:.1f}%")
    
    # Cost estimation
    cost_low = total_pairs * 0.01
    cost_high = total_pairs * 0.03
    time_hours = total_pairs / 1000
    
    print(f"\nEstimated Cost:")
    print(f"  💰 LLM queries: ${cost_low:.0f} - ${cost_high:.0f}")
    print(f"  ⏱️ Time: ~{time_hours:.1f} hours")
    
    # Comparison with brute force
    brute_pairs = 65000
    savings = (1 - total_pairs/brute_pairs) * 100
    print(f"\nComparison with Brute Force:")
    print(f"  📉 Pairs: {brute_pairs:,} → {total_pairs:,}")
    print(f"  📊 Reduction: {savings:.1f}%")
    
    return cost_low, cost_high

def analyze_distribution(summary):
    """Analyze IE distribution"""
    print("\n" + "="*80)
    print("📊 IE Distribution")
    print("="*80)
    
    ie_list = summary.get('ie_list', [])
    
    if not ie_list:
        print("  ⚠️ No IE list available")
        return
    
    # Group by field count
    field_groups = defaultdict(list)
    
    for ie in ie_list:
        num_fields = ie.get('num_fields', 0)
        if num_fields <= 5:
            group = '3-5 fields'
        elif num_fields <= 10:
            group = '6-10 fields'
        elif num_fields <= 15:
            group = '11-15 fields'
        else:
            group = '>15 fields'
        field_groups[group].append(ie)
    
    print(f"\nBy Field Count:")
    for group in ['3-5 fields', '6-10 fields', '11-15 fields', '>15 fields']:
        if group in field_groups:
            ies = field_groups[group]
            total_pairs = sum(ie.get('num_pairs', 0) for ie in ies)
            print(f"  {group:<12s}: {len(ies):3d} IEs, {total_pairs:5,d} pairs")
    
    # Keyword statistics
    with_keywords = sum(1 for ie in ie_list if ie.get('has_keyword', False))
    pct = with_keywords/len(ie_list)*100 if ie_list else 0
    print(f"\nKeyword Analysis:")
    print(f"  IEs with keywords: {with_keywords}/{len(ie_list)} ({pct:.1f}%)")
    
    # Top 10 contributors
    sorted_ies = sorted(ie_list, key=lambda x: x.get('num_pairs', 0), reverse=True)
    print(f"\nTop 10 IEs (by pair count):")
    for i, ie in enumerate(sorted_ies[:10], 1):
        ie_name = ie.get('ie_name', ie.get('filename', 'unknown'))
        num_fields = ie.get('num_fields', 0)
        num_pairs = ie.get('num_pairs', 0)
        print(f"  {i:2d}. {ie_name[:45]:45s} ({num_fields:2d} fields, {num_pairs:3d} pairs)")

def give_recommendations(summary, cost_low, cost_high):
    """Provide recommendations"""
    print("\n" + "="*80)
    print("💡 Recommendations")
    print("="*80)
    
    total_pairs = summary['total_pairs']
    
    if total_pairs < 3000:
        print("\n✅ Very conservative (low cost)")
        print("  - Can start immediately")
        print("  - Verify coverage is sufficient")
    elif total_pairs < 5000:
        print("\n✅ Recommended (balanced)")
        print(f"  - Cost: ${cost_low:.0f}-${cost_high:.0f}")
        print("  - Good coverage")
        print("  - Ready for Toolchain 3")
    elif total_pairs < 7000:
        print("\n⚠️ Slightly aggressive")
        print("  - Higher cost but acceptable")
        print("  - Consider batch processing")
    else:
        print("\n⚠️ Too many pairs")
        print("  - Cost may be high")
        print("  - Consider stricter parameters")
    
    print(f"\n🚀 Next Steps:")
    print(f"  1. Verify coverage (optional)")
    print(f"  2. Start Toolchain 3 (field pair extraction)")
    print(f"  3. Context extraction from specifications")
    print(f"  4. LLM constraint generation")

def main():
    print("="*80)
    print("Toolchain 2 - Results Summary")
    print("="*80)
    
    # Check results
    if not check_results():
        print(f"\n💡 First run: python3 greedy_set_cover_v3.py")
        return
    
    # Read summary
    try:
        summary = read_summary()
    except Exception as e:
        print(f"\n❌ Error reading summary: {e}")
        return
    
    # Generate analyses
    cost_low, cost_high = generate_summary(summary)
    analyze_distribution(summary)
    give_recommendations(summary, cost_low, cost_high)
    
    # Final summary
    print("\n" + "="*80)
    print("✅ Summary Complete")
    print("="*80)
    
    print(f"\nResults:")
    print(f"  Selected IEs: {summary['total_ies']}")
    print(f"  Field pairs: {summary['total_pairs']:,}")
    if 'coverage' in summary and summary['coverage'] > 0:
        print(f"  Coverage: {summary['coverage']:.1f}%")
    
    print(f"\nLocation:")
    print(f"  {OUTPUT_SELECTED_DIR}")

if __name__ == "__main__":
    main()