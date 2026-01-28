import json
import os
import argparse
import re

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
    for record in flattened_records:
        val = record.get("suggested_value", record.get("current_value"))
        field_path = record.get("field_path")
        if field_path:
            try:
                skeleton = set_nested_value(skeleton, field_path, val)
            except Exception as e:
                print(f"设置路径 {field_path} 时出错: {e}")
    return skeleton

def main():
    parser = argparse.ArgumentParser(
        description='使用扁平化文件和元数据重构原始嵌套 JSON 对象'
    )
    parser.add_argument('-f', '--flattened', required=True, help='扁平化 JSON 文件路径（例如 decoded_flattened.json）')
    parser.add_argument('-m', '--metadata', required=True, help='元数据 JSON 文件路径（例如 decoded_metadata.json）')
    parser.add_argument('-o', '--output', help='输出重构后的 JSON 文件路径')
    args = parser.parse_args()
    
    if not args.output:
        base = os.path.splitext(args.flattened)[0]
        base="03"
        args.output = f"{base}_re-constructed.json"
    
    try:
        with open(args.flattened, 'r') as f:
            flattened_records = json.load(f)
    except Exception as e:
        print(f"读取扁平化文件错误: {e}")
        return
    
    try:
        with open(args.metadata, 'r') as f:
            metadata = json.load(f)
    except Exception as e:
        print(f"读取元数据文件错误: {e}")
        return
    
    # 根据元数据重构结构骨架
    skeleton = reconstruct_from_metadata(metadata, "")
    if skeleton is None:
        skeleton = {}  # 若根元数据为空，则默认使用 dict
    # 将扁平化记录覆盖到骨架上
    reconstructed_obj = overlay_flattened(skeleton, flattened_records)
    
    try:
        with open(args.output, 'w') as f:
            json.dump(reconstructed_obj, f, indent=2, ensure_ascii=False)
        print(f"重构后的 JSON 已保存到: {args.output}")
    except Exception as e:
        print(f"保存输出文件错误: {e}")

if __name__ == "__main__":
    main()
