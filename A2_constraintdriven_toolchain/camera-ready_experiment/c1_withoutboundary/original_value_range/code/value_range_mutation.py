#!/usr/bin/env python3
"""
根据字段重要性和ASN.1类型生成变异测试用例，更新原始文件中的字段值。
仅针对INTEGER类型生成最小值-1和最大值+1两个边界变异。
"""

import os
import json
import random
import shutil
from typing import Dict, Any, List, Tuple, Optional

def generate_integer_mutations(field_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    为INTEGER类型字段生成变异值，仅生成最小值-1和最大值+1。
    
    Args:
        field_info: 字段信息
        
    Returns:
        变异列表（固定2个变异）
    """
    try:
        # 获取字段范围
        field_rule = field_info["asn1_rules"]["rules"][0]
        min_val, max_val = field_rule["range"]
        
        # 创建边界值变异列表
        mutations = []
        
        # 1. 最小值-1（下溢测试）
        mutations.append({
            "mutation_value": min_val - 1,
            "mutation_type": "underflow",
            "description": f"最小值-1 ({min_val - 1}) - 下溢测试"
        })
        
        # 2. 最大值+1（上溢测试）
        mutations.append({
            "mutation_value": max_val + 1,
            "mutation_type": "overflow",
            "description": f"最大值+1 ({max_val + 1}) - 上溢测试"
        })
        
        return mutations
    
    except Exception as e:
        print(f"  警告: 整数变异生成出错: {e}")
        return []

def generate_mutations(field_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    根据字段信息生成变异。
    
    Args:
        field_info: 字段信息
        
    Returns:
        变异列表
    """
    # 获取字段类型
    field_type = "UNKNOWN"
    if "asn1_rules" in field_info and "rules" in field_info["asn1_rules"] and field_info["asn1_rules"]["rules"]:
        field_type = field_info["asn1_rules"]["rules"][0].get("type", "UNKNOWN")
    
    # 只处理INTEGER类型
    if field_type in ["INTEGER", "INT"]:
        return generate_integer_mutations(field_info)
    elif field_type in ["ENUMERATED", "ENUM"]:
        # 跳过ENUMERATED类型
        print(f"  跳过ENUMERATED类型字段 {field_info.get('field_name', 'Unknown')}")
        return []
    else:
        print(f"  跳过不支持的字段类型 {field_type}，字段 {field_info.get('field_name', 'Unknown')}")
        return []

def load_original_data(original_file_path: str) -> List[Dict[str, Any]]:
    """
    加载原始数据文件。
    
    Args:
        original_file_path: 原始数据文件路径
        
    Returns:
        原始数据列表
    """
    try:
        with open(original_file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载原始数据文件出错: {e}")
        return []

def format_value_by_type(value: Any, field_type: str) -> Any:
    """
    根据字段类型格式化值。
    
    Args:
        value: 原始值
        field_type: 字段类型
        
    Returns:
        格式化后的值
    """
    if field_type == "int":
        return int(value)
    elif field_type == "str":
        return str(value)
    elif field_type == "bool":
        return bool(value)
    else:
        # 对于其他类型，保持原样
        return value

def find_field_in_original_data(field_id: int, original_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    在原始数据中查找字段。
    
    Args:
        field_id: 字段ID
        original_data: 原始数据
        
    Returns:
        找到的字段，如未找到则返回None
    """
    for field in original_data:
        if field.get("field_id") == field_id:
            return field
    return None

def create_mutation_file(field_id: int, mutation: Dict[str, Any], 
                          original_data: List[Dict[str, Any]], 
                          output_dir: str, mutation_index: int) -> bool:
    """
    创建一个变异文件。
    
    Args:
        field_id: 字段ID
        mutation: 变异信息
        original_data: 原始数据
        output_dir: 输出目录
        mutation_index: 变异索引
        
    Returns:
        是否成功创建
    """
    # 复制原始数据
    mutated_data = []
    for field in original_data:
        field_copy = field.copy()
        # 如果是目标字段，更新suggested_value
        if field_copy.get("field_id") == field_id:
            # 根据字段类型格式化值
            field_type = field_copy.get("field_type", "")
            mutation_value = mutation["mutation_value"]
            
            # 根据field_type设置correct格式
            field_copy["suggested_value"] = format_value_by_type(mutation_value, field_type)
            # 添加变异信息
            field_copy["mutation_info"] = {
                "original_value": field_copy.get("current_value", None),
                "mutation_type": mutation["mutation_type"],
                "description": mutation["description"]
            }
            
        mutated_data.append(field_copy)
    
    # 创建输出文件名
    output_file = f"{field_id}_mut{mutation_index}.json"
    output_path = os.path.join(output_dir, output_file)
    
    # 保存到文件
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(mutated_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"保存变异文件时出错: {e}")
        return False

def process_field_files(input_dir: str, original_file_path: str, output_dir: str) -> Tuple[int, int, int]:
    """
    处理字段文件并生成变异。
    
    Args:
        input_dir: 输入目录
        original_file_path: 原始数据文件路径
        output_dir: 输出目录
        
    Returns:
        (处理文件数, 生成变异数, 跳过文件数)
    """
    processed_count = 0
    mutations_count = 0
    skipped_count = 0
    problem_files = []
    
    # 创建诊断目录
    diagnosis_dir = "./diagnosis"
    os.makedirs(diagnosis_dir, exist_ok=True)
    
    # 加载原始数据
    original_data = load_original_data(original_file_path)
    if not original_data:
        print("无法加载原始数据，退出。")
        return 0, 0, 0
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 获取所有JSON文件
    try:
        files = [f for f in os.listdir(input_dir) if f.endswith('.json')]
        total_files = len(files)
        print(f"找到 {total_files} 个字段文件")
        
        # 按文件名（数字）排序，便于定位
        files.sort(key=lambda x: int(os.path.splitext(x)[0]) if os.path.splitext(x)[0].isdigit() else float('inf'))
        
        for file_index, filename in enumerate(files, 1):
            file_path = os.path.join(input_dir, filename)
            
            # 显示处理进度
            print(f"\n处理文件 {file_index}/{total_files}: {filename}")
            
            try:
                # 获取字段ID
                field_id = int(os.path.splitext(filename)[0])
                
                # 读取字段信息
                with open(file_path, 'r') as f:
                    field_info = json.load(f)
                
                # 找到原始数据中对应的字段
                original_field = find_field_in_original_data(field_id, original_data)
                if not original_field:
                    print(f"  在原始数据中未找到字段ID {field_id}，跳过")
                    skipped_count += 1
                    # 将问题文件复制到诊断目录
                    try:
                        shutil.copy2(file_path, os.path.join(diagnosis_dir, filename))
                    except:
                        pass
                    continue
                
                # 获取原始值和字段类型
                current_value = original_field.get("current_value")
                field_type = original_field.get("field_type", "Unknown")
                
                # 生成变异
                try:
                    mutations = generate_mutations(field_info)
                except Exception as e:
                    print(f"  为字段生成变异时出错: {e}")
                    skipped_count += 1
                    problem_files.append((filename, f"生成变异出错: {e}"))
                    # 将问题文件复制到诊断目录
                    try:
                        shutil.copy2(file_path, os.path.join(diagnosis_dir, filename))
                    except:
                        pass
                    continue
                
                if not mutations:
                    print(f"  跳过 (非INTEGER类型或无法生成变异)")
                    skipped_count += 1
                    continue
                
                # 获取字段信息
                field_name = field_info.get("field_name", original_field.get("field_name", "Unknown"))
                
                # 强制为每个变异创建文件（不进行过滤）
                for i, mutation in enumerate(mutations, 1):
                    try:
                        if create_mutation_file(field_id, mutation, original_data, output_dir, i):
                            mutations_count += 1
                            
                            # 检查是否与原始值相同，仅用于显示警告
                            mutation_value = mutation["mutation_value"]
                            if mutation_value == current_value:
                                print(f"  ⚠ 已创建: {field_id}_mut{i}.json ({mutation['description']}) [警告: 与原始值相同]")
                            else:
                                print(f"  ✓ 已创建: {field_id}_mut{i}.json ({mutation['description']})")
                    except Exception as e:
                        print(f"  创建变异文件时出错: {e}")
                
                processed_count += 1
                
            except json.JSONDecodeError:
                print(f"  解析错误: JSON格式无效")
                skipped_count += 1
                problem_files.append((filename, "JSON解析错误"))
                # 将问题文件复制到诊断目录
                try:
                    shutil.copy2(file_path, os.path.join(diagnosis_dir, filename))
                except:
                    pass
            except ValueError:
                print(f"  无效的文件名 (无法解析为字段ID)")
                skipped_count += 1
                problem_files.append((filename, "无效的文件名"))
            except Exception as e:
                print(f"  处理时出错: {e}")
                skipped_count += 1
                problem_files.append((filename, f"未知错误: {e}"))
                # 将问题文件复制到诊断目录
                try:
                    shutil.copy2(file_path, os.path.join(diagnosis_dir, filename))
                except:
                    pass
            
            # 每处理10个文件显示一次进度
            if file_index % 10 == 0:
                print(f"\n进度: {file_index}/{total_files} ({file_index/total_files*100:.1f}%)")
    
    except Exception as e:
        print(f"读取目录出错: {e}")
    
    # 将问题文件列表写入诊断目录
    if problem_files:
        try:
            with open(os.path.join(diagnosis_dir, "problem_files.txt"), 'w') as f:
                f.write(f"总问题文件数: {len(problem_files)}\n\n")
                for filename, reason in problem_files:
                    f.write(f"{filename}: {reason}\n")
        except Exception as e:
            print(f"写入问题文件列表时出错: {e}")
    
    print(f"\n" + "="*50)
    print(f"处理统计:")
    print(f"  处理成功: {processed_count}")
    print(f"  生成变异: {mutations_count}")
    print(f"  跳过字段: {skipped_count}")
    if problem_files:
        print(f"  问题文件: {len(problem_files)} (已保存到 {diagnosis_dir})")
    print("="*50)
    
    return processed_count, mutations_count, skipped_count

def main():
    """主函数"""
    # 设置目录
    input_dir = "../asn-update/combine_fields"
    original_file_path = "../asn-update/02_flatten.json"
    output_dir = "../output/value_range_mutations"
    
    print("="*50)
    print("INTEGER字段边界变异生成工具")
    print("="*50)
    print(f"输入目录: {input_dir}")
    print(f"原始数据: {original_file_path}")
    print(f"输出目录: {output_dir}")
    print(f"变异策略: 仅INTEGER类型，强制生成最小值-1和最大值+1")
    print(f"注意: 即使变异值与原始值相同也会生成")
    print("="*50 + "\n")
    
    processed, mutations, skipped = process_field_files(input_dir, original_file_path, output_dir)
    
    print(f"\n✓ 处理完成!")
    print(f"变异文件已保存到: {os.path.abspath(output_dir)}")
    if os.path.exists("./diagnosis"):
        print(f"问题文件已保存到: {os.path.abspath('./diagnosis')}")

if __name__ == "__main__":
    # 设置随机种子，使结果可重现
    random.seed(42)
    main()
