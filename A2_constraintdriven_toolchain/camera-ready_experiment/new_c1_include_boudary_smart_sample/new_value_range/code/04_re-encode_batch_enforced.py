#!/usr/bin/env python
import json
import sys
import os
from datetime import datetime
from pycrate_asn1dir import RRCNR
from pycrate_asn1rt.utils import bitstr_to_bytes

# 定义输入和输出目录
INPUT_DIR = "../output/03_reconstruct"
OUTPUT_DIR = "../output/04_reencode"
DIAGNOSIS_FILE = "../diagnosis/reencode_asn_check.txt"

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

def reencode_from_json(json_file, field_name="DL_CCCH_Message", log_file=None):
    """重新编码单个JSON文件"""
    file_name = os.path.basename(json_file)
    
    # 记录处理状态
    log_message = f"\n[{datetime.now()}] 处理文件: {file_name}\n{'='*50}\n"
    if log_file:
        log_file.write(log_message)
    print(log_message, flush=True)
    
    try:
        # 1. 读取 JSON 数据
        with open(json_file, 'r') as f:
            asn1_dict = json.load(f)
        
        # 2. 先处理可能以 "010101..." 保存的 bit string 字符串
        asn1_dict = fix_bitstrings(asn1_dict)
        # 3. 将类似 ["setup", {...}] 的列表转换为元组
        asn1_dict = restore_tuples(asn1_dict)
        # 4. 递归将所有长度为2且符合 BIT STRING 特征的列表转换为元组
        asn1_dict = recursive_convert_bitstring_lists(asn1_dict)
        
        # 5. 获取 ASN.1 结构定义
        try:
            sch = getattr(RRCNR.NR_RRC_Definitions, field_name)
        except AttributeError:
            error_msg = f"[ERROR] ASN.1 结构中找不到 {field_name}"
            if log_file:
                log_file.write(error_msg + "\n")
            print(error_msg, flush=True)
            return None
        
        # 6. 用转换后的字典恢复 ASN.1 对象
        try:
            # ===== 添加调试信息 - 在set_val之前 =====
            if log_file:
                debug_msg = f"[DEBUG] 字段类型: {type(sch)}\n"
                debug_msg += f"[DEBUG] _SAFE_VAL: {getattr(sch, '_SAFE_VAL', 'N/A')}\n"
                debug_msg += f"[DEBUG] _SAFE_BND: {getattr(sch, '_SAFE_BND', 'N/A')}\n"
                debug_msg += f"[DEBUG] _SAFE_BNDTAB: {getattr(sch, '_SAFE_BNDTAB', 'N/A')}\n"
                debug_msg += f"[DEBUG] _const_val: {getattr(sch, '_const_val', 'N/A')}\n"
                
                # 如果有约束，检查扩展性
                if hasattr(sch, '_const_val') and sch._const_val:
                    debug_msg += f"[DEBUG] 约束扩展性 _const_val.ext: {getattr(sch._const_val, 'ext', 'N/A')}\n"
                    debug_msg += f"[DEBUG] 约束内容: {sch._const_val}\n"
                else:
                    debug_msg += f"[DEBUG] 没有找到约束定义\n"
                
                debug_msg += f"[DEBUG] 输入数据类型: {type(asn1_dict)}\n"
                debug_msg += f"[DEBUG] 输入数据内容: {str(asn1_dict)[:200]}...\n"
                log_file.write(debug_msg)
            # ===== 调试信息结束 =====
            
            sch.set_val(asn1_dict)
            
            # ===== 可选：在set_val之后再检查一次 =====
            if log_file and hasattr(sch, '_val'):
                post_debug = f"[DEBUG] set_val后的值: {str(sch._val)[:200]}...\n"
                post_debug += f"[DEBUG] set_val执行成功\n"
                log_file.write(post_debug)
            # ===== 调试信息结束 =====
            
        except Exception as e:
            error_msg = f"[ERROR] 恢复 ASN.1 对象时出错: {e}"
            if log_file:
                log_file.write(error_msg + "\n")
            print(error_msg, flush=True)
            return None
        
        # 7. 重新编码为 UPER 格式
        try:
            encoded_bytes = sch.to_uper()
            success_msg = f"[SUCCESS] 文件 {file_name} 成功重编码"
            if log_file:
                log_file.write(success_msg + "\n")
            print(success_msg, flush=True)
            return encoded_bytes
        except Exception as e:
            error_msg = f"[ERROR] 编码 ASN.1 对象时出错: {e}"
            if log_file:
                log_file.write(error_msg + "\n")
            print(error_msg, flush=True)
            return None
            
    except Exception as e:
        error_msg = f"[ERROR] 处理文件 {file_name} 时出错: {e}"
        if log_file:
            log_file.write(error_msg + "\n")
        print(error_msg, flush=True)
        return None

def process_all_files(field_name="DL_CCCH_Message"):
    """批量处理目录中的所有JSON文件"""
    # 创建输出目录和诊断目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DIAGNOSIS_FILE), exist_ok=True)
    
    # 打开日志文件
    with open(DIAGNOSIS_FILE, 'w') as log_file:
        log_file.write(f"[{datetime.now()}] 开始批量重编码处理\n")
        log_file.write(f"输入目录: {INPUT_DIR}\n")
        log_file.write(f"输出目录: {OUTPUT_DIR}\n")
        log_file.write(f"ASN.1 字段名: {field_name}\n\n")
        
        # 获取所有JSON文件
        json_files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.json')]
        log_file.write(f"找到 {len(json_files)} 个JSON文件待处理\n\n")
        
        success_count = 0
        for json_file in json_files:
            input_path = os.path.join(INPUT_DIR, json_file)
            
            # 编码文件
            encoded_bytes = reencode_from_json(input_path, field_name, log_file)
            
            if encoded_bytes:
                # 生成输出文件名 - 去掉.json后缀，加上.hex
                base_name = os.path.splitext(json_file)[0]
                output_file = os.path.join(OUTPUT_DIR, f"{base_name}.hex")
                
                # 保存编码结果
                try:
                    with open(output_file, 'w') as f:
                        f.write(encoded_bytes.hex())
                    success_msg = f"[INFO] 已将编码结果保存到 {output_file}"
                    log_file.write(success_msg + "\n")
                    print(success_msg, flush=True)
                    success_count += 1
                except Exception as e:
                    error_msg = f"[ERROR] 保存结果到文件 {output_file} 时出错: {e}"
                    log_file.write(error_msg + "\n")
                    print(error_msg, flush=True)
        
        # 记录处理总结
        summary = f"\n[{datetime.now()}] 处理完成\n"
        summary += f"成功处理: {success_count}/{len(json_files)} 个文件\n"
        log_file.write(summary)
        print(summary, flush=True)

if __name__ == "__main__":
    # 如果提供了命令行参数，则使用它作为field_name，否则使用默认值
    field_name = sys.argv[1] if len(sys.argv) > 1 else "DL_CCCH_Message"
    process_all_files(field_name)