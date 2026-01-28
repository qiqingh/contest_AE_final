import os
import shutil
from pathlib import Path
import re

def extract_leading_number(filename):
    """
    从文件名中提取开头的数字
    例如: "2_mut1.json" -> 2, "123_mut5.json" -> 123
    """
    match = re.match(r'^(\d+)', filename)
    if match:
        return int(match.group(1))
    return float('inf')  # 如果没有数字，放到最后

def sample_and_copy_files(source_dir, target_dir, sample_size=3000):
    """
    从源目录按文件名开头的数字排序后取前N个文件并复制到目标目录
    
    Args:
        source_dir: 源目录路径
        target_dir: 目标目录路径
        sample_size: 要采样的文件数量
    """
    source_path = Path(source_dir)
    target_path = Path(target_dir)
    
    # 确保源目录存在
    if not source_path.exists():
        print(f"错误: 源目录不存在 - {source_dir}")
        return
    
    # 创建目标目录（如果不存在）
    target_path.mkdir(parents=True, exist_ok=True)
    print(f"目标目录: {target_dir}")
    
    # 获取源目录中的所有文件（不包括子目录）
    all_files = [f for f in source_path.iterdir() if f.is_file()]
    
    # 按文件名开头的数字排序
    sorted_files = sorted(all_files, key=lambda x: extract_leading_number(x.name))
    
    print(f"源目录中共有 {len(sorted_files)} 个文件")
    print(f"前5个文件示例: {[f.name for f in sorted_files[:5]]}")
    
    # 取前N个文件
    files_to_copy = sorted_files[:sample_size]
    print(f"\n准备复制前 {len(files_to_copy)} 个文件")
    
    # 复制文件
    success_count = 0
    for i, file_path in enumerate(files_to_copy, 1):
        try:
            target_file = target_path / file_path.name
            shutil.copy2(file_path, target_file)
            success_count += 1
            
            # 每100个文件打印一次进度
            if i % 100 == 0:
                print(f"已复制 {i}/{len(files_to_copy)} 个文件...")
        except Exception as e:
            print(f"复制文件失败 {file_path.name}: {e}")
    
    print(f"\n完成! 成功复制 {success_count} 个文件到 {target_dir}")
    print(f"最后一个文件: {files_to_copy[-1].name if files_to_copy else 'N/A'}")

if __name__ == "__main__":
    source_directory = "../output/single_field_mutations_iterate"
    target_directory = "../output/single_field_mutations_iterate_sample"
    
    sample_and_copy_files(source_directory, target_directory, sample_size=3000)