import os
import hashlib
import csv

# 配置
source_dir = "./compiled_payloads"
mapping_file = "./payload_name_mapping.csv"

# 用于存储映射关系
mappings = []

# 获取所有文件
files = os.listdir(source_dir)

# 按 base name 分组（去掉扩展名）
base_names = {}
for filename in files:
    base_name, ext = os.path.splitext(filename)
    if base_name not in base_names:
        base_names[base_name] = []
    base_names[base_name].append(ext)

print(f"找到 {len(base_names)} 个唯一的 payload base name")

# 处理每个 base name
for base_name, extensions in sorted(base_names.items()):
    # 提取需要混淆的部分（去掉 mac_sch_ 前缀）
    if base_name.startswith("mac_sch_"):
        to_hash = base_name[8:]  # 去掉 "mac_sch_"
    else:
        print(f"警告: {base_name} 不以 mac_sch_ 开头，跳过")
        continue
    
    # 计算 MD5 前8位
    md5_hash = hashlib.md5(to_hash.encode()).hexdigest()[:8]
    new_base_name = f"mac_sch_{md5_hash}"
    
    # 保存映射关系
    mappings.append({
        'original_name': base_name,
        'obfuscated_name': new_base_name
    })
    
    # 重命名所有相关文件
    for ext in extensions:
        old_file = os.path.join(source_dir, base_name + ext)
        new_file = os.path.join(source_dir, new_base_name + ext)
        
        os.rename(old_file, new_file)
        print(f"✓ 重命名: {base_name}{ext} → {new_base_name}{ext}")

# 保存映射表
with open(mapping_file, 'w', encoding='utf-8', newline='') as f:
    fieldnames = ['original_name', 'obfuscated_name']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(mappings)

print(f"\n========== 完成 ==========")
print(f"处理的 payload 数量: {len(mappings)}")
print(f"映射表已保存到: {mapping_file}")