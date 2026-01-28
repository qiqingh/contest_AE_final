import os
import json

def hex_to_bit_string(hex_str):
    """Convert each hex character to its 4-bit binary representation."""
    return ''.join(format(int(char, 16), '04b') for char in hex_str)

def bit_string_to_hex(bit_str):
    """Convert bit string to hex string."""
    hex_str = ''.join(format(int(bit_str[i:i+4], 2), 'x') for i in range(0, len(bit_str), 4))
    return hex_str

def find_bit_substring_indices(frame_bit_str, part_bit_str):
    """Find all start indices of the part_bit_str in the frame_bit_str."""
    start_indices = []
    index = frame_bit_str.find(part_bit_str)
    while index != -1:
        start_indices.append(index)
        index = frame_bit_str.find(part_bit_str, index + 1)
    return start_indices

def replace_bitstream_segment_in_place(original_bitstream, positions, target_bitstream, replace_bitstream):
    """Replace each occurrence of target_bitstream at specified positions with replace_bitstream in place."""
    bit_list = list(original_bitstream)  # Convert to list for mutable operations
    target_length = len(target_bitstream)
    
    # Replace each occurrence
    for pos in positions:
        bit_list[pos:pos + target_length] = replace_bitstream

    return ''.join(bit_list)  # Convert back to string

def process_hex_replacement(file_name, original_hex, hex_stream1, hex_stream2, paths):
    """Process hex replacement for the given file."""
    # Remove trailing "00" if present in both hex streams
    if hex_stream1.endswith("00"):
        hex_stream1 = hex_stream1[:-2]
    if hex_stream2.endswith("00"):
        hex_stream2 = hex_stream2[:-2]
    
    # Convert all hex streams to bit streams
    original_bitstream = hex_to_bit_string(original_hex)
    target_bitstream = hex_to_bit_string(hex_stream1)
    replace_bitstream = hex_to_bit_string(hex_stream2)

    # Locate the starting positions of the target bitstream within the original bitstream
    positions = find_bit_substring_indices(original_bitstream, target_bitstream)
    if not positions:
        print(f"Target hex stream not found in original bitstream for file {file_name}.")
        return

    # Check if the replacement bitstream length matches the target bitstream length
    if len(replace_bitstream) != len(target_bitstream):
        print(f"Replacement bitstream length ({len(replace_bitstream)}) does not match target bitstream length ({len(target_bitstream)}). Adjusting replacement length.")
        replace_bitstream = replace_bitstream[:len(target_bitstream)]  # Trim or adjust the length to match

    # Replace in-place all occurrences of the target bitstream with the replacement bitstream
    modified_bitstream = replace_bitstream_segment_in_place(original_bitstream, positions, target_bitstream, replace_bitstream)

    # Convert the modified bitstream back to hex format
    modified_hex = bit_string_to_hex(modified_bitstream)

    # Compare the original and modified hex streams to find the changes
    modifications = []
    min_length = min(len(original_hex), len(modified_hex))  # Ensure we don't go out of bounds
    for i in range(0, min_length, 2):  # Step by 2 since we're comparing hex bytes
        original_byte = original_hex[i:i+2]
        modified_byte = modified_hex[i:i+2].zfill(2)  # Ensure the modified byte is always 2 digits
        
        # Ensure the modified byte is not empty and compare correctly
        if original_byte != modified_byte:
            byte_offset = i // 2
            modifications.append((byte_offset, modified_byte))

    # Print the modifications
    print(f"Modifications for {file_name}:")
    for mod in modifications:
        print(f"Offset: {mod[0]}, New Value: {mod[1]}")

    # Save the original and modified bitstreams to a diagnostic file for further analysis
    with open(paths['diagnosis_file'], 'a') as diag_file:
        diag_file.write(f"File: {file_name}\n")
        diag_file.write(f"Target Hex Stream: {hex_stream1}\n")
        diag_file.write(f"Replacement Hex Stream: {hex_stream2}\n")
        diag_file.write(f"Original Bit Stream:\n{original_bitstream}\n")
        diag_file.write(f"Modified Bit Stream:\n{modified_bitstream}\n\n")

    # Save the changes between original and modified hex streams to an output file
    output_file_path = os.path.join(paths['output'], file_name)
    with open(output_file_path, 'w') as output_file:
        for offset, modified_value in modifications:
            output_file.write(f"Offset: {offset}, New Value: {modified_value}\n")

# Removed detailed_structure loading function as it's no longer needed

def process_file(file_name, original_hex, hex_stream1, hex_stream2, paths):
    """Process a single file with the given hex streams for replacement."""
    # Process hex replacement directly using the provided hex streams
    process_hex_replacement(file_name, original_hex, hex_stream1, hex_stream2, paths)

def main():
    # Example hex streams (replace these with your actual inputs)
    hex_stream1 = "28400414a2e00580088bd76380830f8003e0102341e040002096cc0ca8040ffff8000000080001b8a210000400b28000241000022049ccb3865994105fffe000000020001b8c410000040414850361cb2a0105fffe0000000200006e59040001002ca0000904000098126d31adb194107fe00000000020001b8e610000040414850361cb2a0107fe000000000200006e61840001002ca00009040000a8126db0c5a994109e000000000060001b9081000004041486a431632a0109e0000000000600006e6a040001002ca00009040000b81264ac6aa49a8000200404000800d010013b649180ee03ab3c4d5e0000014d080100012c061060160e0c10e0018940e0000108f7a0080008000032000a00132670cb339c5a98b6f169a3d327098144235524d40001002020004006808009db248c07701d59e26af000000a684008000960308300b0706087000c4a07040187bd0041004000019023020280034635b6339c5a98b6f169a3d327098144235524d40001002020004006808009db248c07701d59e26af000000a684008000960308300b0706087000c4a07080287bd004200400000c023020280036618b5339c5a98b6f169a3d327098144235524d40001002020004006808009db248c07701d59e26af000000a684008000960308300b0706087000c4a070c0387bd004300400000502302028001ca82803115554009c00c13aa002a210028000380982754001c420050500702304ea800008400a1400100000000200080400109c1740054a0070dd00072829c5740000a140800001010404000000102a40300a000c17000c2c40501200541900542e40701a009c1b009c29681022c80708238c7e068800b024040415305a0810c201c408e31f81a20030110102054c1683063480718238c7e068800d064040c153000"  # This will be found and replaced

    hex_stream2 = "28400414a2e00580088bd76380830f8003e0102341e040002096cc0ca8040ffff8000000080001b8a210000400b28000241000022049ccb3865994105fffe000000020001b8c410000040414884422132a0105fffe0000000200006e59040001002ca0000904000098126d31adb194107fe00000000020001b8e610000040414850361cb2a0107fe000000000200006e61840001002ca00009040000a8126db0c5a994109e000000000060001b9081000004041486a431632a0109e0000000000600006e6a040001002ca00009040000b81264ac6aa49a8000200404000800d010013b649180ee03ab3c4d5e0000014d080100012c061060160e0c10e0018940e0000108f7a0080008000032000a00132670cb339c5a98b6f169a3d327098144235524d40001002020004006808009db248c07701d59e26af000000a684008000960308300b0706087000c4a07040187bd0041004000019023020280034635b6339c5a98b6f169a3d327098144235524d40001002020004006808009db248c07701d59e26af000000a684008000960308300b0706087000c4a07080287bd004200400000c023020280036618b5339c5a98b6f169a3d327098144235524d40001002020004006808009db248c07701d59e26af000000a684008000960308300b0706087000c4a070c0387bd004300400000502302028001ca82803115554009c00c13aa002a210028000380982754001c420050500702304ea800008400a1400100000000200080400109c1740054a0070dd00072829c5740000a140800001010404000000102a40300a000c17000c2c40501200541900542e40701a009c1b009c29681022c80708238c7e068800b024040415305a0810c201c408e31f81a20030110102054c1683063480718238c7e068800d064040c153000"  # This will replace hex_stream1

    original_hex = "00000000000000000000000008004500030e2d734000401100007f0000017f000001e7a6270f02fafe9a6d61632d6e72020103020090070119000a013e12a8c78e972640029928400414a2e00580088bd76380830f8003e0102341e040002096cc0ca8040ffff8000000080001b8a210000400b28000241000022049ccb3865994105fffe000000020001b8c410000040414850361cb2a0105fffe0000000200006e59040001002ca0000904000098126d31adb194107fe00000000020001b8e610000040414850361cb2a0107fe000000000200006e61840001002ca00009040000a8126db0c5a994109e000000000060001b9081000004041486a431632a0109e0000000000600006e6a040001002ca00009040000b81264ac6aa49a8000200404000800d010013b649180ee03ab3c4d5e0000014d080100012c061060160e0c10e0018940e0000108f7a0080008000032000a00132670cb339c5a98b6f169a3d327098144235524d40001002020004006808009db248c07701d59e26af000000a684008000960308300b0706087000c4a07040187bd0041004000019023020280034635b6339c5a98b6f169a3d327098144235524d40001002020004006808009db248c07701d59e26af000000a684008000960308300b0706087000c4a07080287bd004200400000c023020280036618b5339c5a98b6f169a3d327098144235524d40001002020004006808009db248c07701d59e26af000000a684008000960308300b0706087000c4a070c0387bd004300400000502302028001ca82803115554009c00c13aa002a210028000380982754001c420050500702304ea800008400a1400100000000200080400109c1740054a0070dd00072829c5740000a140800001010404000000102a40300a000c17000c2c40501200541900542e40701a009c1b009c29681022c80708238c7e068800b024040415305a0810c201c408e31f81a20030110102054c1683063480718238c7e068800d064040c1530003f000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    
    # Define common paths
    paths = {
        'diagnosis_file': './diagnosis/offset_calculation_diagnosis.txt',
        'output': './',
    }

    # Ensure output and diagnosis directories exist
    if not os.path.exists(paths['output']):
        os.makedirs(paths['output'])
        
    # Create diagnosis directory if it doesn't exist
    diagnosis_dir = os.path.dirname(paths['diagnosis_file'])
    if not os.path.exists(diagnosis_dir):
        os.makedirs(diagnosis_dir)

    # Process the replacement with a default filename
    file_name = "05_cal_offset.txt"
    process_file(file_name, original_hex, hex_stream1, hex_stream2, paths)

if __name__ == "__main__":
    main()