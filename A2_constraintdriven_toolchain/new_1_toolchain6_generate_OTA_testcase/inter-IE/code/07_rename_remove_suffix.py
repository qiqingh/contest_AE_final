#!/usr/bin/env python3
"""
Batch rename script: Remove '_reconstructed_offset' part from filenames
"""

import os
import sys
from pathlib import Path

def batch_rename(directory_path):
    """
    Iterate through all files in the specified directory and remove the '_reconstructed_offset' part from the filenames
    
    Args:
        directory_path: Target directory path
    """
    # Convert to Path object
    dir_path = Path(directory_path)
    
    # Check if directory exists
    if not dir_path.exists():
        print(f"错误：目录 '{directory_path}' 不存在！")
        return
    
    if not dir_path.is_dir():
        print(f"错误：'{directory_path}' 不是一个目录！")
        return
    
    # Statistical Information
    total_files = 0
    renamed_files = 0
    skipped_files = 0
    errors = 0
    
    print(f"Processing directory: {dir_path.absolute()}")
    print("-" * 50)
    
    # Iterate through all files in the directory
    for file_path in dir_path.iterdir():
        # Process files only, skip directories
        if file_path.is_file():
            total_files += 1
            old_name = file_path.name
            
            # Check if the filename contains '_reconstructed_offset'
            if '_reconstructed_offset' in old_name:
                # Create new file name
                new_name = old_name.replace('_reconstructed_offset', '')
                new_path = file_path.parent / new_name
                
                try:
                    # Check if new file name already exists
                    if new_path.exists():
                        print(f"⚠️  跳过: '{old_name}' -> '{new_name}' (目标文件已存在)")
                        skipped_files += 1
                    else:
                        # Execute rename
                        file_path.rename(new_path)
                        print(f"✅ 成功: '{old_name}' -> '{new_name}'")
                        renamed_files += 1
                except Exception as e:
                    print(f"❌ 错误: 无法重命名 '{old_name}': {str(e)}")
                    errors += 1
            else:
                # Filename does not contain target string, skipping
                print(f"⏭️  跳过: '{old_name}' (不包含 '_reconstructed_offset')")
                skipped_files += 1
    
    # Print statistics
    print("-" * 50)
    print(f"Processing complete!")
    print(f"Total files: {total_files}")
    print(f"Successfully renamed: {renamed_files}")
    print(f"Skipped files: {skipped_files}")
    print(f"Number of errors: {errors}")

def main():
    """main function"""
    # Target directory path
    target_dir = '../output/06_payloads'
    
    # Execute batch rename
    batch_rename(target_dir)
    
    # Ask if you need to view the final results
    print("Do you want to view the final file list in the directory? (y/n):", end='')
    response = input().strip().lower()
    
    if response == 'y':
        print("Current directory file list:")
        print("-" * 50)
        dir_path = Path(target_dir)
        if dir_path.exists():
            for file_path in sorted(dir_path.iterdir()):
                if file_path.is_file():
                    print(f"  {file_path.name}")

if __name__ == "__main__":
    main()