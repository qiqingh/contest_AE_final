import json
import os
import re
import sys
from datetime import datetime

# 输入和输出目录
FLATTENED_DIR = "../output/value_range_mutations"
METADATA_FILE = "../asn-update/02_metadata.json"
OUTPUT_DIR = "../output/reconstruct"
DIAGNOSIS_FILE = "../diagnosis/reconstruct.txt"

def reconstruct_from_metadata(metadata, current_path=""):
    """
    根据 metadata 递归重构出原始嵌套结构的骨架。
    
    metadata 是一个 dict，键为各节点的完整路径，值为该节点的元数据信息。
    如果 metadata[current_path] 中有 "structure_type"，则说明该节点是容器，
    否则视为叶子节点，返回 None（后续将由扁平化记录填充）。
    """
    if current_path not in metadata:
        return None
    info = metadata[current_path]
    if "structure_type" not in info:
        # 叶子节点
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
    根据 field_path 将 value 插入到 nested 对象中。
    支持类似 "message[1][1].rrc-TransactionIdentifier" 的路径格式。
    
    本函数采用正则先把每个 token 中的 key 和索引提取出来，然后逐级在容器中设置值。
    """
    # 解析 field_path，提取形如 key 或 [index] 的段
    segments = re.findall(r'([^\[\]\.]+)|\[(\d+)\]', field_path)
    current = nested
    for i, (key, index) in enumerate(segments):
        is_last = (i == len(segments) - 1)
        if key:
            # 当前段为字典 key
            if not isinstance(current, dict):
                raise TypeError(f"预期 dict，但在处理段 '{key}' 时遇到 {type(current).__name__}")
            if is_last:
                current[key] = value
            else:
                if key not in current or current[key] is None:
                    # 预判下一个段，如果是数字则创建列表，否则创建 dict
                    next_seg = segments[i+1]
                    if next_seg[1] != "":
                        current[key] = []
                    else:
                        current[key] = {}
                current = current[key]
        elif index:
            idx = int(index)
            if not isinstance(current, list):
                raise TypeError(f"预期 list，但在处理索引 [{idx}] 时遇到 {type(current).__name__}")
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

def overlay_flattened(skeleton, flattened_records):
    """
    根据扁平化记录，将每个记录的 suggested_value（若修改过则使用，否则使用 current_value）
    覆盖到 skeleton 中对应的位置。
    """
    errors = []
    for record in flattened_records:
        val = record.get("suggested_value", record.get("current_value"))
        field_path = record.get("field_path")
        if field_path:
            try:
                skeleton = set_nested_value(skeleton, field_path, val)
            except Exception as e:
                error_msg = f"设置路径 {field_path} 时出错: {e}"
                errors.append(error_msg)
    return skeleton, errors

def process_file(flattened_file, metadata, log_file):
    """处理单个扁平化JSON文件"""
    file_name = os.path.basename(flattened_file)
    log_file.write(f"\n[{datetime.now()}] 处理文件: {file_name}\n")
    log_file.write(f"{'='*50}\n")
    
    try:
        with open(flattened_file, 'r') as f:
            flattened_records = json.load(f)
        log_file.write(f"成功读取扁平化文件，记录数: {len(flattened_records)}\n")
    except Exception as e:
        log_file.write(f"读取扁平化文件错误: {e}\n")
        return False
    
    # 根据元数据重构结构骨架
    skeleton = reconstruct_from_metadata(metadata, "")
    if skeleton is None:
        skeleton = {}  # 若根元数据为空，则默认使用 dict
        log_file.write("警告: 根元数据为空，使用空字典作为骨架\n")
    
    # 将扁平化记录覆盖到骨架上
    reconstructed_obj, errors = overlay_flattened(skeleton, flattened_records)
    
    # 记录错误信息
    if errors:
        log_file.write("覆盖过程中发生以下错误:\n")
        for error in errors:
            log_file.write(f"- {error}\n")
    
    # 生成输出文件名
    base_name = os.path.splitext(file_name)[0]
    output_file = os.path.join(OUTPUT_DIR, f"{base_name}_reconstructed.json")
    
    try:
        with open(output_file, 'w') as f:
            json.dump(reconstructed_obj, f, indent=2, ensure_ascii=False)
        log_file.write(f"重构后的 JSON 已保存到: {output_file}\n")
        return True
    except Exception as e:
        log_file.write(f"保存输出文件错误: {e}\n")
        return False

def main():
    # 创建输出目录和诊断目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DIAGNOSIS_FILE), exist_ok=True)
    
    # 打开诊断日志文件
    with open(DIAGNOSIS_FILE, 'w') as log_file:
        log_file.write(f"[{datetime.now()}] 开始批量重构处理\n")
        log_file.write(f"扁平化文件目录: {FLATTENED_DIR}\n")
        log_file.write(f"元数据文件: {METADATA_FILE}\n")
        log_file.write(f"输出目录: {OUTPUT_DIR}\n\n")
        
        # 加载元数据
        try:
            with open(METADATA_FILE, 'r') as f:
                metadata = json.load(f)
            log_file.write(f"成功加载元数据文件，包含 {len(metadata)} 个节点记录\n\n")
        except Exception as e:
            log_file.write(f"读取元数据文件错误: {e}\n")
            return
        
        # 获取所有JSON文件
        json_files = [os.path.join(FLATTENED_DIR, f) for f in os.listdir(FLATTENED_DIR) 
                     if f.endswith('.json') and os.path.isfile(os.path.join(FLATTENED_DIR, f))]
        
        log_file.write(f"找到 {len(json_files)} 个JSON文件待处理\n\n")
        
        # 处理每个文件
        success_count = 0
        for file_path in json_files:
            if process_file(file_path, metadata, log_file):
                success_count += 1
        
        # 打印总结
        log_file.write(f"\n[{datetime.now()}] 处理完成\n")
        log_file.write(f"成功处理: {success_count}/{len(json_files)} 个文件\n")

if __name__ == "__main__":
    main()