#!/usr/bin/env python3
import os
import re
import csv
import json
from collections import defaultdict

# =========================================================
# =============== 用户配置 ================================
# =========================================================
ROOT_DIR = "/home/qiqingh/Desktop/contest_AE_battle/A2_constraintdriven_toolchain/camera-ready_experiment/new_all_results"
PROJECT_PREFIX = "/home/openairinterface5g/"
RFSIMULATOR_PATH = "/home/openairinterface5g/radio/rfsimulator/simulator.c"

# =========================================================
# ================== 正则表达式 ===========================
# =========================================================
SIGSEGV_LOCATION_RE = re.compile(r'at\s+(/home/openairinterface5g/[^:]+):(\d+)')
SIGABRT_EXIT_FUNC_RE = re.compile(
    r'exit_function.*?file=file@entry=0x[0-9a-f]+\s+"([^"]+)".*?line=line@entry=(\d+)',
    re.MULTILINE | re.DOTALL
)

# =========================================================
# ================== 提取类别 =============================
# =========================================================
def extract_category(testcase_path):
    """从测试用例路径中提取类别 (c1, c2, c3, c4)"""
    parts = testcase_path.split('/')
    
    # 优先检查第二级目录（更具体的分类）
    if len(parts) >= 2:
        second_part = parts[1]
        for category in ['c1', 'c2', 'c3', 'c4']:
            if second_part.startswith(f'{category}_'):
                return category
    
    # 如果第二级不存在或不匹配，再检查第一级
    if len(parts) >= 1:
        first_part = parts[0]
        for category in ['c1', 'c2', 'c3', 'c4']:
            if first_part.startswith(f'{category}_'):
                return category
    
    return 'unknown'

# =========================================================
# ================== 判断是否需要排除 =====================
# =========================================================
def should_exclude_simulator(bug_line):
    """判断是否应该排除该 bug（simulator.c:1052 或 simulator.c:1053）"""
    return bug_line.endswith("simulator.c:1052") or bug_line.endswith("simulator.c:1053")

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
        return matches[0]
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
    
    # 新增：记录每个 bug 对应的类别集合
    bug_to_categories = defaultdict(set)
    
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
            
            testcase = os.path.relpath(log_path, ROOT_DIR)
            
            result = extract_bug(log_path)
            if not result:
                continue
            
            stats["total_crashes"] += 1
            stats["signals"][result["signal"]] += 1
            
            bug = result["bug_line"]
            category = extract_category(testcase)
            
            bug_to_testcases[bug].add(testcase)
            bug_to_categories[bug].add(category)
            
            if bug not in bug_meta:
                bug_meta[bug] = {
                    "signal": result["signal"],
                    "is_libc": result["is_libc"],
                    "is_rfsimulator": result["is_rfsimulator"],
                }
    
    # 输出 bug_lines.csv（增加 category 列）
    with open("bug_lines.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["bug_line", "signal", "is_libc", "is_rfsimulator", "category", "test_case"])
        for bug, tcs in sorted(bug_to_testcases.items()):
            meta = bug_meta[bug]
            for tc in sorted(tcs):
                category = extract_category(tc)
                writer.writerow([
                    bug,
                    meta["signal"],
                    meta["is_libc"],
                    meta["is_rfsimulator"],
                    category,
                    tc
                ])
    
    # 统计每个类别的 distinct bugs（完整统计）
    category_distinct_bugs = defaultdict(set)
    for bug, categories in bug_to_categories.items():
        for cat in categories:
            category_distinct_bugs[cat].add(bug)
    
    category_stats = {cat: len(bugs) for cat, bugs in category_distinct_bugs.items()}
    
    # 统计每个类别的 distinct bugs（排除 simulator.c:1052/1053）
    category_distinct_bugs_filtered = defaultdict(set)
    for bug, categories in bug_to_categories.items():
        if should_exclude_simulator(bug):
            continue
        for cat in categories:
            category_distinct_bugs_filtered[cat].add(bug)
    
    category_stats_filtered = {cat: len(bugs) for cat, bugs in category_distinct_bugs_filtered.items()}
    
    # 输出 summary.json
    distinct_by_signal = defaultdict(int)
    distinct_by_signal_filtered = defaultdict(int)
    libc_count = 0
    libc_count_filtered = 0
    rfsimulator_count = 0
    rfsimulator_count_filtered = 0
    
    for bug, meta in bug_meta.items():
        distinct_by_signal[meta["signal"]] += 1
        if meta["is_libc"]:
            libc_count += 1
        if meta["is_rfsimulator"]:
            rfsimulator_count += 1
        
        # 排除 simulator.c:1052/1053 的统计
        if not should_exclude_simulator(bug):
            distinct_by_signal_filtered[meta["signal"]] += 1
            if meta["is_libc"]:
                libc_count_filtered += 1
            if meta["is_rfsimulator"]:
                rfsimulator_count_filtered += 1
    
    # 计算排除后的总数
    distinct_bugs_filtered = sum(1 for bug in bug_meta.keys() if not should_exclude_simulator(bug))
    
    summary = {
        "total_logs_scanned": stats["total_logs_scanned"],
        "total_crashes": stats["total_crashes"],
        "signals": dict(stats["signals"]),
        
        # === 完整统计（包含所有 crash sites） ===
        "distinct_bug_lines": len(bug_meta),
        "distinct_bug_lines_by_signal": dict(distinct_by_signal),
        "distinct_bug_lines_by_category": category_stats,
        "libc_bug_lines": libc_count,
        "non_libc_bug_lines": len(bug_meta) - libc_count,
        "rfsimulator_bug_lines": rfsimulator_count,
        
        # === 排除 simulator.c:1052/1053 的统计 ===
        "distinct_bug_lines_excluding_simulator_1052_1053": distinct_bugs_filtered,
        "distinct_bug_lines_by_signal_excluding_simulator_1052_1053": dict(distinct_by_signal_filtered),
        "distinct_bug_lines_by_category_excluding_simulator_1052_1053": category_stats_filtered,
        "libc_bug_lines_excluding_simulator_1052_1053": libc_count_filtered,
        "non_libc_bug_lines_excluding_simulator_1052_1053": distinct_bugs_filtered - libc_count_filtered,
        "rfsimulator_bug_lines_excluding_simulator_1052_1053": rfsimulator_count_filtered,
    }
    
    with open("summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    print("Done. Generated:")
    print("  - bug_lines.csv")
    print("  - summary.json")
    print(f"\n{'='*60}")
    print(f"FULL STATISTICS (including all crash sites):")
    print(f"{'='*60}")
    print(f"Total distinct bug lines: {len(bug_meta)}")
    print(f"\nBy category:")
    for cat in sorted(category_stats.keys()):
        print(f"  {cat}: {category_stats[cat]} distinct bugs")
    
    print(f"\n{'='*60}")
    print(f"FILTERED STATISTICS (excluding simulator.c:1052/1053):")
    print(f"{'='*60}")
    print(f"Total distinct bug lines: {distinct_bugs_filtered}")
    print(f"\nBy category:")
    for cat in sorted(category_stats_filtered.keys()):
        print(f"  {cat}: {category_stats_filtered[cat]} distinct bugs")

if __name__ == "__main__":
    main()
