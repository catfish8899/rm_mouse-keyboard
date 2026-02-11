import os
from pathlib import Path

def convert_txt_to_py():
    """将当前目录下所有 .txt 文件转换为 .py 文件（排除友军）"""
    
    # 友军名单（伙伴脚本的 .txt 形式，以防万一）
    friendly_scripts = {
        'py_to_txt.txt',  # 友军可能被误转的形式
        'txt_to_py.txt'   # 自身可能被误转的形式
    }
    
    current_dir = Path('.')
    count = 0
    
    for txt_file in current_dir.glob('*.txt'):
        # 检查是否为友军
        if txt_file.name in friendly_scripts:
            print(f"⏭️  跳过友军: {txt_file.name}")
            continue
        
        py_file = txt_file.with_suffix('.py')
        
        # 检查目标文件是否已存在
        if py_file.exists():
            print(f"⚠️  跳过（目标已存在）: {txt_file.name}")
            continue
        
        txt_file.rename(py_file)
        print(f"✅ 转换: {txt_file.name} -> {py_file.name}")
        count += 1
    
    print(f"\n🎉 完成！共转换 {count} 个文件")

if __name__ == '__main__':
    convert_txt_to_py()
