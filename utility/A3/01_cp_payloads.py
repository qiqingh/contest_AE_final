import pandas as pd
import os
import shutil
from pathlib import Path

# 配置
INPUT_CSV = "./bug_lines_dedup.csv"
COMPILED_DIR = "/home/qiqingh/Desktop/contest_AE_final/A2_constraintdriven_toolchain/camera-ready_experiment/compiled_our_approach"
OUTPUT_DIR = "./compiled_payloads"

def extract_payload_name(test_case_path):
    """
    从 test_case 路径提取 payload 名称（保留 _mutX 后缀）
    
    输入: c1_gdb_results/c1_compiled_value_range_payloads_mac_sch_346_mut1/ue_crash_0.log
    输出: mac_sch_346_mut1  （保留 _mut1）
    
    输入: c3_c4_gdb_results/c3_compiled_intra-IE_mac_sch_f452_f453/ue_crash_1.log
    输出: mac_sch_f452_f453
    """
    parts = test_case_path.split('/')
    if len(parts) < 2:
        return None
    
    folder_name = parts[1]
    
    # 根据前缀提取 payload 名称
    prefixes = [
        'c1_compiled_value_range_payloads_',
        'c2_compiled_presence_payloads_',
        'c3_compiled_intra-IE_',
        'c4_compiled_inter-IE_'
    ]
    
    payload = None
    for prefix in prefixes:
        if folder_name.startswith(prefix):
            payload = folder_name.replace(prefix, '')
            break
    
    # 直接返回完整名称（包含 _mutX 后缀）
    return payload

def find_payload_files(compiled_dir, payload_name):
    """在编译目录中查找 payload 文件"""
    compiled_path = Path(compiled_dir)
    matches = []
    
    for category_dir in compiled_path.iterdir():
        if not category_dir.is_dir():
            continue
        
        for ext in ['.cpp', '.so', '.o']:
            pattern = f"{payload_name}{ext}"
            matching_files = list(category_dir.glob(pattern))
            matches.extend(matching_files)
    
    return matches

def main():
    # 读取去重后的 CSV
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 找不到输入文件: {INPUT_CSV}")
        print(f"请先运行去重脚本生成 {INPUT_CSV}")
        return
    
    df = pd.read_csv(INPUT_CSV)
    print(f"📊 读取 {len(df)} 个唯一 bug")
    
    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 提取所有唯一的 payload 名称
    payloads = set()
    payload_map = {}  # payload -> test_case 映射
    
    for _, row in df.iterrows():
        payload = extract_payload_name(row['test_case'])
        if payload:
            payloads.add(payload)
            payload_map[payload] = row['test_case']
    
    print(f"🎯 发现 {len(payloads)} 个唯一 payload")
    
    # 复制文件
    copied_count = 0
    not_found = []
    
    for payload in sorted(payloads):
        files = find_payload_files(COMPILED_DIR, payload)
        
        if files:
            for src_file in files:
                dst_file = Path(OUTPUT_DIR) / src_file.name
                shutil.copy2(src_file, dst_file)
                copied_count += 1
            print(f"✅ {payload}: 复制 {len(files)} 个文件")
        else:
            not_found.append(payload)
            print(f"⚠️  {payload}: 未找到文件")
    
    # 统计
    print(f"\n" + "="*60)
    print(f"✅ 成功复制: {copied_count} 个文件")
    print(f"🎯 对应 {len(payloads) - len(not_found)} 个唯一 payload")
    print(f"⚠️  未找到: {len(not_found)} 个 payload")
    print(f"📁 输出目录: {OUTPUT_DIR}")
    
    if not_found:
        print(f"\n⚠️  未找到的 payload:")
        for p in not_found[:10]:
            print(f"  - {p}")
        if len(not_found) > 10:
            print(f"  ... 还有 {len(not_found)-10} 个")

if __name__ == "__main__":
    main()