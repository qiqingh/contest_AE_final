#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inter-IE Field Pair Global Aggregator - FINAL VERSION
Cross-IE Field Global Aggregator - Final Version
========================

Output format:
{
  "ie_pair": ["ie1_name", "ie2_name"],
  "field_pair": ["field1", "field2"],
  "field_ids": {
    "field1_all": [71, 136, 154, ...],       // All field1 IDs
    "field2_all": [71, 89, 136, ...],        // All field2 IDs
    "actual_pairs": [                        // Actually existing pairs
      [[71], [89]],
      [[136], [154]]
    ]
  },
  "evidences": [...],
  "confidence_counts": {...},
  "section_counts": {...},
  "source_file_counts": {...}
}

Expected results:
- Input: ~120,000 constraint entries
- Output: ~4,000 unique Inter-IE field pairs
- Avoidance Rate: >90% combinatorial explosion avoidance
"""

import json
import os
import glob
import re
from typing import Dict, List, Tuple, Set, Optional
from collections import defaultdict, Counter
from pathlib import Path
import hashlib
from datetime import datetime

# ============================================================================
# Configuration Area
# ============================================================================

# Input path
CONSTRAINTS_DIR = "../../../toolchain3_field_pair_context_extraction/inter-IE/output/context_enhanced"

# Output path
OUTPUT_DIR = "../output/inter_ie_aggregated"
AGGREGATED_FILE = "aggregated_inter_ie_field_pairs.json"
SUMMARY_FILE = "aggregation_summary.json"
DIAGNOSIS_FILE = "aggregation_diagnosis.txt"

# Aggregation Configuration
NORMALIZE_FIELD_NAMES = True  # Whether to standardize field names (remove case and hyphen differences)
NORMALIZE_IE_NAMES = True  # Whether to standardize IE names
DEDUPLICATE_EVIDENCES = True  # Whether to deduplicate similar evidence
EVIDENCE_SIMILARITY_THRESHOLD = 1.0  # Evidence similarity threshold (kept for compatibility)

# Debug mode
DEBUG_MODE = False
VERBOSE = True  # Show detailed progress

# ============================================================================
# Helper function
# ============================================================================

def log_diagnosis(message: str):
    """Record diagnostic information"""
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(os.path.join(OUTPUT_DIR, DIAGNOSIS_FILE), 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    except Exception as e:
        print(f"⚠️  Failed to write diagnosis: {e}")


def normalize_ie_name(ie_name: str) -> str:
    """
    Standardized IE Name
    
    Rules:
    1. Convert to lowercase
    2. Standardize hyphen format
    """
    if not ie_name:
        return ""
    
    if NORMALIZE_IE_NAMES:
        ie_name = ie_name.lower()
        # Unified format: camelCase -> camel-case
        ie_name = re.sub(r'([a-z])([A-Z])', r'\1-\2', ie_name).lower()
    
    return ie_name.strip()


def normalize_field_name(field_name: str) -> str:
    """
    Standardized field names
    
    Rules:
    1. Convert to lowercase
    2. Remove hyphens and underscores
    3. Remove array index [0]
    """
    if not field_name:
        return ""
    
    # Remove array index
    field_name = re.sub(r'\[\d+\]', '', field_name)
    
    if NORMALIZE_FIELD_NAMES:
        # convert to lowercase
        field_name = field_name.lower()
        # Preserve hyphens and underscores (not completely removed, maintain readability)
        # But use a unified format: camelCase -> camel-case
        field_name = re.sub(r'([a-z])([A-Z])', r'\1-\2', field_name).lower()
    
    return field_name.strip()


def create_inter_ie_key(ie1: str, field1: str, ie2: str, field2: str) -> Tuple[str, str, str, str]:
    """
    Create unique key (quadruple) for Inter-IE field pair
    
    Rules:
    1. Standardize IE names and field names
    2. Sort in lexicographic order (to ensure consistency)
    
    Return: (norm_ie1, norm_field1, norm_ie2, norm_field2)
           or (norm_ie2, norm_field2, norm_ie1, norm_field1)
           depends on which lexicographical order is smaller
    """
    norm_ie1 = normalize_ie_name(ie1)
    norm_field1 = normalize_field_name(field1)
    norm_ie2 = normalize_ie_name(ie2)
    norm_field2 = normalize_field_name(field2)
    
    # Sort in dictionary order to ensure consistency
    pair1 = (norm_ie1, norm_field1, norm_ie2, norm_field2)
    pair2 = (norm_ie2, norm_field2, norm_ie1, norm_field1)
    
    return pair1 if pair1 <= pair2 else pair2


def extract_ie_names_from_source_ies(source_ies: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract IE names from the source_IEs field
    
    Input format: ["19_25_mac-LogicalChannelConfig", "88_229_commonSearchSpaceList"]
    Output: ("mac-LogicalChannelConfig", "commonSearchSpaceList")
    """
    try:
        if not source_ies or len(source_ies) < 2:
            return None, None
        
        ie1_str = source_ies[0]
        ie2_str = source_ies[1]
        
        # Extract IE names (remove preceding numbers)
        # Pattern: Number_Number_IE Name
        pattern = r'^\d+_\d+_(.+)$'
        
        match1 = re.search(pattern, ie1_str)
        match2 = re.search(pattern, ie2_str)
        
        if match1 and match2:
            return match1.group(1), match2.group(1)
        
        # If no match is found, try using directly (may already be IE name)
        return ie1_str, ie2_str
        
    except Exception as e:
        log_diagnosis(f"Error extracting IE names from source_IEs: {e}")
        return None, None


def normalize_text(text: str) -> str:
    """
    Standardized text used for deduplication comparison
    
    Rule:
    Remove leading and trailing whitespace
    2. Normalize internal whitespace (multiple spaces -> single space)
    3. Convert to lowercase
    """
    if not isinstance(text, str):
        return ""
    
    # Basic cleaning
    text = text.strip()
    text = ' '.join(text.split())  # Normalize whitespace characters
    text = text.lower()
    
    return text


def is_evidence_duplicate(evidence: Dict, existing_evidences: List[Dict]) -> bool:
    """
    Check if evidence duplicates with existing ones
    
    Deduplication based solely on exact matching of text content!
    """
    text = normalize_text(evidence.get('text', ''))
    
    if not text:
        return False
    
    for existing in existing_evidences:
        existing_text = normalize_text(existing.get('text', ''))
        
        # Only identical text counts as duplicate
        if text == existing_text:
            return True
    
    return False


# ============================================================================
# Core aggregate functions
# ============================================================================

def aggregate_inter_ie_field_pairs(constraint_files: List[str]) -> Tuple[Dict, int, int]:
    """
    Global aggregation of all Inter-IE field pairs
    
    Key: Use quadruple (IE1, field1, IE2, field2) as key
    
    Return:
    {
      (ie1, field1, ie2, field2): {
        "ie_pair": [ie1, ie2],
        "field_pair": [field1, field2],
        "original_ie_names": set(),
        "original_field_names": set(),
        "field_ids": {
          "ie1_field1": [[...], [...]],  # multiple possible field_ids
          "ie2_field2": [[...], [...]]
        },
        "evidences": [...],
        "stats": {...}
      }
    }
    """
    global_map = {}
    
    total_files = len(constraint_files)
    total_constraints = 0
    skipped_files = 0
    empty_files = 0
    
    print(f"\n🔄 Processing {total_files} constraint files...")
    
    for file_idx, file_path in enumerate(constraint_files, 1):
        if VERBOSE and file_idx % 100 == 0:
            print(f"  Progress: {file_idx}/{total_files} files processed...")
        
        try:
            # Load file
            with open(file_path, 'r', encoding='utf-8') as f:
                constraints = json.load(f)
            
            # Check empty files
            if not constraints:
                empty_files += 1
                if DEBUG_MODE:
                    log_diagnosis(f"Empty file: {file_path}")
                continue
            
            if not isinstance(constraints, list):
                log_diagnosis(f"Invalid format (not list): {file_path}")
                skipped_files += 1
                continue
            
            # Process each constraint
            for constraint in constraints:
                if not isinstance(constraint, dict):
                    continue
                
                # Validate required fields
                if 'fields' not in constraint or not isinstance(constraint['fields'], list):
                    continue
                
                if len(constraint['fields']) < 2:
                    continue
                
                # Extract IE name
                source_ies = constraint.get('source_IEs', [])
                ie1, ie2 = extract_ie_names_from_source_ies(source_ies)
                
                if not ie1 or not ie2:
                    if DEBUG_MODE:
                        log_diagnosis(f"Cannot extract IE names from: {source_ies}")
                    continue
                
                total_constraints += 1
                
                field1, field2 = constraint['fields'][0], constraint['fields'][1]
                
                # Create quadruple key
                inter_ie_key = create_inter_ie_key(ie1, field1, ie2, field2)
                
                # Initialize field pair entry
                if inter_ie_key not in global_map:
                    global_map[inter_ie_key] = {
                        "ie_pair": [inter_ie_key[0], inter_ie_key[2]],  # Standardized IE name
                        "field_pair": [inter_ie_key[1], inter_ie_key[3]],  # Standardized field names
                        "original_ie_names": set(),  # Original IE name (case preserved)
                        "original_field_names": set(),  # Original field name (preserve case)
                        "field_ids": {
                            "ie1_field1": [],  # All possible field_ids for field1 of IE1 (temporary storage)
                            "ie2_field2": [],  # All possible field_ids for field2 of IE2 (temporary storage)
                            "actual_pairs": []  # Real existing field_id pairs
                        },
                        "evidences": [],
                        "confidence_counts": Counter(),
                        "section_counts": Counter(),
                        "source_file_counts": Counter()
                    }
                
                entry = global_map[inter_ie_key]
                
                # Add original name (preserve case)
                entry["original_ie_names"].add((ie1, ie2))
                entry["original_field_names"].add((field1, field2))
                
                # Extract and save field_ids
                field_ids = constraint.get('field_ids', [])
                if field_ids and len(field_ids) >= 2:
                    # field_ids format: [[ie1_field1_ids], [ie2_field2_ids]]
                    ie1_field_ids = field_ids[0] if isinstance(field_ids[0], list) else [field_ids[0]]
                    ie2_field_ids = field_ids[1] if isinstance(field_ids[1], list) else [field_ids[1]]
                    
                    # Add to temporary collection (deduplicate)
                    if ie1_field_ids not in entry["field_ids"]["ie1_field1"]:
                        entry["field_ids"]["ie1_field1"].append(ie1_field_ids)
                    if ie2_field_ids not in entry["field_ids"]["ie2_field2"]:
                        entry["field_ids"]["ie2_field2"].append(ie2_field_ids)
                    
                    # 🔥 Record real existing field_id pairings
                    actual_pair = [ie1_field_ids, ie2_field_ids]
                    if actual_pair not in entry["field_ids"]["actual_pairs"]:
                        entry["field_ids"]["actual_pairs"].append(actual_pair)
                
                # construct evidence
                evidence = {
                    "text": constraint.get('original_sentence', ''),
                    "confidence": constraint.get('confidence', 'UNKNOWN'),
                    "section_number": constraint.get('section_number', ''),
                    "section_title": constraint.get('section_title', ''),
                    "source_file": constraint.get('source_file', ''),
                    "source_ies": source_ies,
                    "field_ids": field_ids,
                    "section_relevance": constraint.get('section_relevance', {})
                }
                
                # Duplicate check
                if DEDUPLICATE_EVIDENCES:
                    if not is_evidence_duplicate(evidence, entry["evidences"]):
                        entry["evidences"].append(evidence)
                        # Update Statistics
                        entry["confidence_counts"][evidence['confidence']] += 1
                        if evidence['section_number']:
                            entry["section_counts"][evidence['section_number']] += 1
                        if evidence['source_file']:
                            entry["source_file_counts"][evidence['source_file']] += 1
                else:
                    entry["evidences"].append(evidence)
                    entry["confidence_counts"][evidence['confidence']] += 1
                    if evidence['section_number']:
                        entry["section_counts"][evidence['section_number']] += 1
                    if evidence['source_file']:
                        entry["source_file_counts"][evidence['source_file']] += 1
        
        except json.JSONDecodeError as e:
            log_diagnosis(f"JSON decode error in {file_path}: {e}")
            skipped_files += 1
        except Exception as e:
            log_diagnosis(f"Error processing {file_path}: {e}")
            skipped_files += 1
    
    print(f"  ✅ Processed {total_files - skipped_files - empty_files}/{total_files} files")
    print(f"  📊 Total constraint entries: {total_constraints}")
    if empty_files > 0:
        print(f"  📝 Empty files skipped: {empty_files}")
    if skipped_files > 0:
        print(f"  ⚠️  Error files skipped: {skipped_files} (see diagnosis log)")
    
    # Convert sets to lists (for JSON serialization)
    for key, entry in global_map.items():
        entry["original_ie_names"] = list(entry["original_ie_names"])
        entry["original_field_names"] = list(entry["original_field_names"])
        entry["confidence_counts"] = dict(entry["confidence_counts"])
        entry["section_counts"] = dict(entry["section_counts"])
        entry["source_file_counts"] = dict(entry["source_file_counts"])
        
        # Convert field_ids to final format
        field_ids_data = entry["field_ids"]
        
        # Extract all field1 IDs (flatten, deduplicate, sort)
        field1_all = set()
        for ids_list in field_ids_data.get("ie1_field1", []):
            if isinstance(ids_list, list):
                field1_all.update(ids_list)
            else:
                field1_all.add(ids_list)
        
        # Extract all field2 IDs (flatten, deduplicate, sort)
        field2_all = set()
        for ids_list in field_ids_data.get("ie2_field2", []):
            if isinstance(ids_list, list):
                field2_all.update(ids_list)
            else:
                field2_all.add(ids_list)
        
        # Update to final format
        entry["field_ids"] = {
            "field1_all": sorted(field1_all),
            "field2_all": sorted(field2_all),
            "actual_pairs": field_ids_data.get("actual_pairs", [])
        }
    
    return global_map, total_constraints, skipped_files


# ============================================================================
# Statistical Analysis Functions
# ============================================================================

def analyze_aggregation(global_map: Dict) -> Dict:
    """
    Analyze aggregation results
    
    Generate detailed statistics (including actual_pairs statistics and combinatorial explosion avoidance rate)
    """
    total_field_pairs = len(global_map)
    
    # Statistical distribution of evidence quantity
    evidence_counts = [len(entry["evidences"]) for entry in global_map.values()]
    evidence_distribution = Counter(evidence_counts)
    
    # Statistics of confidence distribution
    all_confidences = Counter()
    for entry in global_map.values():
        all_confidences.update(entry["confidence_counts"])
    
    # Count the number of IE pair combinations
    ie_pairs = set()
    for entry in global_map.values():
        ie_pair = tuple(entry["ie_pair"])
        ie_pairs.add(ie_pair)
    
    # Count field_ids and actual_pairs
    field_id_stats = {
        "total_with_field_ids": 0,
        "total_actual_pairs": 0,
        "actual_pairs_distribution": Counter()
    }
    
    for entry in global_map.values():
        field_ids = entry["field_ids"]
        # Use the new format
        if field_ids.get("field1_all") or field_ids.get("field2_all"):
            field_id_stats["total_with_field_ids"] += 1
        
        actual_pairs = field_ids.get("actual_pairs", [])
        if actual_pairs:
            field_id_stats["total_actual_pairs"] += len(actual_pairs)
            field_id_stats["actual_pairs_distribution"][len(actual_pairs)] += 1
    
    # Calculate combinatorial explosion avoidance rate
    total_theoretical = 0
    total_actual = 0
    for entry in global_map.values():
        field_ids = entry["field_ids"]
        field1_count = len(field_ids.get("field1_all", []))
        field2_count = len(field_ids.get("field2_all", []))
        actual_count = len(field_ids.get("actual_pairs", []))
        
        theoretical = field1_count * field2_count
        total_theoretical += theoretical
        total_actual += actual_count
    
    avoidance_rate = 0
    if total_theoretical > 0:
        avoidance_rate = (1 - total_actual / total_theoretical) * 100
    
    # Top field pairs (by number of evidence)
    top_field_pairs = sorted(
        global_map.items(),
        key=lambda x: len(x[1]["evidences"]),
        reverse=True
    )[:20]
    
    summary = {
        "total_inter_ie_field_pairs": total_field_pairs,
        "unique_ie_pair_combinations": len(ie_pairs),
        "total_evidences": sum(evidence_counts),
        "avg_evidences_per_pair": sum(evidence_counts) / total_field_pairs if total_field_pairs > 0 else 0,
        
        "evidence_distribution": {
            "by_count": dict(sorted(evidence_distribution.items())),
            "min": min(evidence_counts) if evidence_counts else 0,
            "max": max(evidence_counts) if evidence_counts else 0,
            "median": sorted(evidence_counts)[len(evidence_counts)//2] if evidence_counts else 0
        },
        
        "confidence_distribution": dict(all_confidences),
        
        # Added: field_ids statistics
        "field_id_stats": {
            "total_with_field_ids": field_id_stats["total_with_field_ids"],
            "total_actual_pairs": field_id_stats["total_actual_pairs"],
            "actual_pairs_distribution": dict(sorted(field_id_stats["actual_pairs_distribution"].items()))
        },
        
        # Added: Combo explosion statistics
        "combination_explosion": {
            "theoretical_combinations": total_theoretical,
            "actual_pairs": total_actual,
            "avoidance_rate_percent": round(avoidance_rate, 2)
        },
        
        "top_field_pairs_by_evidence": [
            {
                "ie_pair": fp[1]["ie_pair"],
                "field_pair": fp[1]["field_pair"],
                "evidence_count": len(fp[1]["evidences"]),
                # Use new format
                "has_field_ids": bool(fp[1]["field_ids"].get("field1_all") or fp[1]["field_ids"].get("field2_all")),
                "actual_pairs_count": len(fp[1]["field_ids"].get("actual_pairs", [])),
                "confidences": fp[1]["confidence_counts"]
            }
            for fp in top_field_pairs
        ]
    }
    
    return summary


def print_summary(summary: Dict):
    """Print Summary Statistics"""
    print("\n" + "="*80)
    print("📊 INTER-IE AGGREGATION SUMMARY")
    print("="*80)
    
    print(f"\n🎯 Key Metrics:")
    print(f"   Total Inter-IE field pairs: {summary['total_inter_ie_field_pairs']}")
    print(f"   Unique IE pair combinations: {summary['unique_ie_pair_combinations']}")
    print(f"   Total evidences: {summary['total_evidences']}")
    print(f"   Avg evidences per pair: {summary['avg_evidences_per_pair']:.1f}")
    
    print(f"\n📈 Evidence Distribution:")
    print(f"   Min: {summary['evidence_distribution']['min']}")
    print(f"   Median: {summary['evidence_distribution']['median']}")
    print(f"   Max: {summary['evidence_distribution']['max']}")
    
    print(f"\n🏷️  Confidence Distribution:")
    for conf, count in sorted(summary['confidence_distribution'].items(), 
                             key=lambda x: x[1], reverse=True):
        print(f"   {conf}: {count}")
    
    # Added: field_ids statistics
    print(f"\n🔢 Field ID Stats:")
    field_id_stats = summary.get('field_id_stats', {})
    print(f"   Total with field_ids: {field_id_stats.get('total_with_field_ids', 0)}")
    print(f"   Total actual pairs: {field_id_stats.get('total_actual_pairs', 0)}")
    if field_id_stats.get('actual_pairs_distribution'):
        print(f"   Actual pairs distribution:")
        for count, freq in sorted(field_id_stats['actual_pairs_distribution'].items())[:10]:
            print(f"      {count} pairs: {freq} field pairs")
    
    # Added: Combo explosion statistics
    print(f"\n💥 Combination Explosion Avoidance:")
    comb_exp = summary.get('combination_explosion', {})
    theoretical = comb_exp.get('theoretical_combinations', 0)
    actual = comb_exp.get('actual_pairs', 0)
    avoidance = comb_exp.get('avoidance_rate_percent', 0)
    print(f"   Theoretical combinations: {theoretical:,}")
    print(f"   Actual pairs needed: {actual:,}")
    print(f"   Avoidance rate: {avoidance:.2f}%")
    if theoretical > 0:
        print(f"   Saved: {theoretical - actual:,} unnecessary test cases!")
    
    print(f"\n⭐ Top 10 Field Pairs (by evidence count):")
    for i, item in enumerate(summary['top_field_pairs_by_evidence'][:10], 1):
        ie_pair = item['ie_pair']
        field_pair = item['field_pair']
        actual_pairs_count = item.get('actual_pairs_count', 0)
        print(f"   {i:2d}. {ie_pair[0]}.{field_pair[0]} ↔ {ie_pair[1]}.{field_pair[1]}")
        print(f"       Evidences: {item['evidence_count']}, "
              f"Has field_ids: {'✅' if item['has_field_ids'] else '❌'}, "
              f"Actual pairs: {actual_pairs_count}")
    
    print("\n" + "="*80)


# ============================================================================
# Save function
# ============================================================================

def save_aggregated_data(global_map: Dict, output_dir: str):
    """Save aggregated data"""
    output_path = os.path.join(output_dir, AGGREGATED_FILE)
    
    # Convert to serializable format
    serializable_map = {}
    for key, entry in global_map.items():
        # Use string keys (JSON does not support tuples as keys)
        # Format: ie1___field1___ie2___field2
        key_str = f"{key[0]}___{key[1]}___{key[2]}___{key[3]}"
        serializable_map[key_str] = entry
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(serializable_map, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Saved aggregated data to: {output_path}")
    
    # Calculate file size
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"   File size: {file_size_mb:.2f} MB")


def save_summary(summary: Dict, output_dir: str):
    """Save summary statistics"""
    output_path = os.path.join(output_dir, SUMMARY_FILE)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Saved summary to: {output_path}")


# ============================================================================
# main function
# ============================================================================

def main():
    print("="*80)
    print("🎯 INTER-IE FIELD PAIR AGGREGATOR (FIXED VERSION)")
    print("="*80)
    print(f"📂 Input directory: {CONSTRAINTS_DIR}")
    print(f"📂 Output directory: {OUTPUT_DIR}")
    print(f"⚙️  Configuration:")
    print(f"   - Normalize IE names: {NORMALIZE_IE_NAMES}")
    print(f"   - Normalize field names: {NORMALIZE_FIELD_NAMES}")
    print(f"   - Deduplicate evidences: {DEDUPLICATE_EVIDENCES}")
    print(f"- Key format: (IE1, field1, IE2, field2) four-tuple ✅")
    print(f"   - Preserve field_ids: YES ✅")
    print("="*80)
    
    # Check input directory
    if not os.path.exists(CONSTRAINTS_DIR):
        print(f"\n❌ Input directory not found: {CONSTRAINTS_DIR}")
        return
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Initialize diagnostic file
    diagnosis_path = os.path.join(OUTPUT_DIR, DIAGNOSIS_FILE)
    with open(diagnosis_path, 'w', encoding='utf-8') as f:
        f.write(f"=== Inter-IE Field Pair Aggregation Diagnosis ===\n")
        f.write(f"Started at: {datetime.now()}\n")
        f.write(f"Fixed: 2025-12-09 - Four-tuple key + field_ids preservation\n")
        f.write(f"{'='*60}\n\n")
    
    # Find all constraint files
    print(f"\n🔍 Searching for constraint files...")
    constraint_files = glob.glob(os.path.join(CONSTRAINTS_DIR, "*_constraints*.json"))
    
    if not constraint_files:
        print(f"❌ No constraint files found in {CONSTRAINTS_DIR}")
        return
    
    print(f"✅ Found {len(constraint_files)} constraint files")
    
    # Global Aggregation
    start_time = datetime.now()
    global_map, total_constraints, skipped_files = aggregate_inter_ie_field_pairs(constraint_files)
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print(f"\n✅ Aggregation completed in {elapsed:.2f} seconds")
    print(f"   Aggregated {total_constraints} constraints into {len(global_map)} Inter-IE field pairs")
    print(f"   Compression ratio: {total_constraints/len(global_map):.1f}x")
    
    # Statistical Analysis
    print(f"\n📊 Analyzing aggregation results...")
    summary = analyze_aggregation(global_map)
    
    # Add metadata
    summary["metadata"] = {
        "aggregation_time": datetime.now().isoformat(),
        "input_directory": CONSTRAINTS_DIR,
        "total_files_processed": len(constraint_files) - skipped_files,
        "total_files_found": len(constraint_files),
        "skipped_files": skipped_files,
        "total_constraint_entries": total_constraints,
        "compression_ratio": total_constraints / len(global_map) if global_map else 0,
        "processing_time_seconds": elapsed,
        "configuration": {
            "normalize_ie_names": NORMALIZE_IE_NAMES,
            "normalize_field_names": NORMALIZE_FIELD_NAMES,
            "deduplicate_evidences": DEDUPLICATE_EVIDENCES,
            "key_format": "four_tuple",
            "field_ids_preserved": True
        }
    }
    
    # Print Summary
    print_summary(summary)
    
    # Save results
    print(f"\n💾 Saving results...")
    save_aggregated_data(global_map, OUTPUT_DIR)
    save_summary(summary, OUTPUT_DIR)
    
    print(f"\n📋 Diagnosis log: {diagnosis_path}")
    print("\n" + "="*80)
    print("🎉 AGGREGATION COMPLETED!")
    print("="*80)
    print(f"\n📊 Quick Stats:")
    print(f"   Input: {total_constraints} constraint entries from {len(constraint_files)} files")
    print(f"Output: {len(global_map)} Inter-IE field pairs (quadruples)")
    print(f"   Reduction: {(1 - len(global_map)/total_constraints)*100:.1f}% fewer entries")
    print(f"   Estimated API cost: ${len(global_map) * 0.03:.2f}")
    print(f"   Time savings potential: ~{total_constraints/len(global_map):.0f}x faster with aggregation")
    print("\n🚀 Next step: Run generate_inter_ie_dsl_concurrent.py with aggregated data")
    print("="*80)


if __name__ == "__main__":
    main()