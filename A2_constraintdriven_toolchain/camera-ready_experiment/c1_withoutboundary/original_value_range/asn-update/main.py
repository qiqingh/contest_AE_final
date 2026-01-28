import subprocess
import os
import sys

# 每个步骤可能会输出的关键文件（用于存在性检查）
output_files = [
    "decoded.json",
    "decoded_flattened.json",
    "decoded_flattened_reconstructed.json"
]

scripts = [
    {
        "script": "01_decode.py",
        "args": [],
        "output": "01_decoded.json"
    },
    {
        "script": "02_flatten.py",
        "args": ["-i", "01_decoded.json"],
        "output": "02_flattened.json"
    },
    {
        "script": "02.5_asn-range.py",
        "args": ["-f", "02_flattened.json","-o","combine_fields","-m", "DL_CCCH_Message"],
        "output": None
    },
    # {
    #     "script": "03_re-construct.py",
    #     "args": ["-f", "02_flattened.json", "-m", "02_metadata.json"],
    #     "output": "03_re-constructed.json"
    # },
    # {
    #     "script": "04_re-encode.py",
    #     "args": ["03_re-constructed.json", "DL_CCCH_Message"],
    #     "output": None  # 最后一步不检查文件输出
    # }
]

# 依次运行每个脚本
for step in scripts:
    cmd = ["python", step["script"]] + step["args"]
    print(f"\nRunning: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        print(f"[stdout]\n{result.stdout}")
        if result.stderr:
            print(f"[stderr]\n{result.stderr}")
    except Exception as e:
        print(f"[Exception] Failed to run {step['script']}: {e}")
        sys.exit(1)

    # 如果指定了输出文件，检查它是否生成成功
    if step["output"]:
        if not os.path.exists(step["output"]):
            print(f"[ERROR] Expected output file not found: {step['output']}")
            sys.exit(1)

    print("-" * 60)

print("✅ All scripts completed successfully.")
