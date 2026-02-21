import os
import shutil
import re
import json
from pathlib import Path

def normalize_name(name):
    """
    Standardized names are used for comparison
    - Convert to uppercase
    - Convert both '-' and '_' to a unified character (for comparison)
    """
    name = name.upper()
    name = name.replace('-', '#').replace('_', '#')
    return name

def extract_ie_name_variations(filename):
    """
    Extract all possible variants of IE names from filenames
    Return a list containing multiple possible IE name extraction methods
    """
    # Remove extension
    name = os.path.splitext(filename)[0]
    
    variations = []
    
    # Attempt 1: Match multi-field format: number_number_name
    multi_field_match = re.match(r'^(\d+)_(\d+)_(.+)$', name)
    if multi_field_match:
        ie_name = multi_field_match.group(3)
        variations.append(ie_name)
        # Try removing the trailing numeric suffix (e.g. message_2 -> message)
        clean_name = re.sub(r'_\d+$', '', ie_name)
        if clean_name != ie_name:
            variations.append(clean_name)
        # Remove the _group suffix
        clean_name = re.sub(r'_group\d+$', '', ie_name)
        if clean_name != ie_name:
            variations.append(clean_name)
        return variations
    
    # Attempt 2: Match single field format: number_name
    single_field_match = re.match(r'^(\d+)_(.+)$', name)
    if single_field_match:
        ie_name = single_field_match.group(2)
        variations.append(ie_name)
        # Try removing the trailing number suffix
        clean_name = re.sub(r'_\d+$', '', ie_name)
        if clean_name != ie_name:
            variations.append(clean_name)
        return variations
    
    # Attempt 3: Cases that may contain parent paths, such as "parent_child"
    if '_' in name:
        variations.append(name)  # Full Name
        last_part = name.split('_')[-1]
        variations.append(last_part)  # Final section
        # Also tried removing the numerical suffix
        clean_name = re.sub(r'_\d+$', '', name)
        if clean_name != name:
            variations.append(clean_name)
    else:
        variations.append(name)
    
    return list(set(variations))  # Remove duplicates

def get_asn1_name_from_filename(filename):
    """
    Extract name from ASN.1 filename (remove extension)
    """
    return os.path.splitext(filename)[0]

def find_matching_asn1_file(ie_name_variations, asn1_files):
    """
    Find matching ASN.1 files
    Try all IE name variants
    Returns (matched ASN.1 filename, used IE name variant), or (None, None) if no match is found
    """
    for ie_name in ie_name_variations:
        normalized_ie_name = normalize_name(ie_name)
        
        for asn1_file in asn1_files:
            asn1_name = get_asn1_name_from_filename(asn1_file)
            normalized_asn1_name = normalize_name(asn1_name)
            
            # Try exact match
            if normalized_ie_name == normalized_asn1_name:
                return asn1_file, ie_name
            
            # Try partial matching (IE name contained in ASN.1 name, or vice versa)
            if normalized_ie_name in normalized_asn1_name or normalized_asn1_name in normalized_ie_name:
                # Ensure partial matches are not too short (to avoid false matches)
                if len(normalized_ie_name) >= 4 and len(normalized_asn1_name) >= 4:
                    return asn1_file, ie_name
    
    return None, None

def get_field_id_range(filepath):
    """
    Extract field_id range from IE files
    Returns: (min_id, max_id) or None
    """
    try:
        with open(filepath, 'r') as f:
            records = json.load(f)
        if not records:
            return None
        field_ids = [r['field_id'] for r in records]
        return (min(field_ids), max(field_ids))
    except:
        return None

def filter_ies_with_asn1_rules(verbose=True):
    """
    Main function: Filter IE files with corresponding ASN.1 rules and remove duplicates
    
    Args:
        verbose: whether to print detailed matching information
    """
    # Define path
    ie_dir = "../outputs/00_extracted_IEs_id"  # Use the repaired 00 output
    asn1_dir = "../TS38331ASN"
    output_dir = "../outputs/01_existASN_IEs_id"
    
    # Check if the input directory exists
    if not os.path.exists(ie_dir):
        print(f"Error: IE directory does not exist: {ie_dir}")
        return
    
    if not os.path.exists(asn1_dir):
        print(f"Error: ASN.1 rules directory does not exist: {asn1_dir}")
        return
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all IE files and ASN.1 files
    ie_files = sorted([f for f in os.listdir(ie_dir) if f.endswith('.json')])
    asn1_files = [f for f in os.listdir(asn1_dir) if f.endswith('.asn1')]
    
    print(f"Found {len(ie_files)} IE files")
    print(f"Found {len(asn1_files)} ASN.1 rule files\n")
    
    # Filtering and deduplication
    matched_count = 0
    unmatched_ies = []
    
    # Dictionary for deduplication (field_range -> best IE file information)
    field_range_map = {}
    duplicate_count = 0
    
    for ie_file in ie_files:
        ie_name_variations = extract_ie_name_variations(ie_file)
        matching_asn1, matched_variation = find_matching_asn1_file(ie_name_variations, asn1_files)
        
        if matching_asn1:
            src_path = os.path.join(ie_dir, ie_file)
            
            # Get field_id range for deduplication
            field_range = get_field_id_range(src_path)
            
            if field_range:
                # Check if IE with the same range already exists
                if field_range in field_range_map:
                    duplicate_count += 1
                    existing_file = field_range_map[field_range]['filename']
                    
                    # Choose a better file name
                    # Priority: without _group > with _group, short name > long name
                    current_score = 0
                    existing_score = 0
                    
                    # Without _group bonus points
                    if '_group' not in ie_file:
                        current_score += 10
                    if '_group' not in existing_file:
                        existing_score += 10
                    
                    # Short names get bonus points
                    current_score += (200 - len(ie_file))
                    existing_score += (200 - len(existing_file))
                    
                    if current_score > existing_score:
                        # Current file is better, replace
                        if verbose:
                            print(f"⚠ Deduplication: {ie_file} replaces {existing_file} (same range: {field_range})")
                        field_range_map[field_range] = {
                            'filename': ie_file,
                            'asn1_file': matching_asn1,
                            'matched_variation': matched_variation
                        }
                    else:
                        # Keep original files
                        if verbose:
                            print(f"⚠ Deduplication: Skipping {ie_file} (already has {existing_file}, same range: {field_range})")
                        continue
                else:
                    # New field scope, add
                    field_range_map[field_range] = {
                        'filename': ie_file,
                        'asn1_file': matching_asn1,
                        'matched_variation': matched_variation
                    }
            
            matched_count += 1
            
            if verbose and field_range not in field_range_map:
                print(f"✓ Match: {ie_file}")
                print(f"  -> ASN.1: {matching_asn1}")
                print(f"-> Field range: {field_range}")
                print()
        else:
            unmatched_ies.append((ie_file, ie_name_variations))
    
    # Only copy deduplicated files
    print(f"Copying deduplicated IE files...")
    final_count = 0
    for field_range, info in field_range_map.items():
        ie_file = info['filename']
        src_path = os.path.join(ie_dir, ie_file)
        dst_path = os.path.join(output_dir, ie_file)
        shutil.copy2(src_path, dst_path)
        final_count += 1
        
        if final_count % 50 == 0:
            print(f"Copied {final_count} files...")
    
    # Print statistics
    print("="*80)
    print(f"Screening completed!")
    print(f"- Number of successfully matched IE files: {matched_count}/{len(ie_files)} ({matched_count/len(ie_files)*100:.1f}%)")
    print(f"- Duplicate IEs found: {duplicate_count}")
    print(f"- IEs saved after deduplication: {final_count}")
    print(f"- Number of unmatched IE files: {len(unmatched_ies)}")
    print(f"- Deduplicated files have been copied to: {output_dir}")
    
    # Show unmatched files
    if unmatched_ies:
        print(f"Unmatched IE files (showing first 20):")
        for ie_file, variations in unmatched_ies[:20]:
            print(f"  - {ie_file}")
            print(f"Variations attempted: {variations}")
        if len(unmatched_ies) > 20:
            print(f"... and {len(unmatched_ies) - 20} more unmatched files")
    
    return matched_count, len(ie_files), unmatched_ies

def main():
    import sys
    
    print("Starting to filter IE files with ASN.1 rules (with deduplication)...\n")
    
    # Execute filter
    verbose = '--quiet' not in sys.argv
    filter_ies_with_asn1_rules(verbose=verbose)

if __name__ == "__main__":
    main()