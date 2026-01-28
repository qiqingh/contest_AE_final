#!/usr/bin/env python3
"""
Generate mutation test cases based on field importance and ASN.1 types.
Updates field values in original files.
Supported types: INTEGER, ENUMERATED, CHOICE, BOOL
"""

import os
import json
import random
import string
import math
import shutil
from typing import Dict, Any, List, Tuple, Optional, Union

def format_value_for_comparison(value: Any, field_type: str) -> Any:
    """
    Format value for comparison. Ensures values with different representations can be compared correctly.
    
    Args:
        value: Value to format
        field_type: Field type
        
    Returns:
        Formatted value
    """
    try:
        if field_type == "int":
            # Convert to integer for comparison
            return int(value) if value is not None else None
        elif field_type == "str":
            # Convert to string for comparison
            return str(value) if value is not None else ""
        elif field_type == "bool":
            # Handle different representations of boolean values
            if isinstance(value, bool):
                return value
            elif isinstance(value, str):
                return value.lower() in ('true', 'yes', '1')
            elif isinstance(value, (int, float)):
                return bool(value)
            else:
                return bool(value)
        else:
            # For other types, return as-is
            return value
    except (ValueError, TypeError):
        # If conversion fails, return original value
        return value

def generate_integer_mutations(field_info: Dict[str, Any], num_mutations: int) -> List[Dict[str, Any]]:
    """
    Generate mutations for INTEGER type fields, focusing on boundary values.
    For large ranges (>100), add quartile test points.
    
    Args:
        field_info: Field information
        num_mutations: Number of mutations to generate (ignored in this version, always returns all boundary values)
        
    Returns:
        List of mutations
    """
    # Set 10-second timeout to prevent potential infinite loops
    import signal

    def timeout_handler(signum, frame):
        raise TimeoutError("INTEGER mutation generation timeout")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(5)  # 5-second timeout
    
    try:
        # Get field range
        field_rule = field_info["asn1_rules"]["rules"][0]
        min_val, max_val = field_rule["range"]
        
        # Calculate range size
        range_size = max_val - min_val
        
        # Create boundary value mutation list
        mutations = []
        
        # Minimum value
        mutations.append({
            "mutation_value": min_val,
            "mutation_type": "min_value",
            "description": f"Minimum valid value ({min_val})"
        })
        
        # Maximum value
        mutations.append({
            "mutation_value": max_val,
            "mutation_type": "max_value",
            "description": f"Maximum valid value ({max_val})"
        })
        
        # If type allows, add min-1 (out of lower bound)
        if min_val > -2**31:  # Assume INTEGER type supports minimum 32-bit signed integer
            mutations.append({
                "mutation_value": min_val - 1,
                "mutation_type": "min_minus_one",
                "description": f"Min minus one ({min_val-1}) - Out of lower bound"
            })
        
        # If type allows, add max+1 (out of upper bound)
        if max_val < 2**31 - 1:  # Assume INTEGER type supports maximum 32-bit signed integer
            mutations.append({
                "mutation_value": max_val + 1,
                "mutation_type": "max_plus_one",
                "description": f"Max plus one ({max_val+1}) - Out of upper bound"
            })
        
        # For ranges > 100, add finer-grained test points
        if range_size > 100:
            # Middle value
            mid_val = min_val + range_size // 2
            mutations.append({
                "mutation_value": mid_val,
                "mutation_type": "mid_value",
                "description": f"Middle value ({mid_val})"
            })
            
            # First quartile: (min + mid) / 2
            q1_val = min_val + (mid_val - min_val) // 2
            mutations.append({
                "mutation_value": q1_val,
                "mutation_type": "q1_value",
                "description": f"First quartile ({q1_val})"
            })
            
            # Third quartile: (mid + max) / 2
            q3_val = mid_val + (max_val - mid_val) // 2
            mutations.append({
                "mutation_value": q3_val,
                "mutation_type": "q3_value",
                "description": f"Third quartile ({q3_val})"
            })
            
            print(f"  Large range INTEGER ({range_size}): Added middle and quartile test points")
        
        elif range_size > 2:
            # For smaller ranges, only add middle value
            mid_val = min_val + range_size // 2
            mutations.append({
                "mutation_value": mid_val,
                "mutation_type": "mid_value",
                "description": f"Middle value ({mid_val})"
            })
        
        signal.alarm(0)  # Cancel timeout
        return mutations
    
    except TimeoutError as e:
        print(f"  Warning: {e}, returning simplified mutation set")
        # Return simplified mutations (only min and max values)
        return [
            {
                "mutation_value": field_info["asn1_rules"]["rules"][0]["range"][0],  # Min value
                "mutation_type": "min_value",
                "description": "Minimum valid value (timeout simplified)"
            },
            {
                "mutation_value": field_info["asn1_rules"]["rules"][0]["range"][1],  # Max value
                "mutation_type": "max_value",
                "description": "Maximum valid value (timeout simplified)"
            }
        ]
    except Exception as e:
        print(f"  Warning: Integer mutation generation error: {e}")
        signal.alarm(0)  # Cancel timeout
        # Return empty list
        return []
    finally:
        signal.alarm(0)  # Ensure timeout is cancelled

def generate_bool_mutations(field_info: Dict[str, Any], original_field: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate mutations for BOOL type fields, flipping boolean values.
    
    Args:
        field_info: Field information
        original_field: Original field data (to get current value)
        
    Returns:
        List of mutations
    """
    mutations = []
    
    # Get current value
    current_value = original_field.get("current_value")
    field_type = original_field.get("field_type", "")
    
    # Format current value as boolean type
    current_bool = format_value_for_comparison(current_value, field_type)
    
    # Generate flipped value
    flipped_value = not current_bool
    
    mutations.append({
        "mutation_value": flipped_value,
        "mutation_type": "bool_flip",
        "description": f"Boolean flip ({current_bool} -> {flipped_value})"
    })
    
    print(f"  Generated flip mutation for BOOL field: {current_bool} -> {flipped_value}")
    return mutations

def generate_enumerated_mutations(field_info: Dict[str, Any], num_mutations: int) -> List[Dict[str, Any]]:
    """
    Generate mutations for ENUMERATED type fields using fixed 3-sample strategy.
    - Always samples: first, middle, last
    - For 1 option: 1 sample
    - For 2 options: 2 samples (first, last)
    - For 3+ options: 3 samples (first, middle, last)
    
    Args:
        field_info: Field information
        num_mutations: Number of mutations to generate (ignored in this version)
        
    Returns:
        List of mutations
    """
    mutations = []
    
    # Get enumeration options
    field_rule = field_info["asn1_rules"]["rules"][0]
    available_options = field_rule.get("available_options", [])
    
    # If no available options, try to infer from range
    if not available_options and "range" in field_rule:
        min_val, max_val = field_rule["range"]
        available_options = list(range(min_val, max_val + 1))
    
    # If no enumeration options, return empty list
    if not available_options:
        print(f"Warning: ENUMERATED type field {field_info.get('field_name', 'Unknown')} has no available options.")
        return []
    
    num_options = len(available_options)
    
    # Fixed 3-sample strategy
    if num_options == 1:
        sampled_indices = [0]
        print(f"  ENUM options=1, sampling 1 point")
    elif num_options == 2:
        sampled_indices = [0, 1]
        print(f"  ENUM options=2, sampling 2 points (first, last)")
    else:  # 3+
        sampled_indices = [
            0,                          # First
            num_options // 2,           # Middle
            num_options - 1             # Last
        ]
        print(f"  ENUM options={num_options}, sampling 3 points (first, middle, last)")
    
    # Create mutations from sampled indices
    for idx in sampled_indices:
        option = available_options[idx]
        
        # Determine mutation type
        if idx == 0:
            mutation_type = "enum_min"
            description = f"Enum minimum value ({option})"
        elif idx == num_options - 1:
            mutation_type = "enum_max"
            description = f"Enum maximum value ({option})"
        else:
            mutation_type = "enum_mid"
            description = f"Enum middle value ({option}) [index {idx}/{num_options-1}]"
        
        mutations.append({
            "mutation_value": option,
            "mutation_type": mutation_type,
            "description": description
        })
    
    return mutations

def generate_choice_mutations(field_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate mutations for CHOICE type fields, traversing all possible branch options.
    
    Args:
        field_info: Field information
        
    Returns:
        List of mutations
    """
    mutations = []
    
    # Get available branches for CHOICE
    field_rule = field_info["asn1_rules"]["rules"][0]
    available_options = field_rule.get("available_options", [])
    
    # If no available_options, try to get from branches field
    if not available_options and "branches" in field_rule:
        available_options = [branch.get("name") if isinstance(branch, dict) else branch 
                           for branch in field_rule["branches"]]
    
    # If still none, try to infer from range (in some cases CHOICE may use integer index)
    if not available_options and "range" in field_rule:
        min_val, max_val = field_rule["range"]
        available_options = list(range(min_val, max_val + 1))
    
    if not available_options:
        print(f"Warning: CHOICE type field {field_info.get('field_name', 'Unknown')} has no available branches.")
        return []
    
    # Create mutation for each branch
    for i, branch in enumerate(available_options):
        # Determine mutation type
        if i == 0:
            mutation_type = "choice_first"
            description = f"CHOICE first branch ({branch})"
        elif i == len(available_options) - 1:
            mutation_type = "choice_last"
            description = f"CHOICE last branch ({branch})"
        else:
            mutation_type = "choice_branch"
            description = f"CHOICE branch ({branch})"
        
        mutations.append({
            "mutation_value": branch,
            "mutation_type": mutation_type,
            "description": description
        })
    
    print(f"  Generated {len(mutations)} branch mutations for CHOICE field")
    return mutations

def generate_mutations(field_info: Dict[str, Any], original_field: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Generate mutations based on field information.
    
    Args:
        field_info: Field information
        original_field: Original field data (required for BOOL type)
        
    Returns:
        List of mutations
    """
    # Get field type
    field_type = "UNKNOWN"
    if "asn1_rules" in field_info and "rules" in field_info["asn1_rules"] and field_info["asn1_rules"]["rules"]:
        field_type = field_info["asn1_rules"]["rules"][0].get("type", "UNKNOWN")
    
    # Generate mutations based on type, supporting multiple type representations
    if field_type in ["INTEGER", "INT"]:
        # For INTEGER type, generate all boundary values
        return generate_integer_mutations(field_info, -1)
    elif field_type in ["ENUMERATED", "ENUM"]:
        # For ENUMERATED type, intelligently sample enum values
        return generate_enumerated_mutations(field_info, -1)
    elif field_type in ["CHOICE"]:
        # For CHOICE type, traverse all branches
        return generate_choice_mutations(field_info)
    elif field_type in ["BOOL", "BOOLEAN"]:
        # For BOOL type, flip boolean value
        if original_field is None:
            print(f"Warning: BOOL type field requires original field data")
            return []
        return generate_bool_mutations(field_info, original_field)
    else:
        print(f"Skipping unsupported field type {field_type}, field {field_info.get('field_name', 'Unknown')}")
        return []

def load_original_data(original_file_path: str) -> List[Dict[str, Any]]:
    """
    Load original data file.
    
    Args:
        original_file_path: Original data file path
        
    Returns:
        List of original data
    """
    try:
        with open(original_file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading original data file: {e}")
        return []

def format_value_by_type(value: Any, field_type: str) -> Any:
    """
    Format value according to field type.
    
    Args:
        value: Raw value
        field_type: Field type
        
    Returns:
        Formatted value
    """
    if field_type == "int":
        return int(value)
    elif field_type == "str":
        return str(value)
    elif field_type == "bool":
        return bool(value)
    else:
        # For other types, keep as-is
        return value

def find_field_in_original_data(field_id: int, original_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Find field in original data.
    
    Args:
        field_id: Field ID
        original_data: Original data
        
    Returns:
        Found field, or None if not found
    """
    for field in original_data:
        if field.get("field_id") == field_id:
            return field
    return None

def create_mutation_file(field_id: int, mutation: Dict[str, Any], 
                          original_data: List[Dict[str, Any]], 
                          output_dir: str, mutation_index: int) -> bool:
    """
    Create a mutation file.
    
    Args:
        field_id: Field ID
        mutation: Mutation information
        original_data: Original data
        output_dir: Output directory
        mutation_index: Mutation index
        
    Returns:
        Whether successfully created
    """
    # Copy original data
    mutated_data = []
    for field in original_data:
        field_copy = field.copy()
        # If this is the target field, update suggested_value
        if field_copy.get("field_id") == field_id:
            # Format value according to field type
            field_type = field_copy.get("field_type", "")
            mutation_value = mutation["mutation_value"]
            
            # Set correct format according to field_type
            field_copy["suggested_value"] = format_value_by_type(mutation_value, field_type)
            # Add mutation information
            field_copy["mutation_info"] = {
                "original_value": field_copy.get("current_value", None),
                "mutation_type": mutation["mutation_type"],
                "description": mutation["description"]
            }
            
        mutated_data.append(field_copy)
    
    # Create output filename
    output_file = f"{field_id}_mut{mutation_index}.json"
    output_path = os.path.join(output_dir, output_file)
    
    # Save to file
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(mutated_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving mutation file: {e}")
        return False

def process_field_files(input_dir: str, original_file_path: str, output_dir: str) -> Tuple[int, int, int, int]:
    """
    Process field files and generate mutations.
    
    Args:
        input_dir: Input directory
        original_file_path: Original data file path
        output_dir: Output directory
        
    Returns:
        (processed files, generated mutations, skipped files, same value skipped)
    """
    processed_count = 0
    mutations_count = 0
    skipped_count = 0
    same_value_skipped = 0
    timeout_count = 0
    problem_files = []
    
    # Statistics by type
    type_stats = {
        "INTEGER": {"processed": 0, "mutations": 0},
        "ENUMERATED": {"processed": 0, "mutations": 0},
        "CHOICE": {"processed": 0, "mutations": 0},
        "BOOL": {"processed": 0, "mutations": 0},
        "UNKNOWN": {"processed": 0, "mutations": 0}
    }
    
    # Create diagnosis directory
    diagnosis_dir = "./diagnosis"
    os.makedirs(diagnosis_dir, exist_ok=True)
    
    # Load original data
    original_data = load_original_data(original_file_path)
    if not original_data:
        print("Unable to load original data, exiting.")
        return 0, 0, 0, 0
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all JSON files
    try:
        files = [f for f in os.listdir(input_dir) if f.endswith('.json')]
        total_files = len(files)
        print(f"Found {total_files} field files")
        
        # Sort by filename (numeric) for easier locating
        files.sort(key=lambda x: int(os.path.splitext(x)[0]) if os.path.splitext(x)[0].isdigit() else float('inf'))
        
        for file_index, filename in enumerate(files, 1):
            file_path = os.path.join(input_dir, filename)
            
            # Show processing progress
            print(f"\nProcessing file {file_index}/{total_files}: {filename}")
            
            # Timeout mechanism and warning
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError(f"Processing file {filename} timeout")

            # Set 5-second timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(5)
            
            try:
                # Get field ID
                field_id = int(os.path.splitext(filename)[0])
                
                # Read field information
                with open(file_path, 'r') as f:
                    field_info = json.load(f)
                
                # Find corresponding field in original data
                original_field = find_field_in_original_data(field_id, original_data)
                if not original_field:
                    print(f"Field ID {field_id} not found in original data, skipping {filename}")
                    skipped_count += 1
                    # Copy problem file to diagnosis directory
                    try:
                        shutil.copy2(file_path, os.path.join(diagnosis_dir, filename))
                    except:
                        pass
                    continue
                
                # Get original value and field type
                current_value = original_field.get("current_value")
                field_type = original_field.get("field_type", "Unknown")
                
                # Get ASN.1 type
                asn1_type = "UNKNOWN"
                if "asn1_rules" in field_info and "rules" in field_info["asn1_rules"] and field_info["asn1_rules"]["rules"]:
                    asn1_type = field_info["asn1_rules"]["rules"][0].get("type", "UNKNOWN")
                
                # Print processing stage
                print(f"  Field ID: {field_id}, field_type: {field_type}, ASN.1 type: {asn1_type}")
                print(f"  Current value: {current_value}")
                print(f"  Generating mutations...")
                
                # Generate mutations (pass original_field for BOOL type)
                try:
                    mutations = generate_mutations(field_info, original_field)
                except Exception as e:
                    print(f"Error generating mutations for field {filename}: {e}")
                    skipped_count += 1
                    problem_files.append((filename, f"Mutation generation error: {e}"))
                    # Copy problem file to diagnosis directory
                    try:
                        shutil.copy2(file_path, os.path.join(diagnosis_dir, filename))
                    except:
                        pass
                    continue
                
                if not mutations:
                    print(f"Skipping {filename} (no mutations needed)")
                    skipped_count += 1
                    continue
                
                # Get field information
                field_name = field_info.get("field_name", original_field.get("field_name", "Unknown"))
                
                # Print processing stage
                print(f"  Filtering same-value mutations... (generated {len(mutations)} mutations)")
                
                # Filter out mutations with same value as original
                filtered_mutations = []
                for mutation in mutations:
                    try:
                        mutation_value = mutation["mutation_value"]
                        
                        # Format mutation value and original value for comparison
                        formatted_mutation = format_value_for_comparison(mutation_value, field_type)
                        formatted_current = format_value_for_comparison(current_value, field_type)
                        
                        # Skip if mutation value is same as original value
                        if formatted_mutation == formatted_current:
                            print(f"  Skipped mutation: {mutation['description']} (same as original value: {current_value})")
                            same_value_skipped += 1
                        else:
                            filtered_mutations.append(mutation)
                    except Exception as e:
                        print(f"  Error comparing mutation values: {e}")
                        # If comparison fails, add mutation (better to have incorrect mutation than miss one)
                        filtered_mutations.append(mutation)
                
                # Skip field if all mutations filtered out
                if not filtered_mutations:
                    print(f"Skipping {filename} (all mutation values same as original)")
                    skipped_count += 1
                    continue
                
                # Print processing stage
                print(f"  Creating mutation files... (remaining {len(filtered_mutations)} valid mutations)")
                
                # Create file for each mutation
                field_mutations_created = 0
                for i, mutation in enumerate(filtered_mutations, 1):
                    try:
                        if create_mutation_file(field_id, mutation, original_data, output_dir, i):
                            mutations_count += 1
                            field_mutations_created += 1
                            print(f"  Created mutation: {filename} -> mutation {i}/{len(filtered_mutations)} ({mutation['description']})")
                    except Exception as e:
                        print(f"  Error creating mutation file: {e}")
                
                # Update statistics
                if asn1_type in type_stats:
                    type_stats[asn1_type]["processed"] += 1
                    type_stats[asn1_type]["mutations"] += field_mutations_created
                else:
                    type_stats["UNKNOWN"]["processed"] += 1
                    type_stats["UNKNOWN"]["mutations"] += field_mutations_created
                
                processed_count += 1
                
                # Cancel timeout
                signal.alarm(0)
                
            except TimeoutError as e:
                print(f"Warning: {e}")
                print(f"Skipping timeout file: {filename}")
                timeout_count += 1
                skipped_count += 1
                problem_files.append((filename, "Processing timeout"))
                # Copy problem file to diagnosis directory
                try:
                    shutil.copy2(file_path, os.path.join(diagnosis_dir, filename))
                except:
                    pass
                # Cancel timeout
                signal.alarm(0)
                continue
            except json.JSONDecodeError:
                print(f"Parse error: {filename}")
                skipped_count += 1
                problem_files.append((filename, "JSON parse error"))
                # Copy problem file to diagnosis directory
                try:
                    shutil.copy2(file_path, os.path.join(diagnosis_dir, filename))
                except:
                    pass
                # Cancel timeout
                signal.alarm(0)
            except ValueError:
                print(f"Invalid filename (cannot parse as field ID): {filename}")
                skipped_count += 1
                problem_files.append((filename, "Invalid filename"))
                # Cancel timeout
                signal.alarm(0)
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                skipped_count += 1
                problem_files.append((filename, f"Unknown error: {e}"))
                # Copy problem file to diagnosis directory
                try:
                    shutil.copy2(file_path, os.path.join(diagnosis_dir, filename))
                except:
                    pass
                # Cancel timeout
                signal.alarm(0)
            
            # Show progress every 10 files
            if file_index % 10 == 0:
                print(f"Progress: {file_index}/{total_files} ({file_index/total_files*100:.1f}%)")
    
    except Exception as e:
        print(f"Error reading directory: {e}")
    
    # Write problem files list to diagnosis directory
    try:
        with open(os.path.join(diagnosis_dir, "problem_files.txt"), 'w') as f:
            f.write(f"Total problem files: {len(problem_files)}\n\n")
            for filename, reason in problem_files:
                f.write(f"{filename}: {reason}\n")
    except Exception as e:
        print(f"Error writing problem files list: {e}")
    
    # Print type statistics
    print(f"\nStatistics by type:")
    print(f"{'Type':<15} {'Processed':<12} {'Mutations':<12}")
    print("-" * 40)
    for type_name, stats in sorted(type_stats.items()):
        if stats["processed"] > 0 or stats["mutations"] > 0:
            print(f"{type_name:<15} {stats['processed']:<12} {stats['mutations']:<12}")
    
    print(f"\nOverall statistics:")
    print(f"Processed successfully: {processed_count}")
    print(f"Mutations generated: {mutations_count}")
    print(f"Fields skipped: {skipped_count}")
    print(f"Same value skipped: {same_value_skipped}")
    print(f"Timeout files: {timeout_count}")
    print(f"Problem files: {len(problem_files)} (saved to {diagnosis_dir})")
    
    return processed_count, mutations_count, skipped_count, same_value_skipped

def main():
    """Main function"""
    # Set directories
    input_dir = "../asn-update/combine_fields"
    original_file_path = "../asn-update/02_flatten.json"
    output_dir = "../output/value_range_mutations"
    
    print(f"Starting automatic processing of field files in {input_dir}...")
    print(f"Supported field types: INTEGER/INT, ENUMERATED/ENUM, CHOICE, BOOL/BOOLEAN")
    print(f"For INTEGER ranges >100, quartile test points will be added")
    print(f"Original data file: {original_file_path}")
    print(f"Output directory: {output_dir}")
    
    processed, mutations, skipped, same_value_skipped = process_field_files(input_dir, original_file_path, output_dir)
    
    print("\nProcessing complete!")
    print(f"Fields processed: {processed}")
    print(f"Mutations generated: {mutations}")
    print(f"Fields skipped: {skipped}")
    print(f"Same value skipped: {same_value_skipped}")
    print(f"\nMutation files saved to: {os.path.abspath(output_dir)}")
    print(f"Problem files saved to: {os.path.abspath('../diagnosis')}")

if __name__ == "__main__":
    # Set random seed for reproducibility
    random.seed(42)
    main()