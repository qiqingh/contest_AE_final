import pandas as pd

# 输入文件路径
input_file = "/home/qiqingh/Desktop/contest_AE_final/A2_constraintdriven_toolchain/camera-ready_experiment/new_all_results/bug_lines.csv"

# 输出文件路径
output_file = "./bug_lines_dedup.csv"

# 读取 CSV 文件
df = pd.read_csv(input_file)

print(f"原始数据行数: {len(df)}")
print(f"唯一 bug_line 数量: {df['bug_line'].nunique()}")

# 按 bug_line 去重，保留第一个出现的
df_dedup = df.drop_duplicates(subset='bug_line', keep='first')

# 保留完整的 test_case 路径（修改点！）
result = df_dedup[['bug_line', 'test_case']]

# 保存到新的 CSV 文件
result.to_csv(output_file, index=False)

print(f"\n去重后数据行数: {len(result)}")
print(f"\n前5行预览:")
print(result.head())
print(f"\n结果已保存到: {output_file}")