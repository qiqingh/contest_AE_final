#!/usr/bin/env python3
"""
Batch Refactoring Script - with Detailed Debug Information
"""
import json
import os
import re
import sys
from datetime import datetime

# Input and output directories
FLATTENED_DIR = "../../../toolchain5_dsl_to_testcase/output/test_cases_intra_ie"
METADATA_FILE = "../../02_metadata.json"
OUTPUT_DIR = "../output/03_reconstruct"
DIAGNOSIS_FILE = "../diagnosis/reconstruct.txt"

def log_both(log_file, message):
    """Output to both log file and console simultaneously"""
    print(message)
    log_file.write(message + "\n")
    log_file.flush()  # Write immediately to prevent buffering

def reconstruct_from_metadata(metadata, current_path=""):
    """
    Recursively reconstruct the skeleton of the original nested structure based on metadata.
    
    metadata is a dict where keys are the complete paths of each node and values are the metadata information of that node.
    If metadata[current_path] contains "structure_type", it indicates that the node is a container,
    Otherwise, it is treated as a leaf node and returns None (which will be filled by flattened records later).
    """
    if current_path not in metadata:
        return None
    info = metadata[current_path]
    if "structure_type" not in info:
        # Leaf node
        return None
    stype = info["structure_type"]
    if stype == "dict":
        result = {}
        keys = info.get("keys", [])
        for key in keys:
            child_path = f"{current_path}.{key}" if current_path else key
            result[key] = reconstruct_from_metadata(metadata, child_path)
        return result
    elif stype == "list":
        length = info.get("length", 0)
        result = [None] * length
        for i in range(length):
            child_path = f"{current_path}[{i}]" if current_path else f"[{i}]"
            result[i] = reconstruct_from_metadata(metadata, child_path)
        return result
    elif stype == "tuple":
        length = info.get("length", 0)
        temp = [None] * length
        for i in range(length):
            child_path = f"{current_path}[tuple_{i}]" if current_path else f"tuple[{i}]"
            temp[i] = reconstruct_from_metadata(metadata, child_path)
        return tuple(temp)
    else:
        return None

def set_nested_value(nested, field_path, value):
    """
    Insert value into nested object based on field_path.
    Supports path formats like "message[1][1].rrc-TransactionIdentifier".
    
    This function uses regular expressions to extract the key and index from each token, then sets values in the container level by level.
    """
    # Parse field_path and extract segments in the form of key or [index]
    segments = re.findall(r'([^\[\]\.]+)|\[(\d+)\]', field_path)
    current = nested
    for i, (key, index) in enumerate(segments):
        is_last = (i == len(segments) - 1)
        if key:
            # Current segment is dictionary key
            if not isinstance(current, dict):
                raise TypeError(f"Expected dict, but encountered {type(current).__name__} when processing key '{key}'")
            if is_last:
                current[key] = value
            else:
                if key not in current or current[key] is None:
                    # Predict the next segment, create a list if it's a number, otherwise create a dict
                    next_seg = segments[i+1]
                    if next_seg[1] != "":
                        current[key] = []
                    else:
                        current[key] = {}
                current = current[key]
        elif index:
            idx = int(index)
            if not isinstance(current, list):
                raise TypeError(f"Expected list, but encountered {type(current).__name__} when processing index [{idx}]")
            while len(current) <= idx:
                current.append(None)
            if is_last:
                current[idx] = value
            else:
                if current[idx] is None:
                    next_seg = segments[i+1]
                    if next_seg[1] != "":
                        current[idx] = []
                    else:
                        current[idx] = {}
                current = current[idx]
    return nested

def overlay_flattened(skeleton, flattened_records, log_file):
    """
    Based on the flattened records, use the suggested_value for each record (if modified, otherwise use current_value)
    Cover to the corresponding position in the skeleton.
    """
    errors = []
    
    # Check the type of flattened_records
    if not isinstance(flattened_records, list):
        error_msg = f" Error: flattened_records should be a list, but is actually {type(flattened_records).__name__}"
        log_both(log_file, error_msg)
        errors.append(error_msg)
        return skeleton, errors
    
    log_both(log_file, f"Processing {len(flattened_records)} records...")
    
    for idx, record in enumerate(flattened_records):
        # Check the type of each record
        if not isinstance(record, dict):
            error_msg = f" Record # {idx} Error: should be dictionary, but actually is {type(record).__name__}"
            log_both(log_file, error_msg)
            errors.append(error_msg)
            continue
        
        # Check for required fields
        if "field_path" not in record:
            error_msg = f"  Record # {idx} Warning: missing field_path field"
            log_both(log_file, error_msg)
            log_both(log_file, f"Record Content: {record}")
            errors.append(error_msg)
            continue
        
        # Get Value
        val = record.get("suggested_value", record.get("current_value"))
        field_path = record.get("field_path")
        
        if val is None:
            log_both(log_file, f"    记录 # {idx}: The value of {field_path} is None (possibly normal)")
        
        if field_path:
            try:
                skeleton = set_nested_value(skeleton, field_path, val)
                if idx < 5:  # Only print the first 5 entries to avoid too much output
                    log_both(log_file, f"✓ Record #{idx}: {field_path} = {val}")
            except Exception as e:
                error_msg = f" Error setting path {field_path}: {e}"
                log_both(log_file, error_msg)
                errors.append(error_msg)
    
    return skeleton, errors

def process_file(flattened_file, metadata, log_file):
    """Processing a single flattened JSON file"""
    file_name = os.path.basename(flattened_file)
    
    log_both(log_file, "\n" + "="*80)
    log_both(log_file, f" Processing file: {file_name}")
    log_both(log_file, f"Complete path: {flattened_file}")
    log_both(log_file, "="*80)
    
    # ========== Step 1: Read File ==========
    log_both(log_file, "[Step 1] Reading flattened file...")
    try:
        with open(flattened_file, 'r') as f:
            content = f.read()
            log_both(log_file, f"File size: {len(content)} bytes")
            
        # Parse JSON
        flattened_records = json.loads(content)
        
        # Detailed type checking
        log_both(log_file, f"✓ JSON parsing successful")
        log_both(log_file, f"Data type: {type(flattened_records).__name__}")
        
        if isinstance(flattened_records, list):
            log_both(log_file, f"List length: {len(flattened_records)}")
            if len(flattened_records) > 0:
                log_both(log_file, f"Type of the first element: {type(flattened_records[0]).__name__}")
                log_both(log_file, f"First element preview: {str(flattened_records[0])[:200]}")
                
                # Check fields
                if isinstance(flattened_records[0], dict):
                    keys = list(flattened_records[0].keys())
                    log_both(log_file, f"Key of the first element: {keys}")
                    
                    # Check if the expected fields exist
                    has_field_path = "field_path" in flattened_records[0]
                    has_current_value = "current_value" in flattened_records[0]
                    has_suggested_value = "suggested_value" in flattened_records[0]
                    
                    log_both(log_file, f"Field validation:")
                    log_both(log_file, f"    - field_path: {'✓' if has_field_path else '✗'}")
                    log_both(log_file, f"    - current_value: {'✓' if has_current_value else '✗'}")
                    log_both(log_file, f"    - suggested_value: {'✓' if has_suggested_value else '✗'}")
                    
        elif isinstance(flattened_records, dict):
            log_both(log_file, f"  Data is a dictionary, not a list!")
            log_both(log_file, f"Number of dictionary keys: {len(flattened_records)}")
            log_both(log_file, f"First 10 keys: {list(flattened_records.keys())[:10]}")
        else:
            log_both(log_file, f" Data is neither a list nor a dictionary!")
            log_both(log_file, f"Data content: {str(flattened_records)[:500]}")
            
    except json.JSONDecodeError as e:
        log_both(log_file, f" JSON parsing error: {e}")
        return False
    except Exception as e:
        log_both(log_file, f" File read error: {e}")
        return False
    
    # ========== Step 2: Refactor Framework ==========
    log_both(log_file, "[Step 2] Reconstructing structural skeleton based on metadata...")
    try:
        skeleton = reconstruct_from_metadata(metadata, "")
        if skeleton is None:
            skeleton = {}
            log_both(log_file, " Root metadata is empty, using empty dictionary as skeleton")
        else:
            log_both(log_file, f"✓ Skeleton reconstruction successful, type: {type(skeleton).__name__}")
    except Exception as e:
        log_both(log_file, f" Refactoring skeleton error: {e}")
        return False
    
    # ========== Step 3: Overwrite Data ==========
    log_both(log_file, "[Step 3] Overlay the flattened records onto the skeleton...")
    try:
        reconstructed_obj, errors = overlay_flattened(skeleton, flattened_records, log_file)
        
        if errors:
            log_both(log_file, f"\n    {len(errors)} errors occurred during the override process:")
            for i, error in enumerate(errors[:10], 1):  # Show only the first 10 errors
                log_both(log_file, f"    {i}. {error}")
            if len(errors) > 10:
                log_both(log_file, f"... and {len(errors) - 10} more errors")
        else:
            log_both(log_file, " Coverage complete, no errors")
            
    except Exception as e:
        log_both(log_file, f" Coverage process error: {e}")
        import traceback
        log_both(log_file, f"Stack trace:\n{traceback.format_exc()}")
        return False
    
    # ========== Step 4: Save Output ==========
    log_both(log_file, "[Step 4] Saving the refactored file...")
    base_name = os.path.splitext(file_name)[0]
    output_file = os.path.join(OUTPUT_DIR, f"{base_name}_reconstructed.json")
    
    try:
        with open(output_file, 'w') as f:
            json.dump(reconstructed_obj, f, indent=2, ensure_ascii=False)
        log_both(log_file, f"✓ Saved to: {output_file}")
        
        # Check output file size
        output_size = os.path.getsize(output_file)
        log_both(log_file, f"Output file size: {output_size} bytes")
        
        return True
    except Exception as e:
        log_both(log_file, f" File save error: {e}")
        return False

def main():
    # Create output directory and diagnostic directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DIAGNOSIS_FILE), exist_ok=True)
    
    # Open diagnostic log file
    with open(DIAGNOSIS_FILE, 'w') as log_file:
        log_both(log_file, "="*80)
        log_both(log_file, "Batch Refactoring Processing - Detailed Debug Version")
        log_both(log_file, "="*80)
        log_both(log_file, f"Start time: {datetime.now()}")
        log_both(log_file, f"Flattened file directory: {FLATTENED_DIR}")
        log_both(log_file, f"Metadata file: {METADATA_FILE}")
        log_both(log_file, f"Output directory: {OUTPUT_DIR}")
        log_both(log_file, "")
        
        # ========== Loading Metadata ==========
        log_both(log_file, "="*80)
        log_both(log_file, "[Initializing] Loading metadata file...")
        log_both(log_file, "="*80)
        
        try:
            with open(METADATA_FILE, 'r') as f:
                metadata = json.load(f)
            log_both(log_file, f"✓ Successfully loaded metadata file")
            log_both(log_file, f"Number of node records: {len(metadata)}")
            log_both(log_file, f"First 5 keys: {list(metadata.keys())[:5]}")
        except FileNotFoundError:
            log_both(log_file, f" Metadata file does not exist: {METADATA_FILE}")
            return
        except Exception as e:
            log_both(log_file, f" Error reading metadata file: {e}")
            return
        
        # ========== Scanning Files ==========
        log_both(log_file, "\n" + "="*80)
        log_both(log_file, "[Initialization] Scanning files to be processed...")
        log_both(log_file, "="*80)
        
        if not os.path.exists(FLATTENED_DIR):
            log_both(log_file, f" Flattened file directory does not exist: {FLATTENED_DIR}")
            return
        
        try:
            all_files = os.listdir(FLATTENED_DIR)
            json_files = [
                os.path.join(FLATTENED_DIR, f) 
                for f in all_files 
                if f.endswith('.json') and os.path.isfile(os.path.join(FLATTENED_DIR, f))
            ]
            
            log_both(log_file, f"Total number of files in directory: {len(all_files)}")
            log_both(log_file, f"Number of JSON files: {len(json_files)}")
            
            if len(json_files) == 0:
                log_both(log_file, f"  No JSON files found!")
                log_both(log_file, f"Directory contents: {all_files[:20]}")
                return
            
            # Show the first few files
            log_both(log_file, f"The first 5 files:")
            for i, f in enumerate(json_files[:5], 1):
                log_both(log_file, f"    {i}. {os.path.basename(f)}")
                
        except Exception as e:
            log_both(log_file, f" Directory scan error: {e}")
            return
        
        # ========== Processing File ==========
        log_both(log_file, "\n" + "="*80)
        log_both(log_file, f"[Processing] Starting to process {len(json_files)} files...")
        log_both(log_file, "="*80)
        
        success_count = 0
        failed_files = []
        
        for i, file_path in enumerate(json_files, 1):
            log_both(log_file, f"Progress: [{i}/{len(json_files)}]")
            
            if process_file(file_path, metadata, log_file):
                success_count += 1
                log_both(log_file, f"✓ Success")
            else:
                failed_files.append(os.path.basename(file_path))
                log_both(log_file, f"✗ Failed")
        
        # ========== Summary ==========
        log_both(log_file, "\n" + "="*80)
        log_both(log_file, "Processing Complete - Summary")
        log_both(log_file, "="*80)
        log_both(log_file, f"End time: {datetime.now()}")
        log_both(log_file, f"Total number of files: {len(json_files)}")
        log_both(log_file, f"Success: {success_count}")
        log_both(log_file, f"Failed: {len(failed_files)}")
        
        if failed_files:
            log_both(log_file, f"Failed files:")
            for f in failed_files:
                log_both(log_file, f"  - {f}")
        
        log_both(log_file, "\n" + "="*80)
        log_both(log_file, f"Detailed logs have been saved to: {DIAGNOSIS_FILE}")

if __name__ == "__main__":
    main()