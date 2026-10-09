import csv
import re
import os

def clean_text(text):
    """清洗单个字段：去掉换行符、合并多余空格"""
    if isinstance(text, str):
        # 1. 替换换行符为空格
        text = text.replace('\r\n', ' ').replace('\n', ' ')
        # 2. 合并多个连续空格为一个
        text = re.sub(r'\s+', ' ', text)
        # 3. 去除首尾空格
        text = text.strip()
        return text
    return text

def clean_csv(input_file, output_file=None):
    """清洗 CSV 文件"""
    if output_file is None:
        # 自动生成输出文件名
        name, ext = os.path.splitext(input_file)
        output_file = f"{name}_cleaned{ext}"
    
    print(f"读取文件: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    print(f"共读取 {len(rows)} 条记录")
    
    # 清洗所有字段
    cleaned_rows = []
    for row in rows:
        cleaned_row = {}
        for key, value in row.items():
            cleaned_row[key] = clean_text(value)
        cleaned_rows.append(cleaned_row)
    
    # 写入新文件
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_rows)
    
    print(f"清洗完成！保存到: {output_file}")
    print(f"   共 {len(cleaned_rows)} 条记录")
    return output_file

if __name__ == "__main__":
    # 清洗你的 CSV 文件
    clean_csv("boss_jobs_cleaned.csv")