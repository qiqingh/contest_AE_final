#!/usr/bin/env python3
"""
Greedy Set Cover for Intra-IE Selection
Automatically searches for optimal min_fields and max_fields parameters
"""
import json
import os
import sys
import re
import shutil
from collections import defaultdict

# ===============================
# 📁 PATH CONFIGURATION - MODIFY HERE
# ===============================

# Method 1: Use relative paths (recommended)
# Assumes script is in: intra-IE/code/intra-IE_strategy/
INPUT_IE_DIR = "../outputs/01_existASN_IEs_id"
OUTPUT_SELECTED_DIR = "../outputs/intra-IE_strategy/selected_ies"


# Convert relative paths to absolute (don't modify this)
if not os.path.isabs(INPUT_IE_DIR):
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    INPUT_IE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, INPUT_IE_DIR))

if not os.path.isabs(OUTPUT_SELECTED_DIR):
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_SELECTED_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, OUTPUT_SELECTED_DIR))

def validate_input():
    """Validate input directory exists and contains files"""
    print(f"\n📁 Checking input directory:")
    print(f"   {INPUT_IE_DIR}")
    
    if not os.path.exists(INPUT_IE_DIR):
        print(f"\n❌ Error: Input directory not found")
        print(f"\n💡 To fix this:")
        print(f"   1. Check the path in the script (lines 15-16)")
        print(f"   2. Or use absolute path (lines 19-20)")
        print(f"   3. Make sure you're in the correct directory")
        return False
    
    ie_files = [f for f in os.listdir(INPUT_IE_DIR) if f.endswith('.json')]
    if len(ie_files) == 0:
        print(f"\n❌ Error: No JSON files found in input directory")
        return False
    
    print(f"   ✅ Found {len(ie_files)} IE files")
    return True

# ===============================
# 🔧 SEARCH PARAMETERS - MODIFY HERE
# ===============================
MIN_FIELDS_RANGE = (3, 5)      # Search min_fields: from 3 to 5
MAX_FIELDS_RANGE = (10, 30)    # Search max_fields: from 10 to 30
SEARCH_STEP = 5                # Increase by 5 each time

# Optional: Fine search (more combinations, slower)
# MIN_FIELDS_RANGE = (2, 6)
# MAX_FIELDS_RANGE = (10, 50)
# SEARCH_STEP = 2

# ===============================
# Core Functions (don't modify below)
# ===============================

def check_field_continuity(records):
    """Check if IE fields are continuous"""
    if len(records) <= 1:
        return True, []
    
    field_ids = sorted([r['field_id'] for r in records])
    gaps = [field_ids[i+1] - field_ids[i] for i in range(len(field_ids)-1)]
    is_continuous = all(g == 1 for g in gaps)
    return is_continuous, gaps

def load_ies_with_fields(ie_dir, require_continuous=True):
    """Load all IE and their field information"""
    ies = []
    skipped_count = 0
    
    ie_files = sorted([f for f in os.listdir(ie_dir) if f.endswith('.json')])
    
    for ie_file in ie_files:
        file_path = os.path.join(ie_dir, ie_file)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                records = json.load(f)
            
            match = re.match(r'^(?:\d+_)?(?:\d+_)?(.+)\.json$', ie_file)
            ie_name = match.group(1) if match else ie_file
            
            field_ids = set(record['field_id'] for record in records)
            num_fields = len(records)
            num_pairs = num_fields * (num_fields - 1) // 2 if num_fields > 1 else 0
            
            # Check field continuity
            is_continuous, gaps = check_field_continuity(records)
            if require_continuous and not is_continuous:
                skipped_count += 1
                continue
            
            # Determine whether important keywords are included
            important_keywords = [
                'config', 'setup', 'bearer', 'resource', 'cell',
                'pucch', 'pusch', 'pdsch', 'pdcch', 'prach',
                'harq', 'csi', 'bwp', 'coreset', 'searchspace',
                'srs', 'dmrs', 'mac', 'rlc', 'rrc'
            ]
            ie_name_lower = ie_name.lower()
            has_keyword = any(kw in ie_name_lower for kw in important_keywords)
            keyword_count = sum(1 for kw in important_keywords if kw in ie_name_lower)
            
            ie_info = {
                'filename': ie_file,
                'ie_name': ie_name,
                'num_fields': num_fields,
                'num_pairs': num_pairs,
                'field_ids': field_ids,
                'has_keyword': has_keyword,
                'keyword_count': keyword_count,
                'records': records
            }
            
            ies.append(ie_info)
            
        except Exception as e:
            print(f"Warning: Error occurred while processing {ie_file}: {e}")
    
    if require_continuous and skipped_count > 0:
        print(f"Filtered out {skipped_count} IEs with non-contiguous fields")
    
    return ies

def greedy_set_cover(ies, all_field_ids, min_fields=3, max_fields=20, 
                     prefer_important=True, max_pairs_per_ie=1000,
                     verbose=False):
    """
    Greedy algorithm for minimum set cover
    
    Args:
        verbose: whether to print detailed iteration process
    """
    # Screen candidate IEs
    candidates = [
        ie for ie in ies 
        if min_fields <= ie['num_fields'] <= max_fields
        and ie['num_pairs'] <= max_pairs_per_ie
    ]
    
    if verbose:
        print(f"\nCandidate IE pool: {len(candidates)} items (field count range: {min_fields}-{max_fields})")
    
    covered_fields = set()
    selected_ies = []
    remaining_candidates = candidates.copy()
    
    iteration = 0
    while covered_fields != all_field_ids and remaining_candidates:
        iteration += 1
        
        # Calculate how many new fields each candidate IE can cover
        best_ie = None
        best_new_fields = 0
        best_score = -1
        
        for ie in remaining_candidates:
            new_fields = ie['field_ids'] - covered_fields
            num_new_fields = len(new_fields)
            
            if num_new_fields > 0:
                score = num_new_fields
                
                if prefer_important and ie['has_keyword']:
                    score += ie['keyword_count'] * 5
                
                score -= ie['num_pairs'] / 100
                
                if score > best_score:
                    best_score = score
                    best_ie = ie
                    best_new_fields = num_new_fields
        
        if best_ie is None:
            break
        
        selected_ies.append(best_ie)
        covered_fields.update(best_ie['field_ids'])
        remaining_candidates.remove(best_ie)
        
        if verbose and (iteration <= 20 or iteration % 10 == 0):
            coverage_pct = len(covered_fields) / len(all_field_ids) * 100
            print(f"  Iteration {iteration:2d}: Selected {best_ie['ie_name'][:50]:50s} "
                  f"(+{best_new_fields:3d} new fields) -> Coverage: {coverage_pct:.1f}%")
    
    return selected_ies, covered_fields

def calculate_score(stats, all_field_ids):
    """
    Calculate the comprehensive score of the plan
    
    Goal:
    1. Coverage should be as high as possible (most important)
    2. Moderate number of IEs (not too many)
    3. Moderate number of fields (to control LLM query costs)
    """
    coverage = stats['coverage']
    num_ies = stats['total_ies']
    num_pairs = stats['total_pairs']
    
    # Coverage score (highest weight)
    coverage_score = coverage * 10  # 0-1000 points
    
    # IE quantity score (fewer is better, but not too few)
    # Ideal range: 50-150 IE
    if 50 <= num_ies <= 150:
        ie_score = 100
    elif num_ies < 50:
        ie_score = 50 + num_ies  # Encourage more IE
    else:
        ie_score = max(0, 250 - num_ies)  # Excessive IE penalties
    
    # Field log score (controlled within reasonable range)
    # Ideal range: 1000-5000 pairs
    if 1000 <= num_pairs <= 5000:
        pair_score = 100
    elif num_pairs < 1000:
        pair_score = 50 + num_pairs / 20
    else:
        pair_score = max(0, 600 - num_pairs / 100)
    
    # Overall Score
    total_score = coverage_score + ie_score * 0.3 + pair_score * 0.2
    
    return total_score

def generate_parameter_combinations(min_fields_range, max_fields_range, step=5):
    """
    Generate parameter combinations
    
    Args:
        min_fields_range: (start, end) e.g. (3, 5)
        max_fields_range: (start, end) for example (10, 30)
        step: step size
    """
    combinations = []
    
    min_start, min_end = min_fields_range
    max_start, max_end = max_fields_range
    
    for min_f in range(min_start, min_end + 1):
        for max_f in range(max_start, max_end + 1, step):
            if max_f >= min_f:  # Ensure max >= min
                combinations.append((min_f, max_f))
    
    return combinations

def search_best_parameters(ies, all_field_ids, 
                          min_fields_range, max_fields_range, 
                          step=5, prefer_important=True):
    """
    Search for optimal parameter combination
    
    Returns:
        results: List of all results
        top_3: Top 3 recommended solutions
    """
    print("\n" + "="*80)
    print("🔍 Searching for optimal parameter combination")
    print("="*80)
    
    print(f"Search scope:")
    print(f"  min_fields: {min_fields_range[0]} - {min_fields_range[1]}")
    print(f"  max_fields: {max_fields_range[0]} - {max_fields_range[1]} (step: {step})")
    
    # Generate all combinations
    combinations = generate_parameter_combinations(
        min_fields_range, max_fields_range, step
    )
    
    print(f"Total combinations: {len(combinations)}")
    print(f"\nStarting search...\n")
    
    results = []
    
    for i, (min_f, max_f) in enumerate(combinations, 1):
        print(f"[{i:2d}/{len(combinations)}] Testing min={min_f}, max={max_f}...", end=" ")
        
        selected, covered = greedy_set_cover(
            ies, all_field_ids,
            min_fields=min_f,
            max_fields=max_f,
            prefer_important=prefer_important,
            verbose=False
        )
        
        # Statistics
        total_ies = len(selected)
        total_pairs = sum(ie['num_pairs'] for ie in selected)
        covered_count = len(covered)
        coverage_pct = covered_count / len(all_field_ids) * 100
        
        stats = {
            'min_fields': min_f,
            'max_fields': max_f,
            'total_ies': total_ies,
            'total_pairs': total_pairs,
            'covered_fields': covered_count,
            'coverage': coverage_pct,
            'selected_ies': selected
        }
        
        # Calculate score
        score = calculate_score(stats, all_field_ids)
        stats['score'] = score
        
        results.append(stats)
        
        print(f"IE={total_ies:3d}, Pairs={total_pairs:5,d}, Coverage={coverage_pct:5.1f}%, Score={score:.0f}")
    
    # Sort by score
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # First 3 recommendations
    top_3 = results[:3]
    
    return results, top_3

def display_recommendations(top_3, all_field_ids):
    """Show recommended plans"""
    print("\n" + "="*80)
    print("🏆 Top-3 Recommended Solutions")
    print("="*80)
    
    for rank, result in enumerate(top_3, 1):
        print(f"\n{'='*80}")
        print(f"Recommendation #{rank}")
        print(f"{'='*80}")
        
        print(f"Parameters:")
        print(f"  min_fields = {result['min_fields']}")
        print(f"  max_fields = {result['max_fields']}")
        
        print(f"\nResults:")
        print(f"  ✅ Coverage: {result['coverage']:.2f}%")
        print(f"  📊 Number of IEs: {result['total_ies']}")
        print(f"  🔢 Number of field pairs: {result['total_pairs']:,}")
        print(f"  ⭐ Overall score: {result['score']:.0f}")
        
        # Analyze the advantages and disadvantages
        print(f"\nEvaluation:")
        if result['coverage'] >= 95:
            print(f"  ✅ Excellent coverage")
        elif result['coverage'] >= 85:
            print(f"  ✅ Good coverage")
        else:
            print(f"  ⚠️ Coverage is average")
        
        if 50 <= result['total_ies'] <= 150:
            print(f"  ✅ Moderate number of IEs")
        elif result['total_ies'] < 50:
            print(f"  ⚠️ IE quantity is insufficient")
        else:
            print(f"  ⚠️ Too many IEs")
        
        if result['total_pairs'] < 5000:
            print(f"  ✅ Controllable LLM query costs")
        else:
            print(f"  ⚠️ LLM query costs are high")

def save_selected_ies(selected_ies, output_dir, label, stats):
    """Save selected IE to directory"""
    os.makedirs(output_dir, exist_ok=True)
    
    # Copy files
    print(f"\n📋 Copying {len(selected_ies)} IE files...")
    for ie in selected_ies:
        src_path = os.path.join(INPUT_IE_DIR, ie['filename'])
        dst_path = os.path.join(output_dir, ie['filename'])
        shutil.copy2(src_path, dst_path)
    
    # Save Summary
    summary = {
        'label': label,
        'parameters': {
            'min_fields': stats['min_fields'],
            'max_fields': stats['max_fields']
        },
        'statistics': {
            'total_ies': stats['total_ies'],
            'total_pairs': stats['total_pairs'],
            'coverage': stats['coverage'],
            'covered_fields': stats['covered_fields']
        },
        'ie_list': [
            {
                'filename': ie['filename'],
                'ie_name': ie['ie_name'],
                'num_fields': ie['num_fields'],
                'num_pairs': ie['num_pairs'],
                'has_keyword': ie['has_keyword']
            }
            for ie in selected_ies
        ]
    }
    
    summary_file = os.path.join(output_dir, '_summary.json')
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Saved to: {output_dir}")
    print(f"   Summary: {summary_file}")

def main():
    print("="*80)
    print("Greedy Set Cover - Intra-IE Selection")
    print("="*80)
    
    # Parse command line arguments
    require_continuous = '--no-continuous' not in sys.argv
    auto_mode = '--auto' in sys.argv  # Automatic mode (non-interactive)
    
    # Validate input
    if not validate_input():
        return
    
    # Load data
    print(f"\n📂 Loading IE data...")
    ies = load_ies_with_fields(INPUT_IE_DIR, require_continuous=require_continuous)
    print(f"   ✅ Loaded {len(ies)} IEs")
    
    # Get all field IDs
    all_field_ids = set()
    for ie in ies:
        all_field_ids.update(ie['field_ids'])
    print(f"   ✅ Total message fields: {len(all_field_ids)}")
    
    # Automatically search for optimal parameters
    results, top_3 = search_best_parameters(
        ies, all_field_ids,
        min_fields_range=MIN_FIELDS_RANGE,
        max_fields_range=MAX_FIELDS_RANGE,
        step=SEARCH_STEP
    )
    
    # Show Recommendations
    display_recommendations(top_3, all_field_ids)
    
    # Select the scheme to save
    print("\n" + "="*80)
    print("💾 Select the plan to save")
    print("="*80)
    
    if auto_mode:
        # Auto mode: Save 1st place
        print("\nAutomatic mode: Saving 1st place solution")
        selected_rank = 1
    else:
        # Interactive mode: Let users choose
        print("\nPlease select:")
        print("  1 - 1st Place (Recommended)")
        print("  2 - 2nd place")
        print("  3 - 3rd Place")
        print("  0 - Save all 3 solutions")
        
        while True:
            try:
                choice = input("\nYour choice (0/1/2/3, default=1): ").strip()
                if choice == '':
                    choice = '1'
                
                selected_rank = int(choice)
                if 0 <= selected_rank <= 3:
                    break
                else:
                    print("❌ Please enter 0-3")
            except ValueError:
                print("❌ Please enter a valid number")
            except KeyboardInterrupt:
                print("\n\n❌ Cancelled")
                return
    
    # Save selected plan
    if selected_rank == 0:
        # Save all 3 options
        print("\n💾 Saving all 3 plans...")
        for rank, result in enumerate(top_3, 1):
            output_dir = OUTPUT_SELECTED_DIR.replace('selected_ies', f'selected_ies_rank{rank}')
            save_selected_ies(
                result['selected_ies'],
                output_dir,
                f"Rank {rank} (min={result['min_fields']}, max={result['max_fields']})",
                result
            )
    else:
        # Save single plan
        selected = top_3[selected_rank - 1]
        print(f"\n💾 Saving solution #{selected_rank}...")
        save_selected_ies(
            selected['selected_ies'],
            OUTPUT_SELECTED_DIR,
            f"Rank {selected_rank} (min={selected['min_fields']}, max={selected['max_fields']})",
            selected
        )
    
    # Show final results
    print("\n" + "="*80)
    print("✅ Done!")
    print("="*80)
    
    if selected_rank == 0:
        print(f"\nAll 3 solutions saved:")
        for rank in range(1, 4):
            result = top_3[rank-1]
            print(f"  #{rank}: {result['total_ies']} IEs, {result['coverage']:.1f}% coverage")
    else:
        selected = top_3[selected_rank - 1]
        print(f"\nSolution #{selected_rank}:")
        print(f"  Parameters: min={selected['min_fields']}, max={selected['max_fields']}")
        print(f"  Coverage: {selected['coverage']:.2f}%")
        print(f"  IEs: {selected['total_ies']}")
        print(f"  Pairs: {selected['total_pairs']:,}")
        print(f"\n  📁 Location: {OUTPUT_SELECTED_DIR}")
    
    print(f"\n🔜 Next steps:")
    print(f"   - Verify with validation scripts")
    print(f"   - Proceed to Toolchain 3")

if __name__ == "__main__":
    main()