import os
from pathlib import Path

def convert_py_to_txt():
    """将当前目录下所有 .py 文件转换为 .txt 文件（排除友军）"""
    
    # 友军名单（自身 + 伙伴脚本）
    friendly_scripts = {
        os.path.basename(__file__),  # 自身
        'txt_to_py.py'               # 友军
    }
    
    current_dir = Path('.')
    count = 0
    
    for py_file in current_dir.glob('*.py'):
        # 检查是否为友军
        if py_file.name in friendly_scripts:
            print(f"⏭️  跳过友军: {py_file.name}")
            continue
        
        txt_file = py_file.with_suffix('.txt')
        py_file.rename(txt_file)
        print(f"✅ 转换: {py_file.name} -> {txt_file.name}")
        count += 1
    
    print(f"\n🎉 完成！共转换 {count} 个文件")

if __name__ == '__main__':
    convert_py_to_txt()
