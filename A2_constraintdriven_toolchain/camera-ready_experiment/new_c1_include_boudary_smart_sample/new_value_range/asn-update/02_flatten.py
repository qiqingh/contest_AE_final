import json
import os
import argparse
import copy
import re

def flatten_asn1_obj(asn1_obj, current_path="", parent_type=None, parent_index=None, original_obj=None, counter=None):
    """
    递归遍历 ASN.1 解码后的对象，生成扁平化列表以及包含所有节点结构信息的元数据字典。

    对于每个叶子节点（非容器类型），生成一个记录，包含：
      - field_path：该节点在原始结构中的完整路径（用于反向重构）
      - field_name：节点名称（若为字典中的键，则为键名；若为列表/元组，则为索引表示）
      - field_type：Python 基本类型名称（如 int, str, float 等）
      - current_value：当前值
      - suggested_value：默认初始化为当前值，后续用户可以修改
      - parent_type：所属容器的类型（"dict", "list", "tuple"）
      - parent_index：若所属容器为列表或元组，此处记录其索引；对于字典则为 None
      - field_id：每个 field 的唯一标识

    同时对容器节点（dict、list、tuple）在 metadata 中记录容器的结构信息，
    例如对于字典，会记录 ASN.1 的 type、tag、class、hex 以及所有键列表；对于列表或元组，会记录长度等信息。
    """
    flattened_records = []
    metadata = {}

    # 初始化计数器
    if counter is None:
        counter = [0]

    # 如果 original_obj 为空，则设置为当前对象（根节点）
    if original_obj is None:
        original_obj = asn1_obj

    # 针对字典类型
    if isinstance(asn1_obj, dict):
        # 收集 ASN.1 特定元数据（如果有）; 默认若不存在则标记为 UNKNOWN
        asn1_type = asn1_obj.get("type", "UNKNOWN")
        asn1_tag = asn1_obj.get("tag", None)
        asn1_class = asn1_obj.get("class", None)
        asn1_hex = asn1_obj.get("hex", None)
        
        metadata[current_path] = {
            "asn1_type": asn1_type,
            "asn1_tag": asn1_tag,
            "asn1_class": asn1_class,
            "asn1_hex": asn1_hex,
            "structure_type": "dict",
            "keys": list(asn1_obj.keys())
        }
        
        # 遍历字典中的每个键值对，记录路径信息（parent_type 为 "dict"，同时记录 parent_key）
        for key, value in asn1_obj.items():
            path = f"{current_path}.{key}" if current_path else key
            # 这里 parent_index 对于字典不适用，故保留为 None
            flattened, meta = flatten_asn1_obj(value, path, parent_type="dict", parent_index=None, original_obj=original_obj, counter=counter)
            flattened_records.extend(flattened)
            metadata.update(meta)
            
    # 针对列表类型
    elif isinstance(asn1_obj, list):
        metadata[current_path] = {
            "structure_type": "list",
            "length": len(asn1_obj)
        }
        
        for index, item in enumerate(asn1_obj):
            path = f"{current_path}[{index}]"
            flattened, meta = flatten_asn1_obj(item, path, parent_type="list", parent_index=index, original_obj=original_obj, counter=counter)
            flattened_records.extend(flattened)
            metadata.update(meta)
            
    # 针对元组类型
    elif isinstance(asn1_obj, tuple):
        metadata[current_path] = {
            "structure_type": "tuple",
            "length": len(asn1_obj)
        }
        
        for index, item in enumerate(asn1_obj):
            path = f"{current_path}[tuple_{index}]" if current_path else f"tuple[{index}]"
            flattened, meta = flatten_asn1_obj(item, path, parent_type="tuple", parent_index=index, original_obj=original_obj, counter=counter)
            flattened_records.extend(flattened)
            metadata.update(meta)
            
    # 针对基本数据类型（叶子节点）
    else:
        # 构造叶子节点记录，并增加 field_id
        record = {
            "field_id": counter[0],
            "field_path": current_path,
            "field_name": current_path.split(".")[-1] if current_path and "." in current_path else current_path,
            "field_type": type(asn1_obj).__name__,
            "current_value": asn1_obj,
            "suggested_value": asn1_obj,  # 初始化为当前值，可供后续修改
            "parent_type": parent_type,
            "parent_index": parent_index
        }
        counter[0] += 1
        flattened_records.append(record)
        
        metadata[current_path] = {
            "python_type": type(asn1_obj).__name__,
            "original_value": asn1_obj
        }
    
    return flattened_records, metadata

def main():
    parser = argparse.ArgumentParser(description='将 ASN.1 解码后的标准 JSON 转换为扁平化格式，附带反向还原所需的元数据')
    parser.add_argument('-i', '--input', required=True, help='输入的标准 JSON 文件路径（如 decode.json）')
    parser.add_argument('-o', '--output', help='输出的扁平化 JSON 文件路径（如 flattened.json）')
    parser.add_argument('-m', '--metadata', help='输出的元数据 JSON 文件路径（如 metadata.json）')
    
    args = parser.parse_args()
    input_base = os.path.splitext(args.input)[0]
    input_base="02"
    # 如果没有提供输出路径，则基于输入路径生成输出文件名
    if not args.output:
        args.output = f"{input_base}_flattened.json"
    
    # 如果没有提供元数据路径，则基于输入路径生成元数据文件名
    if not args.metadata:
        args.metadata = f"{input_base}_metadata.json"
    
    # 读取输入 JSON 文件
    try:
        with open(args.input, 'r') as f:
            std_json = json.load(f)
    except Exception as e:
        print(f"读取输入文件时出错: {e}")
        return
    
    # 对输入的 ASN.1 JSON 进行扁平化处理，并获取完整的元数据
    flattened_json, metadata = flatten_asn1_obj(std_json)
    
    # 保存扁平化 JSON（包含每个叶子节点的详细路径和值）
    try:
        with open(args.output, 'w') as f:
            json.dump(flattened_json, f, indent=2)
        print(f"扁平化 JSON 已保存到: {args.output}")
    except Exception as e:
        print(f"保存输出文件时出错: {e}")
        return
    
    # 保存元数据 JSON（记录各容器的结构信息和 ASN.1 相关元数据）
    try:
        with open(args.metadata, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"元数据 JSON 已保存到: {args.metadata}")
    except Exception as e:
        print(f"保存元数据文件时出错: {e}")
        return

if __name__ == "__main__":
    main()