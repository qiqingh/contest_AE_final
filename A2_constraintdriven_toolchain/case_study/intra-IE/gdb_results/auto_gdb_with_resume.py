import subprocess
import time
import os
import signal
from datetime import datetime

# 容器配置
CONTAINER_ID = "3fb8867e471a"
PAYLOAD_DIR = "/home/qiqingh/Desktop/contest_AE_battle/A2_constraintdriven_toolchain/case_study/intra-IE/output/compiled_case_study_intra-IE"

# 进程信息
MAX_RUNS = 2  # 限制最多自动捕获 UE 崩溃的次数
GDB_TIMEOUT = 5  # GDB 运行时间（秒）

def is_payload_completed(payload_name):
    """检查 payload 是否已经执行过（通过检查输出文件夹）"""
    safe_payload_name = payload_name.replace('/', '_')
    log_dir = f"{safe_payload_name}/"
    
    # 检查目录是否存在
    if not os.path.exists(log_dir):
        return False
    
    # 检查目录中是否有 .log 文件
    try:
        log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
        if log_files:
            print(f"[SKIP] Payload {payload_name} 已完成（找到 {len(log_files)} 个日志文件），跳过")
            return True
    except Exception as e:
        print(f"[WARNING] 检查目录 {log_dir} 时出错: {e}")
    
    return False

def setup_log_directory(payload_name):
    """创建日志目录 {PAYLOAD_NAME}/"""
    # 将路径中的 / 替换为 _ 以避免目录嵌套问题
    safe_payload_name = payload_name.replace('/', '_')
    log_dir = f"{safe_payload_name}/"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        print(f"[INFO] 创建日志目录: {log_dir}")
    return log_dir

def run_fuzzer(payload_name):
    """在容器内启动 5g_fuzzer"""
    # 只使用文件名部分作为 exploit 参数
    exploit_name = os.path.basename(payload_name)
    
    command = f"sudo docker exec {CONTAINER_ID} bash -c 'cd /home/5ghoul-5g-nr-attacks && sudo bin/5g_fuzzer --EnableSimulator=true --exploit={exploit_name} --MCC=001 --MNC=01 --GlobalTimeout=false --EnableMutation=false' &"
    
    print(f"[INFO] 在容器内启动 5g_fuzzer，Payload 路径: {payload_name}, Exploit: {exploit_name}")
    os.system(command)
    return None

def get_latest_ue_pid():
    """获取容器内最新的 OAI UE 进程 PID"""
    try:
        cmd = (
            f"sudo docker exec {CONTAINER_ID} bash -c "
            f"\"ps -ef | grep '/home/openairinterface5g/cmake_targets/ran_build/build/nr-uesoftmodem' "
            f"| grep -v 'grep' | awk '{{print \\$2}}' | head -n 1\""
        )
        
        pid = subprocess.check_output(cmd, shell=True).decode().strip()
        
        if pid:
            print(f"[INFO] 找到最新的 OAI UE 进程，PID: {pid}")
            return pid
    except subprocess.CalledProcessError:
        return None

def run_gdb(run_index, payload_name, log_dir):
    """在容器内执行 GDB，日志保存到宿主机"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    gdb_log = f"{log_dir}ue_crash_{run_index}_{timestamp}.log"
    
    pid = get_latest_ue_pid()
    if not pid:
        print("[WARNING] 未找到 OAI UE 进程，跳过 GDB attach")
        return None
    
    gdb_cmd = (
        f"sudo docker exec {CONTAINER_ID} bash -c "
        f"'echo -e \"set pagination off\\ncontinue\\nbt full\\nquit\\ny\" | "
        f"sudo gdb -q -p {pid}' > {gdb_log} 2>&1"
    )
    
    print(f"[INFO] 执行 GDB 并 Attach 到最新的 UE 进程 (PID: {pid})，日志：{gdb_log}")
    
    gdb_proc = subprocess.Popen(gdb_cmd, shell=True)
    gdb_proc.wait()
    return gdb_log

def extract_crash_info(gdb_log):
    """从 GDB 输出文件中提取崩溃代码行"""
    crash_info = []
    if not gdb_log:
        return

    with open(gdb_log, "r") as file:
        lines = file.readlines()

    capturing = False
    for line in lines:
        if "Program received signal SIGSEGV" in line or "Program received signal SIGABRT" in line:
            capturing = True  # 进入崩溃状态，开始记录 backtrace
            crash_info.append(line.strip())  # 记录信号类型
        elif capturing:
            if line.strip().startswith("#"):  # GDB backtrace 行
                crash_info.append(line.strip())
            elif line.strip() == "":  # 空行代表结束
                break

    if crash_info:
        crash_summary = "\n".join(crash_info)
        summary_file = gdb_log.replace(".log", "_summary.log")
        with open(summary_file, "w") as file:
            file.write(crash_summary)
        print(f"[INFO] 崩溃分析摘要保存到: {summary_file}")

def monitor_ue(payload_name):
    """持续监测 UE 崩溃，每次重新运行 GDB"""
    log_dir = setup_log_directory(payload_name)  # 确保日志目录存在
    run_count = 0
    
    run_fuzzer(payload_name)
    
    time.sleep(5)  # 等待 UE 进程启动
    
    while run_count < MAX_RUNS:
        print(f"\n[INFO] Payload: {payload_name}, 第 {run_count+1} 轮检测...")
        
        gdb_log = run_gdb(run_count, payload_name, log_dir)
        
        if gdb_log:
            print(f"[INFO] UE 崩溃！backtrace 记录在 {gdb_log}")
            extract_crash_info(gdb_log)  # 提取崩溃代码行
        
        run_count += 1
        time.sleep(2)  # 稍等，让 UE 重新启动
    
    print(f"[INFO] Payload {payload_name} 执行完毕，终止 fuzzer 进程...")
    # 使用文件名部分来终止进程
    exploit_name = os.path.basename(payload_name)
    kill_cmd = f"sudo docker exec {CONTAINER_ID} bash -c 'pkill -f \"5g_fuzzer.*{exploit_name}\"'"
    os.system(kill_cmd)

def read_payloads():
    """递归遍历 payload 目录并返回所有文件名（不含扩展名）"""
    if not os.path.exists(PAYLOAD_DIR):
        print(f"[ERROR] 目录 {PAYLOAD_DIR} 不存在！")
        return []
    
    payloads = []
    try:
        # 递归遍历所有文件
        for root, dirs, files in os.walk(PAYLOAD_DIR):
            for filename in files:
                # 获取完整文件路径
                filepath = os.path.join(root, filename)
                # 获取相对于PAYLOAD_DIR的路径
                relative_path = os.path.relpath(filepath, PAYLOAD_DIR)
                # 去除扩展名
                payload_name = os.path.splitext(relative_path)[0]
                payloads.append(payload_name)
        
        # 排序以保证执行顺序一致
        payloads.sort()
        print(f"[INFO] 从 {PAYLOAD_DIR} 递归读取到 {len(payloads)} 个 Payload")
        
        # 打印前几个 payload 名称以便确认
        if payloads:
            print(f"[INFO] 前几个 Payload: {', '.join(payloads[:5])}...")
            
    except Exception as e:
        print(f"[ERROR] 读取目录时出错: {e}")
    
    return payloads

if __name__ == "__main__":
    payloads = read_payloads()

    if not payloads:
        print("[ERROR] 没有可用的 Payload，退出程序。")
        exit(1)

    print(f"\n[INFO] 总共需要处理 {len(payloads)} 个 Payload")
    
    # 统计已完成和待处理的数量
    completed_count = 0
    pending_payloads = []
    
    for payload in payloads:
        if is_payload_completed(payload):
            completed_count += 1
        else:
            pending_payloads.append(payload)
    
    print(f"[INFO] 已完成: {completed_count} 个，待处理: {len(pending_payloads)} 个")
    
    if not pending_payloads:
        print("[INFO] 所有 Payload 已完成，无需继续执行。")
        exit(0)
    
    print(f"\n[INFO] 开始处理剩余的 {len(pending_payloads)} 个 Payload...\n")
    
    for idx, payload in enumerate(pending_payloads, 1):
        print(f"\n{'='*60}")
        print(f"[PROGRESS] 正在处理 {idx}/{len(pending_payloads)}: {payload}")
        print(f"{'='*60}\n")
        monitor_ue(payload)
    
    print(f"\n[INFO] 全部完成！")
    print(f"[INFO] 成功处理: {len(pending_payloads)} 个")
    print(f"[INFO] 总计完成: {len(payloads)} 个")