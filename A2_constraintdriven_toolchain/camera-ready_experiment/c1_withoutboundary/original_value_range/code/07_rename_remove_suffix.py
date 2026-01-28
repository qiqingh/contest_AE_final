#!/usr/bin/env python3
"""
批量重命名脚本：去除文件名中的 '_reconstructed_offset' 部分
"""

import os
import sys
from pathlib import Path

def batch_rename(directory_path):
    """
    遍历指定目录下的所有文件，去除文件名中的 '_reconstructed_offset' 部分
    
    Args:
        directory_path: 目标目录路径
    """
    # 转换为Path对象
    dir_path = Path(directory_path)
    
    # 检查目录是否存在
    if not dir_path.exists():
        print(f"错误：目录 '{directory_path}' 不存在！")
        return
    
    if not dir_path.is_dir():
        print(f"错误：'{directory_path}' 不是一个目录！")
        return
    
    # 统计信息
    total_files = 0
    renamed_files = 0
    skipped_files = 0
    errors = 0
    
    print(f"开始处理目录: {dir_path.absolute()}")
    print("-" * 50)
    
    # 遍历目录中的所有文件
    for file_path in dir_path.iterdir():
        # 只处理文件，跳过目录
        if file_path.is_file():
            total_files += 1
            old_name = file_path.name
            
            # 检查文件名是否包含 '_reconstructed_offset'
            if '_reconstructed_offset' in old_name:
                # 构建新文件名
                new_name = old_name.replace('_reconstructed_offset', '')
                new_path = file_path.parent / new_name
                
                try:
                    # 检查新文件名是否已存在
                    if new_path.exists():
                        print(f"⚠️  跳过: '{old_name}' -> '{new_name}' (目标文件已存在)")
                        skipped_files += 1
                    else:
                        # 执行重命名
                        file_path.rename(new_path)
                        print(f"✅ 成功: '{old_name}' -> '{new_name}'")
                        renamed_files += 1
                except Exception as e:
                    print(f"❌ 错误: 无法重命名 '{old_name}': {str(e)}")
                    errors += 1
            else:
                # 文件名不包含目标字符串，跳过
                print(f"⏭️  跳过: '{old_name}' (不包含 '_reconstructed_offset')")
                skipped_files += 1
    
    # 打印统计信息
    print("-" * 50)
    print(f"处理完成！")
    print(f"总文件数: {total_files}")
    print(f"成功重命名: {renamed_files}")
    print(f"跳过文件: {skipped_files}")
    print(f"错误数: {errors}")

def main():
    """主函数"""
    # 目标目录路径
    target_dir = '../output/payloads'
    
    # 执行批量重命名
    batch_rename(target_dir)
    
    # 询问是否需要查看最终结果
    print("\n是否要查看目录中的最终文件列表？(y/n): ", end='')
    response = input().strip().lower()
    
    if response == 'y':
        print("\n当前目录文件列表:")
        print("-" * 50)
        dir_path = Path(target_dir)
        if dir_path.exists():
            for file_path in sorted(dir_path.iterdir()):
                if file_path.is_file():
                    print(f"  {file_path.name}")

if __name__ == "__main__":
    main()