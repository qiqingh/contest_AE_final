#!/usr/bin/env python3
import os
import re
import csv
import json
from collections import defaultdict

# =========================================================
# =============== 用户配置 ================================
# =========================================================
ROOT_DIR = "/home/qiqingh/Desktop/contest_AE_battle/A2_constraintdriven_toolchain/camera-ready_experiment/our_approach/gdb_results"  # 自己设定
PROJECT_PREFIX = "/home/openairinterface5g/"
RFSIMULATOR_PATH = "/home/openairinterface5g/radio/rfsimulator/simulator.c"

# =========================================================
# ================== 正则表达式 ===========================
# =========================================================
# SIGSEGV: 匹配 "at /home/openairinterface5g/...:行号" (任意文件类型)
SIGSEGV_LOCATION_RE = re.compile(r'at\s+(/home/openairinterface5g/[^:]+):(\d+)')

# SIGABRT: 匹配 exit_function 行中的 file="..." 和 line=行号
SIGABRT_EXIT_FUNC_RE = re.compile(
    r'exit_function.*?file=file@entry=0x[0-9a-f]+\s+"([^"]+)".*?line=line@entry=(\d+)',
    re.MULTILINE | re.DOTALL
)

# =========================================================
# ================== 提取 SIGSEGV =========================
# =========================================================
def extract_sigsegv_location(content):
    """从内容中提取 SIGSEGV 的 crash 位置"""
    if 'SIGSEGV' not in content:
        return None
    
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'SIGSEGV' in line:
            # 检查后续5行
            context = '\n'.join(lines[i:i+5])
            match = SIGSEGV_LOCATION_RE.search(context)
            if match:
                return match.group(1), match.group(2)
    return None

# =========================================================
# ================== 提取 SIGABRT =========================
# =========================================================
def extract_sigabrt_location(content):
    """从内容中提取 SIGABRT 的 crash 位置（通过 exit_function）"""
    if 'SIGABRT' not in content:
        return None
    
    matches = SIGABRT_EXIT_FUNC_RE.findall(content)
    if matches:
        return matches[0]  # (file_path, line_number)
    return None

# =========================================================
# ================== 提取单个日志 =========================
# =========================================================
def extract_bug(log_path):
    """提取单个日志文件的 bug 信息"""
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {log_path}: {e}")
        return None
    
    # 先检查 SIGSEGV
    result = extract_sigsegv_location(content)
    if result:
        file_path, line_number = result
        return {
            "signal": "SIGSEGV",
            "bug_line": f"{file_path}:{line_number}",
            "is_libc": not file_path.startswith(PROJECT_PREFIX),
            "is_rfsimulator": file_path == RFSIMULATOR_PATH,
        }
    
    # 再检查 SIGABRT
    result = extract_sigabrt_location(content)
    if result:
        file_path, line_number = result
        return {
            "signal": "SIGABRT",
            "bug_line": f"{file_path}:{line_number}",
            "is_libc": not file_path.startswith(PROJECT_PREFIX),
            "is_rfsimulator": file_path == RFSIMULATOR_PATH,
        }
    
    return None

# =========================================================
# ======================== 主流程 =========================
# =========================================================
def main():
    bug_to_testcases = defaultdict(set)
    bug_meta = {}
    
    stats = {
        "total_logs_scanned": 0,
        "total_crashes": 0,
        "signals": defaultdict(int),
    }
    
    for dirpath, dirnames, filenames in os.walk(ROOT_DIR):
        for fname in filenames:
            if not fname.endswith(".log"):
                continue
            
            stats["total_logs_scanned"] += 1
            log_path = os.path.join(dirpath, fname)
            
            # test_case: 相对路径
            testcase = os.path.relpath(log_path, ROOT_DIR)
            
            result = extract_bug(log_path)
            if not result:
                continue
            
            stats["total_crashes"] += 1
            stats["signals"][result["signal"]] += 1
            
            bug = result["bug_line"]
            bug_to_testcases[bug].add(testcase)
            
            if bug not in bug_meta:
                bug_meta[bug] = {
                    "signal": result["signal"],
                    "is_libc": result["is_libc"],
                    "is_rfsimulator": result["is_rfsimulator"],
                }
    
    # 输出 bug_lines.csv
    with open("bug_lines.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["bug_line", "signal", "is_libc", "is_rfsimulator", "test_case"])
        for bug, tcs in sorted(bug_to_testcases.items()):
            meta = bug_meta[bug]
            for tc in sorted(tcs):
                writer.writerow([
                    bug,
                    meta["signal"],
                    meta["is_libc"],
                    meta["is_rfsimulator"],
                    tc
                ])
    
    # 输出 summary.json
    distinct_by_signal = defaultdict(int)
    libc_count = 0
    rfsimulator_count = 0
    
    for meta in bug_meta.values():
        distinct_by_signal[meta["signal"]] += 1
        if meta["is_libc"]:
            libc_count += 1
        if meta["is_rfsimulator"]:
            rfsimulator_count += 1
    
    summary = {
        "total_logs_scanned": stats["total_logs_scanned"],
        "total_crashes": stats["total_crashes"],
        "signals": dict(stats["signals"]),
        "distinct_bug_lines": len(bug_meta),
        "distinct_bug_lines_by_signal": dict(distinct_by_signal),
        "libc_bug_lines": libc_count,
        "non_libc_bug_lines": len(bug_meta) - libc_count,
        "rfsimulator_bug_lines": rfsimulator_count,
    }
    
    with open("summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    print("Done. Generated:")
    print("  - bug_lines.csv")
    print("  - summary.json")

if __name__ == "__main__":
    main()