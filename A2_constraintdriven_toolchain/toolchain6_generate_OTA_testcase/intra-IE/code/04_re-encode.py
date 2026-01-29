#!/usr/bin/env python
import json
import sys
import os
from datetime import datetime
from pycrate_asn1dir import RRCNR
from pycrate_asn1rt.utils import bitstr_to_bytes

# Define input and output directories
INPUT_DIR = "../output/03_reconstruct"
OUTPUT_DIR = "../output/04_reencode"
DIAGNOSIS_FILE = "../diagnosis/reencode_asn_check.txt"

def fix_bitstrings(obj):
    """
    If there is a string in the format "010101..." in the JSON, use bitstr_to_bytes to convert it to byte data.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and set(v) <= {"0", "1"}:
                try:
                    obj[k] = bitstr_to_bytes(v)
                except Exception as e:
                    print(f"[DEBUG] fix_bitstrings: Error converting {k}: {e}", flush=True)
            else:
                obj[k] = fix_bitstrings(v)
        return obj
    elif isinstance(obj, list):
        return [fix_bitstrings(x) for x in obj]
    else:
        return obj

def restore_tuples(obj):
    """
    Convert lists like ["setup", {...}] back to tuples ("setup", {...}).
    """
    if isinstance(obj, list):
        if len(obj) == 2 and isinstance(obj[0], str):
            return (obj[0], restore_tuples(obj[1]))
        else:
            return [restore_tuples(x) for x in obj]
    elif isinstance(obj, dict):
        return {k: restore_tuples(v) for k, v in obj.items()}
    else:
        return obj

def recursive_convert_bitstring_lists(obj):
    """
    Recursively traverse object:
    If a list is encountered with a length of 2 and the second element is an int less than 100 (typically the bit length of a BIT STRING does not exceed 100),
    considers this to be a BIT STRING representation and converts it to a tuple.
    Process each element in dict, list, and tuple simultaneously.
    """
    if isinstance(obj, list):
        new_list = [recursive_convert_bitstring_lists(x) for x in obj]
        if len(new_list) == 2 and isinstance(new_list[1], int) and new_list[1] < 100:
            try:
                return (int(new_list[0]), int(new_list[1]))
            except Exception as e:
                print(f"[DEBUG] Conversion failed {new_list}: {e}", flush=True)
                return new_list
        else:
            return new_list
    elif isinstance(obj, dict):
        return {k: recursive_convert_bitstring_lists(v) for k, v in obj.items()}
    elif isinstance(obj, tuple):
        return tuple(recursive_convert_bitstring_lists(x) for x in obj)
    else:
        return obj

def reencode_from_json(json_file, field_name="DL_CCCH_Message", log_file=None):
    """Re-encode single JSON file"""
    file_name = os.path.basename(json_file)
    
    # Record processing status
    log_message = f"\n[{datetime.now()}] 处理文件: {file_name}\n{'='*50}\n"
    if log_file:
        log_file.write(log_message)
    print(log_message, flush=True)
    
    try:
        # 1. Read JSON data
        with open(json_file, 'r') as f:
            asn1_dict = json.load(f)
        
        # 2. First process the bit string that may be stored as "010101..."
        asn1_dict = fix_bitstrings(asn1_dict)
        # 3. Convert lists like ["setup", {...}] to tuples
        asn1_dict = restore_tuples(asn1_dict)
        # 4. Recursively convert all lists of length 2 that conform to BIT STRING characteristics into tuples
        asn1_dict = recursive_convert_bitstring_lists(asn1_dict)
        
        # 5. Obtain ASN.1 structure definition
        try:
            sch = getattr(RRCNR.NR_RRC_Definitions, field_name)
        except AttributeError:
            error_msg = f"[ERROR] {field_name} not found in ASN.1 structure"
            if log_file:
                log_file.write(error_msg + "\n")
            print(error_msg, flush=True)
            return None
        
        # 6. Restore ASN.1 object using the converted dictionary
        try:
            # ===== Adding debug information - before set_val =====
            if log_file:
                debug_msg = f"[DEBUG] Field type: {type(sch)}\n"
                debug_msg += f"[DEBUG] _SAFE_VAL: {getattr(sch, '_SAFE_VAL', 'N/A')}\n"
                debug_msg += f"[DEBUG] _SAFE_BND: {getattr(sch, '_SAFE_BND', 'N/A')}\n"
                debug_msg += f"[DEBUG] _SAFE_BNDTAB: {getattr(sch, '_SAFE_BNDTAB', 'N/A')}\n"
                debug_msg += f"[DEBUG] _const_val: {getattr(sch, '_const_val', 'N/A')}\n"
                
                # If there are constraints, check extensibility
                if hasattr(sch, '_const_val') and sch._const_val:
                    debug_msg += f"[DEBUG] 约束扩展性 _const_val.ext: {getattr(sch._const_val, 'ext', 'N/A')}\n"
                    debug_msg += f"[DEBUG] Constraint content: {sch._const_val}\n"
                else:
                    debug_msg += f"[DEBUG] No constraint definition found\n"
                
                debug_msg += f"[DEBUG] Input data type: {type(asn1_dict)}\n"
                debug_msg += f"[DEBUG] Input data content: {str(asn1_dict)[:200]}...\n"
                log_file.write(debug_msg)
            # ===== End of Debug Information =====
            
            sch.set_val(asn1_dict)
            
            # ===== Optional: Check once more after set_val =====
            if log_file and hasattr(sch, '_val'):
                post_debug = f"[DEBUG] Value after set_val: {str(sch._val)[:200]}...\n"
                post_debug += f"[DEBUG] set_val executed successfully\n"
                log_file.write(post_debug)
            # ===== End of Debug Information =====
            
        except Exception as e:
            error_msg = f"[ERROR] Error occurred while recovering ASN.1 object: {e}"
            if log_file:
                log_file.write(error_msg + "\n")
            print(error_msg, flush=True)
            return None
        
        # 7. Re-encode to UPER format
        try:
            encoded_bytes = sch.to_uper()
            success_msg = f"[SUCCESS] File {file_name} successfully re-encoded"
            if log_file:
                log_file.write(success_msg + "\n")
            print(success_msg, flush=True)
            return encoded_bytes
        except Exception as e:
            error_msg = f"[ERROR] Error encoding ASN.1 object: {e}"
            if log_file:
                log_file.write(error_msg + "\n")
            print(error_msg, flush=True)
            return None
            
    except Exception as e:
        error_msg = f"[ERROR] Error processing file {file_name}: {e}"
        if log_file:
            log_file.write(error_msg + "\n")
        print(error_msg, flush=True)
        return None

def process_all_files(field_name="DL_CCCH_Message"):
    """Batch process all JSON files in a directory"""
    # Create output directory and diagnostic directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DIAGNOSIS_FILE), exist_ok=True)
    
    # Open log file
    with open(DIAGNOSIS_FILE, 'w') as log_file:
        log_file.write(f"[{datetime.now()}] Starting batch re-encoding process\n")
        log_file.write(f"Input directory: {INPUT_DIR}\n")
        log_file.write(f"Output directory: {OUTPUT_DIR}\n")
        log_file.write(f"ASN.1 field name: {field_name}\n\n")
        
        # Get all JSON files
        json_files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.json')]
        log_file.write(f"Found {len(json_files)} JSON files to process\n\n")
        
        success_count = 0
        for json_file in json_files:
            input_path = os.path.join(INPUT_DIR, json_file)
            
            # Encoded file
            encoded_bytes = reencode_from_json(input_path, field_name, log_file)
            
            if encoded_bytes:
                # Generate output filename - remove .json suffix, add .hex
                base_name = os.path.splitext(json_file)[0]
                output_file = os.path.join(OUTPUT_DIR, f"{base_name}.hex")
                
                # Save encoding results
                try:
                    with open(output_file, 'w') as f:
                        f.write(encoded_bytes.hex())
                    success_msg = f"[INFO] Encoding results have been saved to {output_file}"
                    log_file.write(success_msg + "\n")
                    print(success_msg, flush=True)
                    success_count += 1
                except Exception as e:
                    error_msg = f"[ERROR] Error saving results to file {output_file}: {e}"
                    log_file.write(error_msg + "\n")
                    print(error_msg, flush=True)
        
        # Record Processing Summary
        summary = f"\n[{datetime.now()}] Processing completed\n"
        summary += f"Successfully processed: {success_count}/{len(json_files)} files\n"
        log_file.write(summary)
        print(summary, flush=True)

if __name__ == "__main__":
    # If command line arguments are provided, use them as field_name, otherwise use the default value.
    field_name = sys.argv[1] if len(sys.argv) > 1 else "DL_CCCH_Message"
    process_all_files(field_name)