#!/usr/bin/env python3
"""
Greedy Set Cover v3 - Inter-IE Version
IE Selection Algorithm for Inter-IE Constraint Extraction Optimization

Key Indicators:
1. Reference Relationship Coverage (Primary)
2. Reference Field Coverage (Auxiliary)
3. IE Quantity Control
4. Field Name Diversity
"""

import json
import os
import sys
import re
from collections import defaultdict

# ===============================
# User Configuration Area - Inter-IE Dedicated
# ===============================

# Parameter search range
MIN_FIELDS_RANGE = (1, 5)      # Search min_fields: 1, 2, 4, 5
MAX_FIELDS_RANGE = (20, 70)    # Search max_fields: 20, 30, 40, 50, 60, 70
SEARCH_STEP = 10               # max step size 10

# Reference field identification keywords (based on data analysis)
REF_KEYWORDS = ['Id', 'ID']

# Input and output paths
INPUT_IE_DIR = "../outputs/01_existASN_IEs_id"
OUTPUT_SELECTED_DIR = "../outputs/inter-IE_strategy/selected_ies"

# ===============================
# Field Reference Identification
# ===============================

def clean_field_name(field_name):
    """Remove array indices [0], [1], etc."""
    return re.sub(r'\[\d+\]', '', field_name)

def is_reference_field(field_name):
    """
    Determine whether it is a reference field
    
    Rules:
    1. Remove array index
    2. Suffix matching Id, ID
    """
    clean_name = clean_field_name(field_name)
    
    for keyword in REF_KEYWORDS:
        if clean_name.endswith(keyword):
            return True
    
    return False

# ===============================
# IE loading and processing
# ===============================

def load_ies_with_fields(ie_dir):
    """Load IE and extract field information"""
    ies = []
    
    if not os.path.exists(ie_dir):
        print(f"Error: Directory does not exist {ie_dir}")
        return []
    
    ie_files = sorted([f for f in os.listdir(ie_dir) if f.endswith('.json')])
    
    for filename in ie_files:
        filepath = os.path.join(ie_dir, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                records = json.load(f)
            
            if not isinstance(records, list) or len(records) == 0:
                continue
            
            # Extract field ID and field name
            field_ids = set()
            field_names = set()
            ref_field_names = set()
            
            for record in records:
                if isinstance(record, dict):
                    if 'field_id' in record:
                        field_ids.add(record['field_id'])
                    
                    if 'field_path' in record:
                        field_path = record['field_path']
                        # Extract the last level field name
                        if '.' in field_path:
                            field_name = field_path.split('.')[-1]
                        else:
                            field_name = field_path
                        
                        field_names.add(field_name)
                        
                        # Determine if it is a reference field
                        if is_reference_field(field_name):
                            ref_field_names.add(field_name)
            
            if len(field_ids) > 0:
                ies.append({
                    'filename': filename,
                    'field_ids': field_ids,
                    'field_names': field_names,
                    'ref_field_names': ref_field_names,
                    'num_fields': len(field_ids)
                })
        
        except Exception as e:
            print(f"Warning: Failed to load {filename}: {e}")
    
    return ies

# ===============================
# Citation relationship calculation
# ===============================

def calculate_reference_pairs(ies):
    """
    Calculate logarithm of potential citation relationships
    
    Logic:
    1. Count which IEs each referenced field name appears in
    2. If a referenced field name appears in n IEs, it generates C(n,2) pairs of reference relationships
    """
    # Create mapping: ref_field_name -> [ie1, ie2, ...]
    ref_field_to_ies = defaultdict(list)
    
    for ie in ies:
        for ref_name in ie['ref_field_names']:
            ref_field_to_ies[ref_name].append(ie)
    
    # Calculate citation relationship logarithms
    total_pairs = 0
    pair_details = {}
    
    for ref_name, ie_list in ref_field_to_ies.items():
        n = len(ie_list)
        if n >= 2:
            pairs = n * (n - 1) // 2
            total_pairs += pairs
            pair_details[ref_name] = {
                'ie_count': n,
                'pair_count': pairs
            }
    
    return total_pairs, pair_details, ref_field_to_ies

def count_new_reference_pairs(new_ie, current_selected, ref_field_to_selected_ies):
    """
    Calculate how many new reference relationship pairs can be generated after adding new_ie
    
    Parameters:
    - new_ie: IE to be added
    - current_selected: Currently selected IE list
    - ref_field_to_selected_ies: Reference field mapping for currently selected IEs
    
    Return:
    - Number of newly added citation relationships
    """
    new_pairs = 0
    
    for ref_name in new_ie['ref_field_names']:
        # See how many times this referenced field name appears in the selected IE
        existing_count = len(ref_field_to_selected_ies.get(ref_name, []))
        
        # After adding new_ie, existing_count new pairs will be generated.
        new_pairs += existing_count
    
    return new_pairs

# ===============================
# Greedy Algorithm
# ===============================

def greedy_set_cover_inter(ies, all_field_ids, all_ref_field_names, min_fields, max_fields):
    """
    Inter-IE Dedicated Greedy Algorithm
    
    Priority:
    1. Generate the most new citation relationship pairs
    2. Cover the most new reference fields
    3. Cover the most new common fields
    """
    # Filter IEs that match the field count range
    candidates = [ie for ie in ies 
                  if min_fields <= ie['num_fields'] <= max_fields]
    
    if not candidates:
        return []
    
    selected_ies = []
    covered_field_ids = set()
    covered_ref_field_names = set()
    covered_field_names = set()
    
    # Mapping of referenced fields to selected IE
    ref_field_to_selected_ies = defaultdict(list)
    
    while candidates:
        best_ie = None
        best_score = -1
        
        for ie in candidates:
            # Calculate each gain
            new_ref_pairs = count_new_reference_pairs(
                ie, selected_ies, ref_field_to_selected_ies
            )
            
            new_ref_fields = len(ie['ref_field_names'] - covered_ref_field_names)
            new_field_ids = len(ie['field_ids'] - covered_field_ids)
            new_field_names = len(ie['field_names'] - covered_field_names)
            
            # Overall Rating
            # Priority: Reference relationships > Reference fields > Regular fields
            score = (new_ref_pairs * 100 +      # Citation relationships have the highest weight
                    new_ref_fields * 10 +        # Referenced fields come next
                    new_field_ids * 1 +          # Field ID Override
                    new_field_names * 0.1)       # Field name diversity
            
            if score > best_score:
                best_score = score
                best_ie = ie
        
        # If there is no IE that can increase coverage, stop
        if best_score <= 0:
            break
        
        # Select best_ie
        selected_ies.append(best_ie)
        covered_field_ids.update(best_ie['field_ids'])
        covered_ref_field_names.update(best_ie['ref_field_names'])
        covered_field_names.update(best_ie['field_names'])
        
        # Update reference field mapping
        for ref_name in best_ie['ref_field_names']:
            ref_field_to_selected_ies[ref_name].append(best_ie)
        
        # Remove from candidate pool
        candidates.remove(best_ie)
    
    return selected_ies

# ===============================
# Rating and Sorting
# ===============================

def calculate_score_inter(selected_ies, all_field_ids, all_ref_field_names, 
                         total_ref_pairs_baseline, min_fields, max_fields):
    """
    Inter-IE Specific Scoring
    
    Score = Citation Relationship Coverage (×10) + Citation Field Coverage (×5)
         + IE quantity score (×0.3) + field name diversity (×0.2)
    """
    if not selected_ies:
        return 0
    
    # Count the selected data
    selected_field_ids = set()
    selected_ref_field_names = set()
    selected_field_names = set()
    
    for ie in selected_ies:
        selected_field_ids.update(ie['field_ids'])
        selected_ref_field_names.update(ie['ref_field_names'])
        selected_field_names.update(ie['field_names'])
    
    # Calculate the logarithm of the reference relationships for selected items
    selected_ref_pairs, _, _ = calculate_reference_pairs(selected_ies)
    
    # 1. Citation Relationship Coverage Score (0-1000 points)
    if total_ref_pairs_baseline > 0:
        ref_pair_coverage = selected_ref_pairs / total_ref_pairs_baseline
    else:
        ref_pair_coverage = 0
    score1 = ref_pair_coverage * 10 * 100  # ×10 weight, ×100 to convert to percentage scale
    
    # 2. Citation Field Coverage Score (0-500 points)
    if len(all_ref_field_names) > 0:
        ref_field_coverage = len(selected_ref_field_names) / len(all_ref_field_names)
    else:
        ref_field_coverage = 0
    score2 = ref_field_coverage * 5 * 100
    
    # 3. IE Quantity Score (0-30 points)
    ie_count = len(selected_ies)
    if 100 <= ie_count <= 200:
        score3 = 100
    elif ie_count < 100:
        score3 = max(0, 50 + ie_count * 0.5)
    else:
        score3 = max(0, 300 - ie_count)
    score3 = score3 * 0.3
    
    # 4. Field Name Diversity Score (0-20 points)
    # Here, the count of unique field names is used as a diversity indicator.
    score4 = min(100, len(selected_field_names)) * 0.2
    
    # Overall Score
    total_score = score1 + score2 + score3 + score4
    
    # Normal Field Coverage (Reference)
    field_coverage = len(selected_field_ids) / len(all_field_ids) if all_field_ids else 0
    
    return {
        'total_score': total_score,
        'ref_pair_coverage': ref_pair_coverage * 100,
        'ref_field_coverage': ref_field_coverage * 100,
        'field_coverage': field_coverage * 100,
        'total_ies': ie_count,
        'ref_pairs': selected_ref_pairs,
        'ref_fields': len(selected_ref_field_names),
        'unique_field_names': len(selected_field_names),
        'min_fields': min_fields,
        'max_fields': max_fields
    }

# ===============================
# Parameter Search
# ===============================

def search_best_parameters(ies, all_field_ids, all_ref_field_names, 
                          total_ref_pairs_baseline):
    """
    Search for the optimal parameter combination
    
    Search space: min ∈ [1,2,4,5], max ∈ [20,30,40,50,60,70]
    """
    # Generate parameter combinations
    min_values = [1, 2, 4, 5]
    max_values = [20, 30, 40, 50, 60, 70]
    
    combinations = []
    for min_f in min_values:
        for max_f in max_values:
            if min_f <= max_f:
                combinations.append((min_f, max_f))
    
    print(f"\nWill test {len(combinations)} parameter combinations...")
    print()
    
    results = []
    
    for idx, (min_f, max_f) in enumerate(combinations, 1):
        print(f"[{idx}/{len(combinations)}] Testing min={min_f}, max={max_f}...", end=' ')
        
        # Run greedy algorithm
        selected = greedy_set_cover_inter(
            ies, all_field_ids, all_ref_field_names, min_f, max_f
        )
        
        # Calculate score
        score_data = calculate_score_inter(
            selected, all_field_ids, all_ref_field_names,
            total_ref_pairs_baseline, min_f, max_f
        )
        
        score_data['selected_ies'] = selected
        results.append(score_data)
        
        print(f"IE={score_data['total_ies']}, "
              f"rReference Relationships={score_data['ref_pairs']} pairs, "
              f"Referenced Fields={score_data['ref_fields']}, "
              f"Score={score_data['total_score']:.0f}")
    
    # Sort by score
    results.sort(key=lambda x: x['total_score'], reverse=True)
    
    # Return Top-3
    return results, results[:3]

# ===============================
# Show recommendations
# ===============================

def display_recommendations(top_3, all_field_ids, all_ref_field_names, total_ref_pairs):
    """Show Top-3 recommended solutions"""
    print("\n" + "="*80)
    print("🏆 Top-3 Recommended Solutions (Inter-IE)")
    print("="*80)
    
    for rank, result in enumerate(top_3, 1):
        print(f"Recommendation #{rank}:")
        print(f"  Parameters: min_fields={result['min_fields']}, max_fields={result['max_fields']}")
        print(f"  Reference Relationship Coverage: {result['ref_pair_coverage']:.1f}% "
              f"({result['ref_pairs']}/{total_ref_pairs} pairs)")
        print(f"  Referenced Field Coverage: {result['ref_field_coverage']:.1f}% "
              f"({result['ref_fields']}/{len(all_ref_field_names)} fields)")
        print(f"  Message Field Coverage: {result['field_coverage']:.1f}% "
              f"({len(all_field_ids):.0f} fields)")
        print(f"  Number of IEs: {result['total_ies']}")
        print(f"  Field Name Diversity: {result['unique_field_names']} unique field names")
        print(f"  Total Score: {result['total_score']:.0f}")
        
        # Evaluation
        evaluation = []
        if result['ref_pair_coverage'] >= 90:
            evaluation.append("Excellent citation relationship coverage")
        elif result['ref_pair_coverage'] >= 85:
            evaluation.append("Good citation relationship coverage")
        else:
            evaluation.append("Low citation relationship coverage")
        
        if result['ref_field_coverage'] >= 95:
            evaluation.append("Excellent reference field coverage")
        elif result['ref_field_coverage'] >= 90:
            evaluation.append("Good field reference coverage")
        
        if 100 <= result['total_ies'] <= 200:
            evaluation.append("Moderate number of IEs")
        elif result['total_ies'] < 100:
            evaluation.append("Insufficient number of IEs")
        else:
            evaluation.append("Excessive number of IEs")
        
        print(f"  Evaluation: {' '.join(evaluation)}")

# ===============================
# Save results
# ===============================

def save_selected_ies(selected_ies, output_dir, label, score_data):
    """Save selected IE"""
    os.makedirs(output_dir, exist_ok=True)
    
    # Copy IE files
    for ie in selected_ies:
        src = os.path.join(INPUT_IE_DIR, ie['filename'])
        dst = os.path.join(output_dir, ie['filename'])
        
        with open(src, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        with open(dst, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    # Save Summary
    summary = {
        'label': label,
        'parameters': {
            'min_fields': score_data['min_fields'],
            'max_fields': score_data['max_fields'],
            'ref_keywords': REF_KEYWORDS
        },
        'statistics': {
            'total_ies': score_data['total_ies'],
            'ref_pairs': score_data['ref_pairs'],
            'ref_fields': score_data['ref_fields'],
            'ref_pair_coverage': score_data['ref_pair_coverage'],
            'ref_field_coverage': score_data['ref_field_coverage'],
            'field_coverage': score_data['field_coverage'],
            'unique_field_names': score_data['unique_field_names'],
            'total_score': score_data['total_score']
        },
        'ie_list': [
            {
                'filename': ie['filename'],
                'num_fields': ie['num_fields'],
                'ref_field_names': list(ie['ref_field_names'])
            }
            for ie in selected_ies
        ]
    }
    
    summary_file = os.path.join(output_dir, '_summary.json')
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved {len(selected_ies)} IEs to: {output_dir}")
    print(f"Summary Information: {summary_file}")

# ===============================
# Validate input
# ===============================

def validate_input():
    """Verify input directory"""
    if not os.path.exists(INPUT_IE_DIR):
        print(f"Error: Input directory does not exist")
        print(f"   {INPUT_IE_DIR}")
        print(f"Please run first:")
        print(f"  1. 00_extract_IE_id.py (min_fields=1, continuous=False)")
        print(f"  2. 01_filter_IE_with_ASN_id.py")
        print(f"Generate 01_existASN_IEs_id_inter/")
        return False
    
    ie_files = [f for f in os.listdir(INPUT_IE_DIR) if f.endswith('.json')]
    if len(ie_files) == 0:
        print(f" Error: Input directory is empty")
        print(f"   {INPUT_IE_DIR}")
        return False
    
    return True

# ===============================
# Main function
# ===============================

def main():
    print("="*80)
    print("Greedy Coverage Algorithm - Inter-IE Version")
    print("="*80)
    
    # Validate input
    if not validate_input():
        return
    
    # Loading data
    print(f"Loading IE data...")
    ies = load_ies_with_fields(INPUT_IE_DIR)
    print(f"Loaded {len(ies)} IEs")
    
    # Get all field IDs and reference field names
    all_field_ids = set()
    all_ref_field_names = set()
    
    for ie in ies:
        all_field_ids.update(ie['field_ids'])
        all_ref_field_names.update(ie['ref_field_names'])
    
    print(f"Total number of fields: {len(all_field_ids)}")
    print(f"Total number of referenced field names: {len(all_ref_field_names)}")
    
    # Calculate the logarithm of baseline citation relationships
    total_ref_pairs, pair_details, _ = calculate_reference_pairs(ies)
    print(f"Total reference relationship pairs: {total_ref_pairs:,}")
    
    # Show Top Citation Fields
    top_ref_fields = sorted(pair_details.items(), 
                           key=lambda x: x[1]['pair_count'], 
                           reverse=True)[:10]
    print(f"Top 10 cited fields (by relationship logarithm):")
    for ref_name, info in top_ref_fields:
        print(f"  {ref_name}: {info['ie_count']}个IE, {info['pair_count']}对关系")
    
    # Automatically search for optimal parameters
    results, top_3 = search_best_parameters(
        ies, all_field_ids, all_ref_field_names, total_ref_pairs
    )
    
    # Show Recommendations
    display_recommendations(top_3, all_field_ids, all_ref_field_names, total_ref_pairs)
    
    # Select the plan to save
    print("\n" + "="*80)
    print("Select the scheme to save")
    print("="*80)
    
    print("Please select the plan to save:")
    print("1 - 1st Place (Recommended)")
    print("2 - 2nd place")
    print("3 - 3rd place")
    print("0 - Save all 3 solutions to different directories")
    
    while True:
        try:
            choice = input("Please enter your choice (0/1/2/3, default 1):").strip()
            if choice == '':
                choice = '1'
            
            selected_rank = int(choice)
            if 0 <= selected_rank <= 3:
                break
            else:
                print(" Please enter a number between 0-3")
        except ValueError:
            print(" Please enter a valid number")
        except KeyboardInterrupt:
            print(" User canceled, exit")
            return
    
    # Save selected plan
    if selected_rank == 0:
        # Save all 3 options
        print("Save all 3 plans...")
        for rank, result in enumerate(top_3, 1):
            output_dir = OUTPUT_SELECTED_DIR.replace('selected_ies', f'selected_ies_rank{rank}')
            save_selected_ies(
                result['selected_ies'],
                output_dir,
                f"{rank}th Plan (min={result['min_fields']}, max={result['max_fields']})",
                result
            )
    else:
        # Save single plan
        selected = top_3[selected_rank - 1]
        print(f"\nSaving the #{selected_rank} ranked solution...")
        save_selected_ies(
            selected['selected_ies'],
            OUTPUT_SELECTED_DIR,
            f"{selected_rank}th Plan (min={selected['min_fields']}, max={selected['max_fields']})",
            selected
        )
    
    # Display final results
    print("\n" + "="*80)
    print("Done!")
    print("="*80)
    
    if selected_rank == 0:
        print(f" Saved all 3 solutions to different directories:")
        for rank in range(1, 4):
            print(f"   {rank}: {OUTPUT_SELECTED_DIR.replace('selected_ies', f'selected_ies_rank{rank}')}")
    else:
        selected = top_3[selected_rank - 1]
        print(f"\n Saved solution ranked #{selected_rank}:")
        print(f"   Parameters: min={selected['min_fields']}, max={selected['max_fields']}")
        print(f"   Reference Relationship Coverage: {selected['ref_pair_coverage']:.1f}%")
        print(f"   Referenced Field Coverage: {selected['ref_field_coverage']:.1f}%")
        print(f"   Number of IEs: {selected['total_ies']}")
        print(f"Position: {OUTPUT_SELECTED_DIR}")
    
    print(f"Next step:")
    print(f"- Run check_inter_coverage.py to verify coverage")
    print(f"- Start Toolchain 3B (inter-IE field pair extraction)")

if __name__ == "__main__":
    main()
