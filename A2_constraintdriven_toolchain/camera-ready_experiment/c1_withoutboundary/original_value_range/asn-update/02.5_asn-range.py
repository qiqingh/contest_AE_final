from pycrate_asn1dir.RRCNR import NR_RRC_Definitions
from pycrate_asn1rt.asnobj_construct import CHOICE,SEQ,SET,SEQ_OF,SET_OF
from pycrate_asn1rt.asnobj_basic import INT,BOOL,ENUM,REAL,OID,REL_OID,NULL
from pycrate_asn1rt.asnobj_str import OCT_STR, BIT_STR
import json
import os
import argparse
import re

def resolve_path_with_names(obj,path):
    parts = []
    for part in path.split("."):
        matches = re.findall(r'([a-zA-Z0-9_-]+)|\[(\d+)\]', part)
        for name, idx in matches:
            if name:
                parts.append(name)
            if idx:
                parts.append(int(idx))
    #print(parts)
    current = obj
    resolved_path = []
    for i, key in enumerate(parts):
        if isinstance(key, int):
            if isinstance(current[key], list) or isinstance(current[key], dict) or isinstance(current, list):
                if key>0 and isinstance(current[key-1], str):
                    field_name = current[key - 1]  # 取前一个字段名
                else:
                    field_name = str(key)
                resolved_path.append(field_name)
                current = current[key]
            else:
                resolved_path.append(str(current[key]))
                current = current[key]
        else:
            resolved_path.append(key)
            current = current[key]
    #print(resolved_path)
    return '.'.join(resolved_path)

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

def get_range(leaf):
    if isinstance(leaf, CHOICE):
        #print("CHOICE found")
        _tags = getattr(leaf, '_cont_tags', None)
        if _tags is None:
            raise AttributeError("_cont_tags not found")
        lst = list(_tags.values())
        #print(lst)
        return lst, type(leaf)

    if isinstance(leaf, INT):
        # print("INT found")
        _const_val = getattr(leaf, '_const_val', None)
        if _const_val is None:
            raise AttributeError("_const_val not found")
        root_val = getattr(_const_val, 'root', None)
        if root_val is None or not isinstance(root_val, list) or len(root_val) == 0:
            raise ValueError("Invalid or missing root value")
        lb = getattr(root_val[0], 'lb', None)
        ub = getattr(root_val[0], 'ub', None)
        return (lb, ub), type(leaf)

    if isinstance(leaf,OCT_STR):
        #print("OCT_STR found")
        #_const_cont = getattr(leaf, '_const_cont', None)
        return (None, None), type(leaf)

    if isinstance(leaf, BIT_STR):
        #print("BIT_STR found")
        _const_sz = getattr(leaf, '_const_sz', None)
        if _const_sz is None:
            raise AttributeError("_const_sz not found")
        lb = getattr(_const_sz, 'lb', None)
        ub = getattr(_const_sz, 'ub', None)
        return (lb, ub), type(leaf)

    if isinstance(leaf, ENUM):
        #print("ENUM found")
        _tags = getattr(leaf, '_cont_rev', None)
        if _tags is None:
            raise AttributeError("_cont_rev not found")
        lst = list(_tags.values())
        # print(lst)
        return lst, type(leaf)

    if isinstance(leaf, BOOL):
        #print("BOOL found")
        return (True, False), type(leaf)

    if isinstance(leaf, NULL):
        #print("NULL found")
        return (NULL), type(leaf)
    # if isinstance(leaf, SEQ):
    #     print("SEQ found")
    #     return (None, None), type(leaf)
    else:
        raise TypeError(f"Unsupported type: {type(leaf)}")



def get_field_range(sch,path):
    parts = []
    for part in path.split("."):
        parts.append(part)
    try:
        current = sch
        for i, key in enumerate(parts):
            #print(type(current))
            if is_number(key):
                key = int(key)
                if isinstance(current, (SEQ_OF)):
                    _cont = getattr(current, '_cont', None)
                    current = _cont
                    continue
                if isinstance(current, (BIT_STR,CHOICE,OCT_STR)):
                    continue
                current = current._cont[key]
            else:
                _cont = getattr(current, '_cont', None)
                if _cont is None:
                    _cont = getattr(current, '_const_cont', None)
                    current = _cont
                    continue
                current = _cont[key]
        #print(f"Current type: {type(current)}", f"Key: {key}, Value: {current}")
        range,value_type=get_range(current)
        return range, value_type


    except Exception as e:
        print(type(current))
        print(f"Error accessing path '{path}': {e}")
        raise

def make_json_serializable(obj):
    """递归地将对象转换为 JSON 可序列化格式"""
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    elif isinstance(obj, (list, tuple, set)):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, dict):
        return {
            str(make_json_serializable(key)): make_json_serializable(value)
            for key, value in obj.items()
        }
    elif hasattr(obj, '__name__'):  # 处理类型对象如 BOOL, int 等
        return obj.__name__
    else:
        return str(obj)
# sch = NR_RRC_Definitions.DL_CCCH_Message
# #ddd = NR_RRC_Definitions.UL_CCCH_Message
# hex_stream = "28400404bae00580088bd76380830f8003e0102341e0400020904c0ca8040ffff8000000080001b8a210000400b28000241000022049a06aa49a8000200404000800d010013b64b180ee0391a2b3c48000014d080100012c0e104164e0c10e001c4a0700000817bd00400040000190005000ca82803115054001c00400468800a88400a00000000000000000008a1004008001000028010100054c00"
# asn1_bytes = bytes.fromhex(hex_stream)
# sch.from_uper(asn1_bytes)
# asn1_obj = sch.get_val()
# #asn1_obj 主要用于还原path中的索引名称
#
# path="message[1][1].criticalExtensions[1].masterCellGroup[1].rlc-BearerToAddModList[0].logicalChannelIdentity"
# range_result = get_field_range(sch,asn1_obj, path)
# print(range_result)

# 最方便的外部调用方式
# with open("decoded.json", 'r') as f:
#     asn1_obj = json.load(f)
# sch = NR_RRC_Definitions.DL_CCCH_Message
# range_result = get_field_range(sch,asn1_obj, path)
def main():
    parser = argparse.ArgumentParser(description='定位 ASN.1 解码后的范围')
    parser.add_argument('-i', '--input', help='输入的标准 JSON 文件路径（如 decode.json）',default="01_decoded.json")
    parser.add_argument('-f', '--flattened', help='扁平化 JSON 文件路径（例如 flattened.json）',default="02_flattened.json")
    parser.add_argument('-o', '--output', help='输出的文件夹路径',default="combine_fields" )
    parser.add_argument('-m', '--message', help='待解析的消息类型（如 DL_CCCH_Message）',default="DL_CCCH_Message")

    args = parser.parse_args()

    # 读取输入 JSON 文件
    try:
        with open(args.input, 'r') as f:
            decode_json = json.load(f)
        with open(args.flattened, 'r') as f:
            flattened_json = json.load(f)
    except Exception as e:
        print(f"读取输入扁平化时出错: {e}")
        return "stop"


    sch = NR_RRC_Definitions.DL_CCCH_Message
    for field in flattened_json:
        field_path= field['field_path']
        #field_path = "message[0]"
        #field_path = "message[1][1].rrc-TransactionIdentifier"
        #field_path = "message[1][1].criticalExtensions[0]"
        #field_path="message[1][1].criticalExtensions[1].masterCellGroup[1].spCellConfig.spCellConfigDedicated.initialDownlinkBWP.pdcch-Config[1].controlResourceSetToAddModList[0].frequencyDomainResources[1]"
        #field_path = "message[1][1].criticalExtensions[1].masterCellGroup[1].rlc-BearerToAddModList[0].mac-LogicalChannelConfig.ul-SpecificParameters.logicalChannelSR-Mask"
        #print(f"Processing field: {field_path}")
        path = resolve_path_with_names(decode_json, field_path)
        #print(f"Processing path: {path}")
        range_result,value_type = get_field_range(sch,path)
        print(f"id{field['field_id']}，{field['field_name']}, Range: {range_result}")
        if range_result=="stop":
            break
        #break
        ranges = [None]
        available_options = [None]

        if value_type is INT:
            ranges=range_result
        elif value_type in (ENUM,CHOICE):
            available_options=range_result

        new_field = {
        "field_name": field["field_name"],
        "field_path": field["field_path"],
        "asn1_rules": {
            "rules": [
                {
                    "field_name": field["field_name"],
                    "type": value_type,
                    "range": ranges,
                    "available_options": available_options,
                    "additional_constraints": "XXX"
                }
                    ]
                    },
        "importance_score": 0,
        "category": "XXX",
        "reason": (
            f"The '{field['field_name']}' field is XXX"
            )
        }
        field_path = os.path.join(args.output,str(field['field_id'])+".json")
        try:
            with open(field_path, 'w') as f:
                json.dump(make_json_serializable(new_field), f, indent=2)
        except Exception as e:
            print(f"保存输出文件时出错: {e}")
            return



if __name__ == "__main__":
    main()