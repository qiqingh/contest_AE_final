#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Intra-IE Constraint Aggregation Tool
Aggregate the output of Toolchain 3 by field pairs to reduce API calls
"""

import os
import json
import glob
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# ============================================================================
# Configuration
# ============================================================================

DEFAULT_INPUT_DIR = "../../../toolchain3_field_pair_context_extraction/intra-IE/outputs/new_2_context_with_sections_all_pairs"
DEFAULT_OUTPUT_DIR = "../outputs/aggregated"
AGGREGATED_FILENAME = "aggregated_field_pairs.json"

# ============================================================================
# Core Aggregation Functions
# ============================================================================

def extract_ie_name_from_filename(filename):
    """Extract IE name from filename"""
    basename = os.path.basename(filename)
    
    # New format: {field_id_range}_{ie_name}_constraints.json
    # For example: 695_780_NZP-CSI-RS-ResourceConfig_constraints.json
    match = re.search(r'^\d+_\d+_(.+)_constraints\.json$', basename)
    if match:
        ie_name = match.group(1)
        return ie_name
    
    # Compatible with legacy formats (if needed)
    match_old = re.search(r'(.+)_constraints\.json$', basename)
    if match_old:
        return match_old.group(1)
    
    return None

def create_field_pair_key(constraint):
    """Create unique key for field pairs"""
    fields = tuple(constraint.get('fields', []))
    field_ids = tuple(map(tuple, constraint.get('field_ids', [])))
    return (fields, field_ids)

def aggregate_constraints(constraint_files):
    """Aggregate all constraint files"""
    print(f"\n{'='*60}")
    print("Aggregating constraints by field pairs...")
    print(f"{'='*60}")
    
    field_pair_map = defaultdict(list)
    total_entries = 0
    file_count = 0
    
    for constraint_file in constraint_files:
        try:
            with open(constraint_file, 'r', encoding='utf-8') as f:
                constraints = json.load(f)
            
            if not constraints:
                continue
            
            ie_name = extract_ie_name_from_filename(constraint_file)
            file_count += 1
            
            for constraint in constraints:
                # Create Key
                key = create_field_pair_key(constraint)
                
                # Add IE information
                constraint['ie_name'] = ie_name
                constraint['source_constraint_file'] = os.path.basename(constraint_file)
                
                # Add to mapping
                field_pair_map[key].append(constraint)
                total_entries += 1
            
            if file_count % 10 == 0:
                print(f"  Processed {file_count} files, {total_entries} entries...")
                
        except Exception as e:
            print(f"  Error processing {constraint_file}: {e}")
            continue
    
    print(f"\n Aggregation complete!")
    print(f"  - Files processed: {file_count}")
    print(f"  - Total constraint entries: {total_entries}")
    print(f"  - Unique field pairs: {len(field_pair_map)}")
    print(f"  - Reduction rate: {(1 - len(field_pair_map)/max(total_entries, 1))*100:.1f}%")
    
    return field_pair_map, total_entries

def format_aggregated_output(field_pair_map):
    """Format aggregated output"""
    print(f"\n{'='*60}")
    print("Formatting aggregated data...")
    print(f"{'='*60}")
    
    output = {
        "summary": {
            "generated_at": datetime.now().isoformat(),
            "total_constraint_entries": sum(len(v) for v in field_pair_map.values()),
            "unique_field_pairs": len(field_pair_map),
            "reduction_rate": f"{(1 - len(field_pair_map)/sum(len(v) for v in field_pair_map.values()))*100:.1f}%"
        },
        "field_pairs": {}
    }
    
    for (fields, field_ids), constraints in field_pair_map.items():
        # Create readable key names
        field1, field2 = fields
        field_ids_str = str(list(map(list, field_ids))).replace(' ', '')
        key_name = f"{field1}_{field2}_{field_ids_str}"
        
        # Extract all evidence
        evidences = []
        for c in constraints:
            evidences.append({
                "original_sentence": c.get('original_sentence', ''),
                "source_file": c.get('source_file', ''),
                "section_number": c.get('section_number', ''),
                "section_title": c.get('section_title', ''),
                "confidence": c.get('confidence', 'UNKNOWN'),
                "constraint_keyword": c.get('constraint_keyword', ''),
                "ie_relevance_score": c.get('ie_relevance_score', 0.0),
                "matched_fields": c.get('matched_fields', [])
            })
        
        # Calculate optimal confidence level
        confidence_priority = {'HIGH': 4, 'MEDIUM': 3, 'LOW': 2, 'VERY_LOW': 1, 'UNKNOWN': 0}
        best_confidence = max(
            (c.get('confidence', 'UNKNOWN') for c in constraints),
            key=lambda x: confidence_priority.get(x, 0)
        )
        
        # Collect all sources
        all_sources = list(set(c.get('source_file', '') for c in constraints if c.get('source_file')))
        all_sections = list(set(c.get('section_number', '') for c in constraints if c.get('section_number')))
        all_ie_names = list(set(c.get('ie_name', '') for c in constraints if c.get('ie_name')))
        
        # Get is_self_reference (should be the same for all entries)
        is_self_reference = constraints[0].get('is_self_reference', False) if constraints else False
        
        # Build field-to-entry mapping
        output["field_pairs"][key_name] = {
            "fields": list(fields),
            "field_ids": list(map(list, field_ids)),
            "is_self_reference": is_self_reference,
            "ie_names": all_ie_names,
            "evidence_count": len(evidences),
            "evidences": evidences,
            "best_confidence": best_confidence,
            "all_sources": all_sources,
            "all_sections": all_sections
        }
    
    return output

def print_statistics(output):
    """Print statistics"""
    print(f"\n{'='*60}")
    print("Aggregation Statistics")
    print(f"{'='*60}")
    
    summary = output['summary']
    print(f"Total constraint entries: {summary['total_constraint_entries']}")
    print(f"Unique field pairs: {summary['unique_field_pairs']}")
    print(f"Reduction rate: {summary['reduction_rate']}")
    
    # Statistical distribution of evidence quantity
    evidence_counts = [v['evidence_count'] for v in output['field_pairs'].values()]
    print(f"\nEvidence distribution:")
    print(f"  - Min evidences per pair: {min(evidence_counts)}")
    print(f"  - Max evidences per pair: {max(evidence_counts)}")
    print(f"  - Average evidences per pair: {sum(evidence_counts)/len(evidence_counts):.1f}")
    
    # Statistical Confidence Distribution
    confidence_stats = defaultdict(int)
    for v in output['field_pairs'].values():
        confidence_stats[v['best_confidence']] += 1
    
    print(f"\nConfidence distribution (best per pair):")
    for conf, count in sorted(confidence_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {conf}: {count} pairs")
    
    # Statistical self-citation vs cross-field
    self_ref_count = sum(1 for v in output['field_pairs'].values() if v['is_self_reference'])
    cross_field_count = len(output['field_pairs']) - self_ref_count
    print(f"\nConstraint types:")
    print(f"  - Self-reference: {self_ref_count} pairs")
    print(f"  - Cross-field: {cross_field_count} pairs")
    
    # Top field pairs by evidence count
    print(f"\nTop 10 field pairs by evidence count:")
    sorted_pairs = sorted(
        output['field_pairs'].items(),
        key=lambda x: x[1]['evidence_count'],
        reverse=True
    )[:10]
    
    for idx, (key, value) in enumerate(sorted_pairs, 1):
        fields = ' ↔ '.join(value['fields'])
        print(f"  {idx}. {fields}: {value['evidence_count']} evidences")

def main():
    """main function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Aggregate Intra-IE constraints by field pairs'
    )
    parser.add_argument('--input_dir', default=DEFAULT_INPUT_DIR,
                       help='Input directory containing constraint JSON files')
    parser.add_argument('--output_dir', default=DEFAULT_OUTPUT_DIR,
                       help='Output directory for aggregated results')
    
    args = parser.parse_args()
    
    print("="*60)
    print(" INTRA-IE CONSTRAINT AGGREGATION TOOL")
    print("="*60)
    print(f"Input directory: {args.input_dir}")
    print(f"Output directory: {args.output_dir}")
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Find all constraint files
    constraint_files = glob.glob(os.path.join(args.input_dir, "*_constraints.json"))
    
    if not constraint_files:
        print(f"\n  No constraint files found in {args.input_dir}")
        return
    
    print(f"\n  Found {len(constraint_files)} constraint files")
    
    # Aggregation constraints
    field_pair_map, total_entries = aggregate_constraints(constraint_files)
    
    if not field_pair_map:
        print("\n  No constraints to aggregate")
        return
    
    # Formatted output
    output = format_aggregated_output(field_pair_map)
    
    # Save results
    output_path = os.path.join(args.output_dir, AGGREGATED_FILENAME)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n Aggregated results saved to: {output_path}")
    
    # Print statistics
    print_statistics(output)
    
    print("\n" + "="*60)
    print(" AGGREGATION COMPLETE!")
    print("="*60)
    print(f"\n Summary:")
    print(f"  Original entries: {total_entries}")
    print(f"  Unique field pairs: {len(field_pair_map)}")
    print(f"  API calls saved: {total_entries - len(field_pair_map)} ({(1 - len(field_pair_map)/total_entries)*100:.1f}%)")
    print(f"\n Estimated cost reduction:")
    print(f"  Before: ${total_entries * 0.03:.2f} (assuming $0.03/call)")
    print(f"  After: ${len(field_pair_map) * 0.03:.2f}")
    print(f"  Savings: ${(total_entries - len(field_pair_map)) * 0.03:.2f}")

if __name__ == "__main__":
    main()