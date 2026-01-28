import os
import json
from datetime import datetime

# 输入和输出目录
INPUT_DIR = "../output/reencode"
OUTPUT_DIR = "../output/calOffset"
DIAGNOSIS_FILE = "../diagnosis/offset_calculation_diagnosis.txt"

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
        log_msg = f"Target hex stream not found in original bitstream for file {file_name}."
        print(log_msg)
        with open(paths['diagnosis_file'], 'a') as diag_file:
            diag_file.write(f"{log_msg}\n")
        return False

    # Check if the replacement bitstream length matches the target bitstream length
    if len(replace_bitstream) != len(target_bitstream):
        log_msg = f"Replacement bitstream length ({len(replace_bitstream)}) does not match target bitstream length ({len(target_bitstream)}). Adjusting replacement length."
        print(log_msg)
        with open(paths['diagnosis_file'], 'a') as diag_file:
            diag_file.write(f"{log_msg}\n")
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
        diag_file.write(f"Original Bit Stream length: {len(original_bitstream)}\n")
        diag_file.write(f"Modified Bit Stream length: {len(modified_bitstream)}\n")
        diag_file.write(f"Number of modifications: {len(modifications)}\n\n")

    # Save the changes between original and modified hex streams to an output file
    output_file_path = os.path.join(paths['output'], f"{os.path.splitext(file_name)[0]}_offset.txt")
    with open(output_file_path, 'w') as output_file:
        for offset, modified_value in modifications:
            output_file.write(f"Offset: {offset}, New Value: {modified_value}\n")
    
    return True

def read_hex_from_file(file_path):
    """从文件中读取十六进制字符串"""
    try:
        with open(file_path, 'r') as f:
            return f.read().strip()
    except Exception as e:
        print(f"读取文件 {file_path} 时出错: {e}")
        return None

def process_file(input_file_path, original_hex, hex_stream1, paths):
    """处理单个文件"""
    file_name = os.path.basename(input_file_path)
    
    # 从文件中读取 hex_stream2
    hex_stream2 = read_hex_from_file(input_file_path)
    if not hex_stream2:
        return False
    
    # 处理 hex 替换
    return process_hex_replacement(file_name, original_hex, hex_stream1, hex_stream2, paths)

def main():
    # 硬编码的 hex 流
    hex_stream1 = "28400414a2e00580088bd76380830f8003e0102341e040002096cc0ca8040ffff8000000080001b8a210000400b28000241000022049ccb3865994105fffe000000020001b8c410000040414850361cb2a0105fffe0000000200006e59040001002ca0000904000098126d31adb194107fe00000000020001b8e610000040414850361cb2a0107fe000000000200006e61840001002ca00009040000a8126db0c5a994109e000000000060001b9081000004041486a431632a0109e0000000000600006e6a040001002ca00009040000b81264ac6aa49a8000200404000800d010013b649180ee03ab3c4d5e0000014d080100012c061060160e0c10e0018940e0000108f7a0080008000032000a00132670cb339c5a98b6f169a3d327098144235524d40001002020004006808009db248c07701d59e26af000000a684008000960308300b0706087000c4a07040187bd0041004000019023020280034635b6339c5a98b6f169a3d327098144235524d40001002020004006808009db248c07701d59e26af000000a684008000960308300b0706087000c4a07080287bd004200400000c023020280036618b5339c5a98b6f169a3d327098144235524d40001002020004006808009db248c07701d59e26af000000a684008000960308300b0706087000c4a070c0387bd004300400000502302028001ca82803115554009c00c13aa002a210028000380982754001c420050500702304ea800008400a1400100000000200080400109c1740054a0070dd00072829c5740000a140800001010404000000102a40300a000c17000c2c40501200541900542e40701a009c1b009c29681022c80708238c7e068800b024040415305a0810c201c408e31f81a20030110102054c1683063480718238c7e068800d064040c153000"
    
    original_hex = "00000000000000000000000008004500030e2d734000401100007f0000017f000001e7a6270f02fafe9a6d61632d6e72020103020090070119000a013e12a8c78e972640029928400414a2e00580088bd76380830f8003e0102341e040002096cc0ca8040ffff8000000080001b8a210000400b28000241000022049ccb3865994105fffe000000020001b8c410000040414850361cb2a0105fffe0000000200006e59040001002ca0000904000098126d31adb194107fe00000000020001b8e610000040414850361cb2a0107fe000000000200006e61840001002ca00009040000a8126db0c5a994109e000000000060001b9081000004041486a431632a0109e0000000000600006e6a040001002ca00009040000b81264ac6aa49a8000200404000800d010013b649180ee03ab3c4d5e0000014d080100012c061060160e0c10e0018940e0000108f7a0080008000032000a00132670cb339c5a98b6f169a3d327098144235524d40001002020004006808009db248c07701d59e26af000000a684008000960308300b0706087000c4a07040187bd0041004000019023020280034635b6339c5a98b6f169a3d327098144235524d40001002020004006808009db248c07701d59e26af000000a684008000960308300b0706087000c4a07080287bd004200400000c023020280036618b5339c5a98b6f169a3d327098144235524d40001002020004006808009db248c07701d59e26af000000a684008000960308300b0706087000c4a070c0387bd004300400000502302028001ca82803115554009c00c13aa002a210028000380982754001c420050500702304ea800008400a1400100000000200080400109c1740054a0070dd00072829c5740000a140800001010404000000102a40300a000c17000c2c40501200541900542e40701a009c1b009c29681022c80708238c7e068800b024040415305a0810c201c408e31f81a20030110102054c1683063480718238c7e068800d064040c1530003f000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    
    # 定义路径
    paths = {
        'diagnosis_file': DIAGNOSIS_FILE,
        'output': OUTPUT_DIR,
    }

    # 确保输出和诊断目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DIAGNOSIS_FILE), exist_ok=True)

    # 初始化诊断文件
    with open(DIAGNOSIS_FILE, 'w') as diag_file:
        diag_file.write(f"[{datetime.now()}] 开始批量处理 Hex 替换偏移量计算\n")
        diag_file.write(f"输入目录: {INPUT_DIR}\n")
        diag_file.write(f"输出目录: {OUTPUT_DIR}\n\n")
    
    # 获取所有hex文件
    hex_files = [os.path.join(INPUT_DIR, f) for f in os.listdir(INPUT_DIR) 
                if (f.endswith('.hex') or f.endswith('.txt')) and os.path.isfile(os.path.join(INPUT_DIR, f))]
    
    # 处理统计
    total_files = len(hex_files)
    success_count = 0
    
    with open(DIAGNOSIS_FILE, 'a') as diag_file:
        diag_file.write(f"找到 {total_files} 个文件待处理\n\n")
    
    # 批量处理每个文件
    for input_file in hex_files:
        if process_file(input_file, original_hex, hex_stream1, paths):
            success_count += 1
    
    # 打印和记录总结
    summary = f"\n[{datetime.now()}] 处理完成\n"
    summary += f"成功处理: {success_count}/{total_files} 个文件\n"
    
    print(summary)
    with open(DIAGNOSIS_FILE, 'a') as diag_file:
        diag_file.write(summary)

if __name__ == "__main__":
    main()