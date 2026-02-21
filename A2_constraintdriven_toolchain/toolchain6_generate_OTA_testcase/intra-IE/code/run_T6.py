#!/usr/bin/env python3
"""
T6 - OTA-Style Testcase Payload Generation
Place this script in the target code directory and run it directly.

Usage:
    python3 run_T6.py
"""

import subprocess
import sys
import time


def run_step(script_name, step_num, total):
    print(f"\n[{step_num}/{total}] Running {script_name} ...")
    start = time.time()
    result = subprocess.run(["python3", script_name])
    elapsed = time.time() - start
    if result.returncode != 0:
        print(f"[ERROR] {script_name} failed (return code {result.returncode}). Aborting.")
        sys.exit(1)
    print(f"[OK] {script_name} completed in {elapsed:.1f}s")


scripts = [
    "03_re-construct.py",
    "04_re-encode.py",
    "05_cal_offset.py",
    "06_payload.py",
    "07_rename.py",
    "08_rename.py",
]

total_start = time.time()
for i, script in enumerate(scripts, 1):
    run_step(script, i, len(scripts))

total_elapsed = time.time() - total_start
print(f"\n[DONE] All T6 steps completed in {total_elapsed:.1f}s")