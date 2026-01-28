import os

# 设置要重命名的目录路径
# directory = '/home/qiqingh/Desktop/5g_testing/ccsMarchBatch/output/boundary_test_exploits'
directory = '../output/payloads'

# 设置要添加的前缀
prefix = 'mac_sch_'

# 第二步：在文件前面添加前缀
for filename in os.listdir(directory):
    # 创建新的文件名
    new_filename = prefix + filename

    # 获取旧文件路径和新文件路径
    old_file = os.path.join(directory, filename)
    new_file = os.path.join(directory, new_filename)

    # 重命名文件
    os.rename(old_file, new_file)

    print(f"重命名: {filename} -> {new_filename}")

print("文件重命名完成。")
