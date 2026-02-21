import json
import os
import re
from collections import defaultdict
from pathlib import Path

def parse_path_segments(path):
    """
    Parse the path and return a list of all segments
    """
    segments = []
    current_segment = ""
    in_bracket = False
    
    for char in path:
        if char == '[':
            in_bracket = True
            current_segment += char
        elif char == ']':
            in_bracket = False
            current_segment += char
        elif char == '.' and not in_bracket:
            if current_segment:
                segments.append(current_segment)
                current_segment = ""
        else:
            current_segment += char
    
    if current_segment:
        segments.append(current_segment)
    
    return segments

def get_all_prefixes(path):
    """
    Get all possible prefixes of a path
    Generate both indexed and non-indexed versions simultaneously
    """
    segments = parse_path_segments(path)
    prefixes = []
    
    for i in range(len(segments)):
        # Indexed prefix
        prefix = '.'.join(segments[:i+1])
        prefixes.append(prefix)
        
        # Prefix without index
        segments_without_index = []
        for seg in segments[:i+1]:
            clean_seg = re.sub(r'\[\d+\]', '', seg)
            segments_without_index.append(clean_seg)
        prefix_without_index = '.'.join(segments_without_index)
        if prefix_without_index != prefix and prefix_without_index:
            prefixes.append(prefix_without_index)
    
    return prefixes

def get_meaningful_ie_paths(flattened_records):
    """
    Extract meaningful IE path combinations
    """
    all_paths = set()
    
    for record in flattened_records:
        path = record['field_path']
        
        # 1. Add all prefixes
        prefixes = get_all_prefixes(path)
        all_paths.update(prefixes)
        
        # 2. Add complete path
        all_paths.add(path)
        
        # 3. Add middle section combinations
        segments = parse_path_segments(path)
        
        for start in range(len(segments)):
            for end in range(start + 2, len(segments) + 1):
                sub_segments = segments[start:end]
                sub_path = '.'.join(sub_segments)
                all_paths.add(sub_path)
                
                clean_segments = [re.sub(r'\[\d+\]', '', seg) for seg in sub_segments]
                clean_path = '.'.join(clean_segments)
                if clean_path != sub_path and clean_path:
                    all_paths.add(clean_path)
    
    return all_paths

def extract_ie_name(path):
    """Extract IE name from path"""
    segments = parse_path_segments(path)
    if not segments:
        return ""
    
    last_segment = segments[-1]
    ie_name = re.sub(r'\[\d+\]', '', last_segment)
    return ie_name

def extract_parent_name(path):
    """Extract the name of the parent path"""
    segments = parse_path_segments(path)
    if len(segments) <= 1:
        return ""
    
    parent_segment = segments[-2]
    parent_name = re.sub(r'\[\d+\]', '', parent_segment)
    return parent_name

def path_starts_with(path, prefix):
    """Check if the path starts with the specified prefix"""
    if path == prefix:
        return True
    
    if path.startswith(prefix):
        if len(path) > len(prefix):
            next_char = path[len(prefix)]
            return next_char in ['.', '[']
    
    return False

def path_contains_substring(path, substring):
    """Check if a path contains a certain substring"""
    if substring in path:
        return True
    
    path_clean = re.sub(r'\[\d+\]', '', path)
    substring_clean = re.sub(r'\[\d+\]', '', substring)
    
    return substring_clean in path_clean

def get_matching_records(flattened_records, ie_path):
    """Get all records matching a specific IE path"""
    matching_records = []
    
    for record in flattened_records:
        field_path = record['field_path']
        
        if path_starts_with(field_path, ie_path):
            matching_records.append(record)
            continue
        
        if '.' in ie_path and ie_path not in field_path:
            if path_contains_substring(field_path, ie_path):
                matching_records.append(record)
    
    return matching_records

def split_into_continuous_groups(records):
    """
    Group records by field_id continuity
    Core improvement: Ensure that field_ids within each IE are consecutive
    """
    if not records:
        return []
    
    # Sort by field_id
    sorted_records = sorted(records, key=lambda x: x['field_id'])
    
    groups = []
    current_group = [sorted_records[0]]
    
    for i in range(1, len(sorted_records)):
        prev_id = sorted_records[i-1]['field_id']
        curr_id = sorted_records[i]['field_id']
        
        if curr_id == prev_id + 1:
            # Continuous, add to current group
            current_group.append(sorted_records[i])
        else:
            # Discontinuous, save current group and start new group
            if len(current_group) > 0:
                groups.append(current_group[:])
            current_group = [sorted_records[i]]
    
    # Save the last group
    if len(current_group) > 0:
        groups.append(current_group)
    
    return groups

def get_field_id_prefix(records):
    """Generate filename prefix based on field_id in the record"""
    field_ids = [r['field_id'] for r in records if 'field_id' in r]
    
    if not field_ids:
        return ""
    
    unique_ids = sorted(set(field_ids))
    
    if len(unique_ids) == 1:
        return str(unique_ids[0])
    else:
        return f"{unique_ids[0]}_{unique_ids[-1]}"

def extract_ies(input_file, output_dir, min_fields=3, max_fields=20, ensure_continuous=True):
    """
    Main function: Extract all IE and save to file
    
    Args:
        input_file: Input flattened JSON file
        output_dir: Output directory
        min_fields: Minimum number of fields that IE must contain
        max_fields: Maximum number of fields that IE can contain
        ensure_continuous: Whether to ensure field_id continuity (⭐new parameter)
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Read flattened JSON file
    with open(input_file, 'r', encoding='utf-8') as f:
        flattened_records = json.load(f)
    
    print(f"Read {len(flattened_records)} field records")
    
    # Collect all meaningful IE paths
    print("Analyzing path structure...")
    all_ie_paths = get_meaningful_ie_paths(flattened_records)
    print(f"Found {len(all_ie_paths)} possible IE paths")
    
    # For each IE path, collect the matching records
    print("Matching records...")
    ie_map = {}
    for ie_path in sorted(all_ie_paths):
        matching_records = get_matching_records(flattened_records, ie_path)
        
        if len(matching_records) >= min_fields:
            ie_map[ie_path] = matching_records
    
    print(f"{len(ie_map)} IEs remaining after initial screening")
    
    # New: Group by continuity
    if ensure_continuous:
        print("Grouping by field_id continuity...")
        continuous_ie_map = {}
        split_count = 0
        
        for ie_path, records in ie_map.items():
            groups = split_into_continuous_groups(records)
            
            if len(groups) > 1:
                split_count += 1
            
            # Create an IE for each consecutive group
            for group_idx, group in enumerate(groups):
                # Filter field count range
                if min_fields <= len(group) <= max_fields:
                    if len(groups) == 1:
                        # Only one group, use the original path name
                        continuous_ie_map[ie_path] = group
                    else:
                        # Multiple groups, add group number
                        new_path = f"{ie_path}_group{group_idx}"
                        continuous_ie_map[new_path] = group
        
        print(f"- Number of split IEs: {split_count}")
        print(f"- Remaining after continuity filtering: {len(continuous_ie_map)} IEs")
        ie_map = continuous_ie_map
    else:
        # Filter by field count only
        ie_map = {k: v for k, v in ie_map.items() 
                  if min_fields <= len(v) <= max_fields}
        print(f"{len(ie_map)} IEs remaining after field filtering")
    
    # Handle filename conflicts and save files
    used_filenames = {}
    saved_count = 0
    duplicate_count = 0
    
    for ie_path, records in sorted(ie_map.items()):
        ie_name = extract_ie_name(ie_path)
        if not ie_name:
            ie_name = "root"
        
        # Generate field_id prefix
        field_id_prefix = get_field_id_prefix(records)
        
        # Handle filename conflicts
        base_filename = ie_name
        
        if base_filename in used_filenames:
            duplicate_count += 1
            parent_name = extract_parent_name(ie_path)
            if parent_name:
                filename = f"{parent_name}_{ie_name}"
            else:
                count = 2
                while f"{ie_name}_{count}" in [v for v in used_filenames.values()]:
                    count += 1
                filename = f"{ie_name}_{count}"
        else:
            filename = base_filename
        
        used_filenames[base_filename] = filename
        
        # Add field_id prefix
        if field_id_prefix:
            final_filename = f"{field_id_prefix}_{filename}"
        else:
            final_filename = filename
        
        # Save to file
        output_file = os.path.join(output_dir, f"{final_filename}.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        
        saved_count += 1
        
        if saved_count % 100 == 0:
            print(f"Saved {saved_count} IE...")
    
    print(f"Extraction complete!")
    print(f"="*80)
    print(f"Statistical Information:")
    print(f"- Number of input fields: {len(flattened_records)}")
    print(f"- Number of IE paths found: {len(all_ie_paths)}")
    print(f"- Number of saved IE files: {saved_count}")
    print(f"- Field count range: {min_fields}-{max_fields}")
    print(f"  - Continuity Requirement: {'Yes' if ensure_continuous else 'No'}")
    print(f"- Number of filename conflicts: {duplicate_count}")
    print(f"- Output directory: {output_dir}")

def main():
    import sys
    
    input_file = "../02_flattened.json"
    output_dir = "../outputs/00_extracted_IEs_id"  # Use the original directory
    
    if not os.path.exists(input_file):
        print(f"Error: Input file {input_file} not found")
        return
    
    # Ensure continuity by default
    min_fields = 3
    max_fields = 50  # A bit looser
    ensure_continuous = True  # Enable continuity check by default
    
    # Command line argument parsing
    for arg in sys.argv:
        if arg.startswith('--min-fields='):
            min_fields = int(arg.split('=')[1])
        elif arg.startswith('--max-fields='):
            max_fields = int(arg.split('=')[1])
        elif arg == '--no-continuous':
            ensure_continuous = False
    
    print(f"Parameter Settings:")
    print(f"- Minimum number of fields: {min_fields}")
    print(f"- Maximum number of fields: {max_fields}")
    print(f"- Ensure continuity: {ensure_continuous}")
    print()
    
    extract_ies(input_file, output_dir, 
                min_fields=min_fields, 
                max_fields=max_fields,
                ensure_continuous=ensure_continuous)
    print("Extraction complete!")

if __name__ == "__main__":
    main()