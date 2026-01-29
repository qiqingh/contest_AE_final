#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inter-IE Radical Optimization Cluster Configuration Generator
Goal: Reduce from 23,987 IE pairs to 5,000-8,000 pairs, processing time 6-10 hours

Strategy:
1. Prohibit all intra-cluster pairs (same configuration families should be handled at Intra-IE)
   EXCEPT: C2_PDCCH cluster (contains critical SearchSpace-ControlResourceSet constraints)
2. Only retain the most core cross-cluster pairs
3. Apply sampling or restriction strategies to large clusters
"""

import json
import os
import glob
from pathlib import Path

# ============================================================================
# Path Configuration (modify here)
# ============================================================================

# Inter-IE's IE Directory (295 Fine-grained IE)
INTER_IE_DIR = "../../../toolchain2_IE_collection/inter-IE/outputs/inter-IE_strategy/selected_ies"

# Output path
OUTPUT_CONFIG = "./cluster_config_aggressive_inter_ie.json"

# ============================================================================
# Optimize parameters
# ============================================================================

# Whether to prohibit all internal pairs within the cluster
DISABLE_ALL_INTRA_CLUSTER = True

# Critical intra-cluster pairs to preserve (even when DISABLE_ALL_INTRA_CLUSTER is True)
# C2_PDCCH: Contains essential SearchSpace-ControlResourceSet reference relationships
# C6_CSI_RS: Contains CSI measurement configuration reference chains
# C4_PUSCH: Contains power control parameter references
PRESERVE_CRITICAL_INTRA_CLUSTERS = ["C2_PDCCH", "C6_CSI_RS", "C4_PUSCH"]  # Modify this list to add/remove clusters

# Whether to use extended pairs (if False, only use core pairs)
ENABLE_EXTENDED_PAIRS = True

# Whether to enable restrictions for very large cluster pairs (to prevent combinatorial explosion)
ENABLE_LARGE_CLUSTER_LIMIT = True
MAX_PAIR_SIZE = 2500  # Maximum number of IE pairs for a single cluster pair

# ============================================================================
# Cluster Classification Rules
# ============================================================================

def classify_ie(ie_name):
    """Classify by IE name into clusters"""
    name_lower = ie_name.lower()
    
    # Remove number prefix
    parts = ie_name.split('_')
    clean_parts = [p for p in parts if not p.isdigit()]
    clean_name = '_'.join(clean_parts)
    name_lower = clean_name.lower()
    
    # Classification Logic (Priority from High to Low)
    if 'rlc' in name_lower:
        return 'C8_RLC'
    elif 'mac' in name_lower or 'tag' in name_lower or 'logicalchannel' in name_lower:
        return 'C7_MAC'
    elif 'csi' in name_lower or 'srs' in name_lower or 'codebook' in name_lower or 'nzp' in name_lower:
        return 'C6_CSI_RS'
    elif 'pucch' in name_lower:
        return 'C5_PUCCH'
    elif 'pusch' in name_lower:
        return 'C4_PUSCH'
    elif 'pdsch' in name_lower:
        return 'C3_PDSCH'
    elif 'pdcch' in name_lower or 'controlresourceset' in name_lower or 'searchspace' in name_lower:
        return 'C2_PDCCH'
    elif 'bwp' in name_lower or 'downlink' in name_lower or 'uplink' in name_lower or 'servingcell' in name_lower:
        return 'C1_BWP_ServingCell'
    
    return 'C_OTHER'

# ============================================================================
# Cluster Pair Strategy Configuration
# ============================================================================

def get_core_cluster_pairs():
    """
    Core cross-cluster pairs (must be retained)
    Core reference relationships based on 3GPP protocols
    """
    return [
        # Physical layer scheduling relationship (core)
        ["C2_PDCCH", "C3_PDSCH"],     # PDCCH schedules PDSCH
        ["C2_PDCCH", "C5_PUCCH"],     # PDCCH allocates PUCCH resources
        
        # Physical Layer and Measurements (Core)
        ["C3_PDSCH", "C6_CSI_RS"],    # PDSCH uses CSI measurement
        ["C4_PUSCH", "C6_CSI_RS"],    # PUSCH uses SRS
        
        # Upper layer protocols and physical layer (core)
        ["C8_RLC", "C3_PDSCH"],       # RLC carrying PDSCH data
        ["C8_RLC", "C4_PUSCH"],       # RLC bearer PUSCH data
        ["C7_MAC", "C5_PUCCH"],       # MAC scheduling PUCCH
        ["C7_MAC", "C4_PUSCH"],       # MAC schedules PUSCH
    ]

def get_extended_cluster_pairs():
    """
    Extend cross-cluster pairs (optional)
    """
    return [
        # Physical Layer Combination
        ["C4_PUSCH", "C5_PUCCH"],     # PUSCH and PUCCH
        ["C2_PDCCH", "C4_PUSCH"],     # PDCCH and PUSCH
        
        # BWP related
        ["C1_BWP_ServingCell", "C2_PDCCH"],
        ["C1_BWP_ServingCell", "C3_PDSCH"],
        ["C1_BWP_ServingCell", "C4_PUSCH"],
        
        # CSI Additional Portfolio
        ["C5_PUCCH", "C6_CSI_RS"],    # PUCCH and CSI
        ["C2_PDCCH", "C6_CSI_RS"],    # PDCCH and CSI
        
        # MAC/RLC Extension
        ["C7_MAC", "C3_PDSCH"],
        ["C7_MAC", "C2_PDCCH"],
        ["C8_RLC", "C5_PUCCH"],
    ]

# ============================================================================
# Main logic
# ============================================================================

def check_cluster_pair_size(c1_size, c2_size, max_size):
    """
    Check if cluster pairs exceed the limit
    Return: (whether allowed, actual IE logarithm, recommendation)
    """
    pair_count = c1_size * c2_size
    
    if pair_count <= max_size:
        return True, pair_count, "Allow"
    else:
        # Calculate the required sampling ratio
        sample_ratio = max_size / pair_count
        return False, pair_count, f"Limit exceeded (recommend sampling {sample_ratio*100:.0f}%)"

def main():
    print("="*70)
    print("Inter-IE Aggressive Optimization Cluster Configuration Generator")
    print("="*70)
    
    print(f"Goal:")
    print(f"- Reduced from ~24,000 IE pairs to 5,000-8,000")
    print(f"Processing time: 6-10 hours")
    print(f"- Only retain the most essential citation relationships")
    
    print(f"\nOptimization Strategy:")
    print(f"- Prohibit all intra-cluster pairs: {DISABLE_ALL_INTRA_CLUSTER}")
    if PRESERVE_CRITICAL_INTRA_CLUSTERS:
        print(f"- EXCEPT critical clusters: {', '.join(PRESERVE_CRITICAL_INTRA_CLUSTERS)}")
    print(f"- Enable extended pairs: {ENABLE_EXTENDED_PAIRS}")
    print(f"- Limit large cluster pairs: {ENABLE_LARGE_CLUSTER_LIMIT}")
    if ENABLE_LARGE_CLUSTER_LIMIT:
        print(f"  Maximum single pair limit: {MAX_PAIR_SIZE}")
    
    print(f"\nConfiguration:")
    print(f"Inter-IE directory: {INTER_IE_DIR}")
    print(f"Output Configuration: {OUTPUT_CONFIG}")
    
    # Verification Directory
    if not os.path.exists(INTER_IE_DIR):
        print(f"\n❌ Error: Inter-IE directory does not exist")
        print(f"   {INTER_IE_DIR}")
        return
    
    # Scan IE directory
    ie_files = glob.glob(os.path.join(INTER_IE_DIR, "*.json"))
    ie_files = [f for f in ie_files if not os.path.basename(f).startswith('_')]
    
    print(f"\nScanning IE directory:")
    print(f"Found {len(ie_files)} IE files")
    
    # Initialize clusters
    clusters = {
        'C1_BWP_ServingCell': [],
        'C2_PDCCH': [],
        'C3_PDSCH': [],
        'C4_PUSCH': [],
        'C5_PUCCH': [],
        'C6_CSI_RS': [],
        'C7_MAC': [],
        'C8_RLC': [],
    }
    
    # Classify each IE
    other_ies = []
    for ie_file in sorted(ie_files):
        basename = os.path.basename(ie_file)
        ie_name = os.path.splitext(basename)[0]
        
        cluster = classify_ie(ie_name)
        if cluster == 'C_OTHER':
            other_ies.append(ie_name)
        else:
            clusters[cluster].append(ie_name)
    
    # Display categorization results
    print(f"\nClassification results:")
    total_ies = 0
    for cluster, ies in sorted(clusters.items()):
        count = len(ies)
        total_ies += count
        print(f"  {cluster:20s}: {count:3d} IE")
    
    if other_ies:
        print(f"  {'Uncategorized':20s}: {len(other_ies):3d} IE")
    
    print(f"  {'Total':20s}: {total_ies:3d} IE")
    
    # Remove empty clusters
    clusters = {k: v for k, v in clusters.items() if v}
    
    # Get core and extended cluster pairs
    core_pairs = get_core_cluster_pairs()
    extended_pairs = get_extended_cluster_pairs() if ENABLE_EXTENDED_PAIRS else []
    
    # Filter out pairs involving empty clusters
    def filter_valid_pairs(pairs):
        return [[c1, c2] for c1, c2 in pairs if c1 in clusters and c2 in clusters]
    
    core_pairs = filter_valid_pairs(core_pairs)
    extended_pairs = filter_valid_pairs(extended_pairs)
    
    # Check and filter oversized cluster pairs
    final_pairs = []
    skipped_pairs = []
    
    print(f"\n{'='*70}")
    print(f"Cluster Pair Analysis and Screening")
    print(f"{'='*70}")
    
    print(f"\nCore cross-cluster pairs:")
    for c1, c2 in core_pairs:
        c1_size = len(clusters[c1])
        c2_size = len(clusters[c2])
        
        if ENABLE_LARGE_CLUSTER_LIMIT:
            allowed, pair_count, suggestion = check_cluster_pair_size(c1_size, c2_size, MAX_PAIR_SIZE)
            
            if allowed:
                final_pairs.append([c1, c2])
                print(f"  ✓ {c1:20s} × {c2:20s}: {c1_size:3d} × {c2_size:3d} = {pair_count:5d}")
            else:
                skipped_pairs.append([c1, c2, pair_count, suggestion])
                print(f"  ✗ {c1:20s} × {c2:20s}: {c1_size:3d} × {c2_size:3d} = {pair_count:5d} ({suggestion})")
        else:
            pair_count = c1_size * c2_size
            final_pairs.append([c1, c2])
            print(f"  ✓ {c1:20s} × {c2:20s}: {c1_size:3d} × {c2_size:3d} = {pair_count:5d}")
    
    if ENABLE_EXTENDED_PAIRS:
        print(f"\nExpand cross-cluster pairs:")
        for c1, c2 in extended_pairs:
            c1_size = len(clusters[c1])
            c2_size = len(clusters[c2])
            
            if ENABLE_LARGE_CLUSTER_LIMIT:
                allowed, pair_count, suggestion = check_cluster_pair_size(c1_size, c2_size, MAX_PAIR_SIZE)
                
                if allowed:
                    final_pairs.append([c1, c2])
                    print(f"  ✓ {c1:20s} × {c2:20s}: {c1_size:3d} × {c2_size:3d} = {pair_count:5d}")
                else:
                    skipped_pairs.append([c1, c2, pair_count, suggestion])
                    print(f"  ✗ {c1:20s} × {c2:20s}: {c1_size:3d} × {c2_size:3d} = {pair_count:5d} ({suggestion})")
            else:
                pair_count = c1_size * c2_size
                final_pairs.append([c1, c2])
                print(f"  ✓ {c1:20s} × {c2:20s}: {c1_size:3d} × {c2_size:3d} = {pair_count:5d}")
    
    # ============================================================================
    # Critical modification: Preserve intra-cluster pairs for critical clusters
    # ============================================================================
    # Reason: C2_PDCCH contains essential SearchSpace-ControlResourceSet constraints
    # that are referenced in the paper case study (3GPP TS 38.213 §10.1)
    # ============================================================================
    if DISABLE_ALL_INTRA_CLUSTER:
        # Even when disabling intra-cluster pairs, preserve critical ones
        allowed_intra = [c for c in PRESERVE_CRITICAL_INTRA_CLUSTERS if c in clusters]
        if allowed_intra:
            print(f"\n⚠️  Note: Preserving critical intra-cluster pairs:")
            for cluster in allowed_intra:
                n = len(clusters[cluster])
                intra_pairs = n * (n - 1) // 2
                print(f"  → {cluster}: {n} IEs, {intra_pairs:,} intra-pairs")
                print(f"     Reason: Contains essential protocol constraints")
    else:
        # If not disabling, include both critical and default clusters
        allowed_intra = list(set(PRESERVE_CRITICAL_INTRA_CLUSTERS + ["C7_MAC"]))
        allowed_intra = [c for c in allowed_intra if c in clusters]
    
    # Build complete configuration
    config = {
        "clusters": clusters,
        "allowed_cluster_pairs": final_pairs,
        "allow_intra_cluster_pairs": allowed_intra,
        "optimization_info": {
            "strategy": "aggressive_dedup_with_critical_intra",
            "target_pairs": "5000-8000",
            "target_time": "6-10 hours",
            "disable_all_intra": DISABLE_ALL_INTRA_CLUSTER,
            "critical_intra_clusters": PRESERVE_CRITICAL_INTRA_CLUSTERS,
            "enable_extended": ENABLE_EXTENDED_PAIRS,
            "large_cluster_limit": ENABLE_LARGE_CLUSTER_LIMIT,
            "max_pair_size": MAX_PAIR_SIZE if ENABLE_LARGE_CLUSTER_LIMIT else None
        },
        "skipped_pairs": [
            {"cluster1": c1, "cluster2": c2, "pair_count": count, "reason": reason}
            for c1, c2, count, reason in skipped_pairs
        ]
    }
    
    # Calculate total IE logarithm
    total_pairs = 0
    intra_pairs_count = 0
    
    for c1, c2 in final_pairs:
        pairs = len(clusters[c1]) * len(clusters[c2])
        total_pairs += pairs
    
    for cluster in allowed_intra:
        n = len(clusters[cluster])
        if n >= 2:
            pairs = n * (n - 1) // 2
            total_pairs += pairs
            intra_pairs_count += pairs
    
    # Display skipped pairs
    if skipped_pairs:
        print(f"\n⚠️  Skipped oversized cluster pairs:")
        skipped_total = 0
        for c1, c2, count, reason in skipped_pairs:
            skipped_total += count
            print(f"  {c1:20s} × {c2:20s}: {count:5d} pairs ({reason})")
        print(f"  Total saved: {skipped_total:,} pairs")
    
    print(f"\n{'='*70}")
    print(f"Final Statistics")
    print(f"{'='*70}")
    print(f"Cross-cluster pairs: {total_pairs - intra_pairs_count:,}")
    print(f"Intra-cluster pairs: {intra_pairs_count:,}")
    print(f"Total IE pairs: {total_pairs:,}")
    print(f"{'='*70}")
    
    # Comparison
    baseline_total = 23987  # The result from last time
    reduction = (baseline_total - total_pairs) / baseline_total * 100
    
    print(f"\nComparison:")
    print(f"  Previous (Moderate Optimization): {baseline_total:,} pairs")
    print(f"  This time (Aggressive + Critical): {total_pairs:,} pairs")
    print(f"  Reduction: {baseline_total - total_pairs:,} pairs ({reduction:.1f}%)")
    
    # Check if within target range
    if 5000 <= total_pairs <= 8000:
        print(f"  ✅ Within target range (5,000-8,000)")
    elif total_pairs < 5000:
        print(f"  ⚠️  Below target minimum (you can add some extension pairs or increase the limit)")
    else:
        print(f"  ⚠️  Exceeds target limit (requires more aggressive restrictions)")
        print(f"  Recommendation: Reduce MAX_PAIR_SIZE to {int(MAX_PAIR_SIZE * 5000 / total_pairs)}")
    
    # Save Configuration
    with open(OUTPUT_CONFIG, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    # Estimated processing time
    specs_per_pair = 8
    seconds_per_spec = 3
    workers = 8
    total_seconds = total_pairs * specs_per_pair * seconds_per_spec / workers
    hours = total_seconds / 3600
    
    print(f"\nEstimated processing time:")
    print(f"  Specification files/pair: {specs_per_pair}")
    print(f"  Processing time/file: {seconds_per_spec} seconds")
    print(f"  Parallel cores: {workers}")
    print(f"  Estimated total time: {hours:.1f} hours")
    
    if 6 <= hours <= 10:
        print(f"  ✅ Within target range (6-10 hours)")
    elif hours < 6:
        print(f"  💡 Below expectations (consider adding more valuable pairs)")
    else:
        print(f"  ⚠️  Exceeds expectations (requires further optimization)")
    
    print(f"\nEstimated constraints: ~{total_pairs * 50:,}")
    
    print(f"\n{'='*70}")
    print(f"✅ Generation complete")
    print(f"{'='*70}")
    
    print(f"\nConfiguration saved: {OUTPUT_CONFIG}")
    
    if skipped_pairs:
        print(f"\n⚠️  Warning: {len(skipped_pairs)} cluster pairs were skipped due to exceeding limits")
        print(f"   If you need to include these pairs, please:")
        print(f"   1. Increase MAX_PAIR_SIZE")
        print(f"   2. Or set ENABLE_LARGE_CLUSTER_LIMIT = False")
    
    print(f"\nNext steps:")
    print(f"  1. Review the statistics above")
    print(f"  2. If satisfied: mv {OUTPUT_CONFIG} cluster_config.json")
    print(f"  3. Run: python3 inter_ie_enhanced_extractor_fixed.py")
    print(f"  4. Expected processing time: {hours:.1f} hours")

if __name__ == "__main__":
    main()