#!/usr/bin/env python
import json
import sys
from pycrate_asn1dir import RRCNR
from pycrate_asn1rt.utils import bitstr_to_bytes

def fix_bitstrings(obj):
    """
    如果 JSON 中有 "010101..." 形式的字符串，则用 bitstr_to_bytes 转成字节数据。
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and set(v) <= {"0", "1"}:
                try:
                    obj[k] = bitstr_to_bytes(v)
                except Exception as e:
                    print(f"[DEBUG] fix_bitstrings: 转换 {k} 时出错: {e}", flush=True)
            else:
                obj[k] = fix_bitstrings(v)
        return obj
    elif isinstance(obj, list):
        return [fix_bitstrings(x) for x in obj]
    else:
        return obj

def restore_tuples(obj):
    """
    将类似 ["setup", {...}] 的列表还原为 ("setup", {...}) 的元组。
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
    递归遍历对象：
    如果遇到列表，其长度为2且第二个元素是 int 并且小于 100（通常 BIT STRING 的 bit 长度不会超过 100），
    则认为这是 BIT STRING 的表示形式，将其转换为元组。
    同时对 dict、list 和 tuple 中的每个元素都进行处理。
    """
    if isinstance(obj, list):
        new_list = [recursive_convert_bitstring_lists(x) for x in obj]
        if len(new_list) == 2 and isinstance(new_list[1], int) and new_list[1] < 100:
            try:
                return (int(new_list[0]), int(new_list[1]))
            except Exception as e:
                print(f"[DEBUG] 转换失败 {new_list}: {e}", flush=True)
                return new_list
        else:
            return new_list
    elif isinstance(obj, dict):
        return {k: recursive_convert_bitstring_lists(v) for k, v in obj.items()}
    elif isinstance(obj, tuple):
        return tuple(recursive_convert_bitstring_lists(x) for x in obj)
    else:
        return obj

def reencode_from_json(json_file, field_name="DL_CCCH_Message"):
    # 1. 读取 JSON 数据
    with open(json_file, 'r') as f:
        asn1_dict = json.load(f)
    
    # 2. 先处理可能以 "010101..." 保存的 bit string 字符串
    asn1_dict = fix_bitstrings(asn1_dict)
    # 3. 将类似 ["setup", {...}] 的列表转换为元组
    asn1_dict = restore_tuples(asn1_dict)
    # 4. 递归将所有长度为2且符合 BIT STRING 特征的列表转换为元组
    asn1_dict = recursive_convert_bitstring_lists(asn1_dict)
    
    # 可选：你可以打印部分数据确认 frequencyDomainResources 已转换
    # print(json.dumps(asn1_dict, indent=2))
    
    # 5. 获取 ASN.1 结构定义
    try:
        sch = getattr(RRCNR.NR_RRC_Definitions, field_name)
    except AttributeError:
        print(f"[ERROR] ASN.1 结构中找不到 {field_name}", flush=True)
        sys.exit(1)
    
    # 6. 用转换后的字典恢复 ASN.1 对象
    try:
        sch.set_val(asn1_dict)
    except Exception as e:
        print(f"[ERROR] 恢复 ASN.1 对象时出错: {e}", flush=True)
        sys.exit(1)
    
    # 7. 重新编码为 UPER 格式
    try:
        encoded_bytes = sch.to_uper()
    except Exception as e:
        print(f"[ERROR] 编码 ASN.1 对象时出错: {e}", flush=True)
        sys.exit(1)
    
    return encoded_bytes

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python re-encode.py <json_file> [<field_name>]", flush=True)
        sys.exit(1)
    
    json_file = sys.argv[1]
    field_name = sys.argv[2] if len(sys.argv) > 2 else "DL_CCCH_Message"
    
    encoded = reencode_from_json(json_file, field_name)
    
    # 输出到控制台
    print("重新编码后的 ASN.1 十六进制字符串:", flush=True)
    print(encoded.hex(), flush=True)
    
    # 保存到文件
    output_file = "04_re-encode.hex"
    try:
        with open(output_file, 'w') as f:
            f.write(encoded.hex())
        print(f"[INFO] 已将编码结果保存到 {output_file}", flush=True)
    except Exception as e:
        print(f"[ERROR] 保存结果到文件时出错: {e}", flush=True)