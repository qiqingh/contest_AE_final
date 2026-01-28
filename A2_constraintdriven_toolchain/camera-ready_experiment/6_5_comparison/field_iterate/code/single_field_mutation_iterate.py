#!/usr/bin/env python3
"""
根据字段重要性和ASN.1类型生成变异测试用例，更新原始文件中的字段值。
"""

import os
import json
import random
import string
import math
import shutil
from typing import Dict, Any, List, Tuple, Optional, Union

def format_value_for_comparison(value: Any, field_type: str) -> Any:
    """
    格式化值用于比较。确保不同表示形式的相同值可以被正确比较。
    
    Args:
        value: 要格式化的值
        field_type: 字段类型
        
    Returns:
        格式化后的值
    """
    try:
        if field_type == "int":
            # 转换为整数进行比较
            return int(value) if value is not None else None
        elif field_type == "str":
            # 转换为字符串进行比较
            return str(value) if value is not None else ""
        elif field_type == "bool":
            # 处理布尔值的不同表示形式
            if isinstance(value, bool):
                return value
            elif isinstance(value, str):
                return value.lower() in ('true', 'yes', '1')
            elif isinstance(value, (int, float)):
                return bool(value)
            else:
                return bool(value)
        else:
            # 对于其他类型，直接返回
            return value
    except (ValueError, TypeError):
        # 如果转换失败，返回原始值
        return value

def generate_integer_mutations(field_info: Dict[str, Any], num_mutations: int) -> List[Dict[str, Any]]:
    """
    为INTEGER类型字段生成变异值，从最小值遍历到最大值（无限制）。
    
    Args:
        field_info: 字段信息
        num_mutations: 生成的变异数量（此版本中忽略）
        
    Returns:
        变异列表
    """
    import signal

    def timeout_handler(signum, frame):
        raise TimeoutError("INTEGER变异生成超时")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(30)  # 30秒超时（增加超时时间以应对大范围）
    
    try:
        # 获取字段范围
        field_rule = field_info["asn1_rules"]["rules"][0]
        min_val, max_val = field_rule["range"]
        
        # 计算范围大小
        range_size = max_val - min_val + 1
        
        # 创建变异列表
        mutations = []
        
        print(f"  生成 {range_size} 个变异值 (从 {min_val} 到 {max_val})")
        
        # 从最小值遍历到最大值（无限制）
        for value in range(min_val, max_val + 1):
            # 确定变异类型描述
            if value == min_val:
                mutation_type = "min_value"
                description = f"最小值 ({value})"
            elif value == max_val:
                mutation_type = "max_value"
                description = f"最大值 ({value})"
            else:
                mutation_type = "traverse_value"
                description = f"遍历值 ({value})"
            
            mutations.append({
                "mutation_value": value,
                "mutation_type": mutation_type,
                "description": description
            })
            
            # 每10000个值打印一次进度
            if (value - min_val) % 10000 == 0 and value != min_val:
                print(f"    进度: {value - min_val}/{range_size} ({(value - min_val)/range_size*100:.1f}%)")
        
        signal.alarm(0)  # 取消超时
        return mutations
    
    except TimeoutError as e:
        print(f"  警告: {e}，返回简化的变异集")
        # 超时时返回边界值作为后备方案
        return [
            {
                "mutation_value": field_info["asn1_rules"]["rules"][0]["range"][0],
                "mutation_type": "min_value",
                "description": "最小值 (超时简化)"
            },
            {
                "mutation_value": field_info["asn1_rules"]["rules"][0]["range"][1],
                "mutation_type": "max_value",
                "description": "最大值 (超时简化)"
            }
        ]
    except Exception as e:
        print(f"  警告: 整数变异生成出错: {e}")
        signal.alarm(0)
        return []
    finally:
        signal.alarm(0)

def generate_enumerated_mutations(field_info: Dict[str, Any], num_mutations: int) -> List[Dict[str, Any]]:
    """
    为ENUMERATED类型字段生成变异值，暴力遍历所有可能的枚举值。
    
    Args:
        field_info: 字段信息
        num_mutations: 生成的变异数量（在这个版本中忽略，始终返回所有可能值）
        
    Returns:
        变异列表
    """
    mutations = []
    
    # 获取枚举选项
    field_rule = field_info["asn1_rules"]["rules"][0]
    available_options = field_rule.get("available_options", [])
    
    # 如果没有可用选项，尝试从range中推断
    if not available_options and "range" in field_rule:
        min_val, max_val = field_rule["range"]
        available_options = list(range(min_val, max_val + 1))
    
    # 如果没有枚举选项，返回空列表
    if not available_options:
        print(f"警告: 枚举类型字段 {field_info.get('field_name', 'Unknown')} 没有可用选项。")
        return []
    
    # 创建所有枚举值的变异
    for i, option in enumerate(available_options):
        # 确定变异类型
        if i == 0:
            mutation_type = "enum_min"
            description = f"枚举最小值 ({option})"
        elif i == len(available_options) - 1:
            mutation_type = "enum_max"
            description = f"枚举最大值 ({option})"
        else:
            mutation_type = "enum_value"
            description = f"枚举值 ({option})"
        
        mutations.append({
            "mutation_value": option,
            "mutation_type": mutation_type,
            "description": description
        })
    
    return mutations

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
    
    # 根据类型生成变异，支持多种类型表示方式
    if field_type in ["INTEGER", "INT"]:
        # 对于INTEGER类型，生成所有边界值
        return generate_integer_mutations(field_info, -1)
    elif field_type in ["ENUMERATED", "ENUM"]:
        # 对于ENUMERATED类型，暴力遍历所有枚举值
        return generate_enumerated_mutations(field_info, -1)
    else:
        print(f"跳过不支持的字段类型 {field_type}，字段 {field_info.get('field_name', 'Unknown')}")
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

def process_field_files(input_dir: str, original_file_path: str, output_dir: str) -> Tuple[int, int, int, int]:
    """
    处理字段文件并生成变异。
    
    Args:
        input_dir: 输入目录
        original_file_path: 原始数据文件路径
        output_dir: 输出目录
        
    Returns:
        (处理文件数, 生成变异数, 跳过文件数, 相同值跳过数)
    """
    processed_count = 0
    mutations_count = 0
    skipped_count = 0
    same_value_skipped = 0
    timeout_count = 0
    problem_files = []
    
    # 创建诊断目录
    diagnosis_dir = "./diagnosis"
    os.makedirs(diagnosis_dir, exist_ok=True)
    
    # 加载原始数据
    original_data = load_original_data(original_file_path)
    if not original_data:
        print("无法加载原始数据，退出。")
        return 0, 0, 0, 0
    
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
            
            # 超时机制和警告
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError(f"处理文件 {filename} 超时")

            # 设置60秒超时（增加超时时间）
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(60)
            
            try:
                # 获取字段ID
                field_id = int(os.path.splitext(filename)[0])
                
                # 读取字段信息
                with open(file_path, 'r') as f:
                    field_info = json.load(f)
                
                # 找到原始数据中对应的字段
                original_field = find_field_in_original_data(field_id, original_data)
                if not original_field:
                    print(f"在原始数据中未找到字段ID {field_id}，跳过 {filename}")
                    skipped_count += 1
                    # 将问题文件复制到诊断目录
                    try:
                        shutil.copy2(file_path, os.path.join(diagnosis_dir, filename))
                    except:
                        pass
                    continue
                
                # 获取原始值
                current_value = original_field.get("current_value")
                field_type = original_field.get("field_type", "Unknown")
                
                # 打印处理阶段
                print(f"  生成变异中... (字段ID: {field_id}, 类型: {field_type})")
                
                # 生成变异
                try:
                    mutations = generate_mutations(field_info)
                except Exception as e:
                    print(f"为字段 {filename} 生成变异时出错: {e}")
                    skipped_count += 1
                    problem_files.append((filename, f"生成变异出错: {e}"))
                    # 将问题文件复制到诊断目录
                    try:
                        shutil.copy2(file_path, os.path.join(diagnosis_dir, filename))
                    except:
                        pass
                    continue
                
                if not mutations:
                    print(f"跳过 {filename} (无需变异)")
                    skipped_count += 1
                    continue
                
                # 获取字段信息
                field_name = field_info.get("field_name", original_field.get("field_name", "Unknown"))
                
                # 打印处理阶段
                print(f"  过滤相同值变异中... (生成了 {len(mutations)} 个变异)")
                
                # 过滤掉与原始值相同的变异
                filtered_mutations = []
                for mutation in mutations:
                    try:
                        mutation_value = mutation["mutation_value"]
                        
                        # 格式化变异值和原始值以便比较
                        formatted_mutation = format_value_for_comparison(mutation_value, field_type)
                        formatted_current = format_value_for_comparison(current_value, field_type)
                        
                        # 如果变异值与原始值相同，则跳过
                        if formatted_mutation == formatted_current:
                            print(f"  跳过变异: {mutation['description']} (与原始值相同: {current_value})")
                            same_value_skipped += 1
                        else:
                            filtered_mutations.append(mutation)
                    except Exception as e:
                        print(f"  比较变异值时出错: {e}")
                        # 如果比较失败，添加变异（宁可错误变异也不要漏掉）
                        filtered_mutations.append(mutation)
                
                # 如果所有变异都被过滤掉，跳过该字段
                if not filtered_mutations:
                    print(f"跳过 {filename} (所有变异值都与原始值相同)")
                    skipped_count += 1
                    continue
                
                # 打印处理阶段
                print(f"  创建变异文件中... (剩余 {len(filtered_mutations)} 个有效变异)")
                
                # 为每个变异创建文件
                for i, mutation in enumerate(filtered_mutations, 1):
                    try:
                        if create_mutation_file(field_id, mutation, original_data, output_dir, i):
                            mutations_count += 1
                            # 每100个变异打印一次进度
                            if i % 100 == 0 or i == len(filtered_mutations):
                                print(f"  已创建变异: {i}/{len(filtered_mutations)} ({mutation['description']})")
                    except Exception as e:
                        print(f"  创建变异文件时出错: {e}")
                
                processed_count += 1
                
                # 取消超时
                signal.alarm(0)
                
            except TimeoutError as e:
                print(f"警告: {e}")
                print(f"跳过超时文件: {filename}")
                timeout_count += 1
                skipped_count += 1
                problem_files.append((filename, "处理超时"))
                # 将问题文件复制到诊断目录
                try:
                    shutil.copy2(file_path, os.path.join(diagnosis_dir, filename))
                except:
                    pass
                # 取消超时
                signal.alarm(0)
                continue
            except json.JSONDecodeError:
                print(f"解析错误: {filename}")
                skipped_count += 1
                problem_files.append((filename, "JSON解析错误"))
                # 将问题文件复制到诊断目录
                try:
                    shutil.copy2(file_path, os.path.join(diagnosis_dir, filename))
                except:
                    pass
                # 取消超时
                signal.alarm(0)
            except ValueError:
                print(f"无效的文件名 (无法解析为字段ID): {filename}")
                skipped_count += 1
                problem_files.append((filename, "无效的文件名"))
                # 取消超时
                signal.alarm(0)
            except Exception as e:
                print(f"处理 {filename} 时出错: {e}")
                skipped_count += 1
                problem_files.append((filename, f"未知错误: {e}"))
                # 将问题文件复制到诊断目录
                try:
                    shutil.copy2(file_path, os.path.join(diagnosis_dir, filename))
                except:
                    pass
                # 取消超时
                signal.alarm(0)
            
            # 每处理10个文件显示一次进度
            if file_index % 10 == 0:
                print(f"进度: {file_index}/{total_files} ({file_index/total_files*100:.1f}%)")
    
    except Exception as e:
        print(f"读取目录出错: {e}")
    
    # 将问题文件列表写入诊断目录
    try:
        with open(os.path.join(diagnosis_dir, "problem_files.txt"), 'w') as f:
            f.write(f"总问题文件数: {len(problem_files)}\n\n")
            for filename, reason in problem_files:
                f.write(f"{filename}: {reason}\n")
    except Exception as e:
        print(f"写入问题文件列表时出错: {e}")
    
    print(f"\n处理统计:")
    print(f"处理成功: {processed_count}")
    print(f"生成变异: {mutations_count}")
    print(f"跳过字段: {skipped_count}")
    print(f"跳过相同值: {same_value_skipped}")
    print(f"超时文件: {timeout_count}")
    print(f"问题文件: {len(problem_files)} (已保存到 {diagnosis_dir})")
    
    return processed_count, mutations_count, skipped_count, same_value_skipped

def main():
    """主函数"""
    # 设置目录
    input_dir = "../asn-update/combine_fields"
    original_file_path = "../asn-update/02_flatten.json"
    output_dir = "../output/single_field_mutations_iterate"
    
    print(f"开始自动处理 {input_dir} 中的字段文件...")
    print(f"支持的字段类型: INTEGER/INT, ENUMERATED/ENUM")
    print(f"原始数据文件: {original_file_path}")
    print(f"输出目录: {output_dir}")
    print(f"注意: 已移除所有变异数量限制，将完全遍历所有可能值")
    
    processed, mutations, skipped, same_value_skipped = process_field_files(input_dir, original_file_path, output_dir)
    
    print("\n处理完成!")
    print(f"处理字段: {processed}")
    print(f"生成变异: {mutations}")
    print(f"跳过字段: {skipped}")
    print(f"跳过相同值: {same_value_skipped}")
    print(f"\n变异文件已保存到: {os.path.abspath(output_dir)}")
    print(f"问题文件已保存到: {os.path.abspath('./diagnosis')}")

if __name__ == "__main__":
    # 设置随机种子，使结果可重现
    random.seed(42)
    main()