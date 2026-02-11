import time
import cv2
import numpy as np
import mss
import random
import sys
import serial
import ctypes
from ctypes import wintypes
import math

# ================= 配置区域 =================
TARGET_IMAGE_PATH = 'target.png'
MATCH_THRESHOLD = 0.8
TIMEOUT_SECONDS = 30
COM_PORT = 'COM6'  # 保持 COM6
BAUD_RATE = 115200 
INPUT_STRING = "1#Aa甘蓝" # 待输入的字符串
# ===========================================

SM_CXSCREEN = 0
SM_CYSCREEN = 1

def get_screen_resolution():
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(SM_CXSCREEN), user32.GetSystemMetrics(SM_CYSCREEN)

def get_current_mouse_pos():
    point = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y

try:
    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=0.1)
    print(f"[硬件] 已连接到 {COM_PORT}")
except Exception as e:
    print(f"[错误] 无法连接 RP2350: {e}")
    sys.exit(1)

# === 硬件指令发送函数 ===

def send_move(dx, dy):
    if dx == 0 and dy == 0: return
    ser.write(f"m,{int(dx)},{int(dy)}\n".encode('utf-8'))

def send_double_click():
    ser.write(b"c\n")
    time.sleep(random.uniform(0.08, 0.15))
    ser.write(b"c\n")

def send_key(key_name):
    """发送单个功能键，如 enter, space"""
    ser.write(f"k,{key_name}\n".encode('utf-8'))
    time.sleep(0.05)

def send_text(text):
    """发送纯ASCII文本"""
    if not text: return
    ser.write(f"w,{text}\n".encode('utf-8'))
    time.sleep(0.05 * len(text)) # 稍微等一下打字

def send_combo(mod, key):
    """发送组合键，如 combo,shift,u"""
    ser.write(f"combo,{mod},{key}\n".encode('utf-8'))
    time.sleep(0.1)

# === 核心：复杂混合输入逻辑 ===

def hardware_type_complex_string(content):
    """
    解析并输入混合字符串。
    规则：
    1. 中文：Shift+U -> Unicode Hex -> Space
    2. 字母(a-z, A-Z)：直接输入 -> Enter (确认字母上屏，关闭中文联想框)
    3. 数字/符号：直接输入
    """
    print(f" -> 开始输入: {content}")
    
    i = 0
    while i < len(content):
        char = content[i]
        
        # === 情况 1: 中文字符 ===
        if '\u4e00' <= char <= '\u9fff': 
            # 获取 Unicode 十六进制码 (去掉 '0x', 只要后面的)
            # 例如 '甘' -> 0x7518 -> '7518'
            hex_code = hex(ord(char))[2:] 
            print(f"    输入中文 '{char}' (Unicode: {hex_code})")
            
            # 1. 发送 Shift + U
            send_combo('shift', 'u')
            time.sleep(0.1)
            
            # 2. 输入 Hex 码 (小写)
            send_text(hex_code)
            time.sleep(0.1)
            
            # 3. 空格确认 (选中第一个字)
            send_key('space')
            time.sleep(0.2) # 中文上屏需要一点时间
            i += 1
            
        # === 情况 2: 字母 (需要 Enter 确认) ===
        elif ('a' <= char <= 'z') or ('A' <= char <= 'Z'):
            # 我们需要把连续的字母凑在一起一次性发，避免每个字母都敲回车
            temp_str = ""
            while i < len(content) and (('a' <= content[i] <= 'z') or ('A' <= content[i] <= 'Z')):
                temp_str += content[i]
                i += 1
            
            print(f"    输入字母串 '{temp_str}' + Enter")
            send_text(temp_str)
            time.sleep(0.1)
            send_key('enter') # 关闭输入法候选框
            time.sleep(0.1)
            
        # === 情况 3: 数字和符号 (直接输入) ===
        else:
            # 同样凑连续的数字符号一起发
            temp_str = ""
            # 只要不是中文且不是字母
            while i < len(content) and not ('\u4e00' <= content[i] <= '\u9fff') and not (('a' <= content[i] <= 'z') or ('A' <= content[i] <= 'Z')):
                temp_str += content[i]
                i += 1
            
            print(f"    输入符号/数字 '{temp_str}'")
            send_text(temp_str)
            time.sleep(0.1)
            # 数字符号通常不需要回车确认，直接上屏

# === 鼠标移动逻辑 (V3 稳定版) ===

def smooth_move_to(target_x, target_y):
    max_loops = 300 
    loop_count = 0
    while loop_count < max_loops:
        cur_x, cur_y = get_current_mouse_pos()
        diff_x = target_x - cur_x
        diff_y = target_y - cur_y
        if abs(diff_x) <= 3 and abs(diff_y) <= 3: break
        
        distance = math.sqrt(diff_x**2 + diff_y**2)
        if distance > 100: speed_factor = 0.15 
        elif distance > 20: speed_factor = 0.3
        else: speed_factor = 0.6
            
        move_x = int(diff_x * speed_factor)
        move_y = int(diff_y * speed_factor)
        
        max_step = 15
        move_x = max(-max_step, min(max_step, move_x))
        move_y = max(-max_step, min(max_step, move_y))
        
        if move_x == 0 and abs(diff_x) > 0: move_x = 1 if diff_x > 0 else -1
        if move_y == 0 and abs(diff_y) > 0: move_y = 1 if diff_y > 0 else -1
        
        send_move(move_x, move_y)
        time.sleep(0.015) 
        loop_count += 1
        
    cur_x, cur_y = get_current_mouse_pos()
    final_dx = target_x - cur_x
    final_dy = target_y - cur_y
    if abs(final_dx) > 0 or abs(final_dy) > 0:
        send_move(final_dx, final_dy)

def find_image_on_screen(template_path, threshold=0.8):
    try:
        template = cv2.imread(template_path)
        if template is None: return None
        template_h, template_w = template.shape[:2]
        
        with mss.mss() as sct:
            monitor = sct.monitors[1] 
            screenshot = np.array(sct.grab(monitor))
            screenshot_bgr = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            
            result = cv2.matchTemplate(screenshot_bgr, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= threshold:
                center_x = max_loc[0] + template_w // 2 + monitor["left"]
                center_y = max_loc[1] + template_h // 2 + monitor["top"]
                return center_x, center_y
            else:
                return None
    except: return None

def main_loop():
    print(f"\n[硬件模式 V4 - 键鼠一体] 启动。")
    print(f"待输入内容: {INPUT_STRING}")
    
    while True:
        print(f"\n[开始] 寻找目标...")
        start_time = time.time()
        found = False
        
        while (time.time() - start_time) < TIMEOUT_SECONDS:
            coords = find_image_on_screen(TARGET_IMAGE_PATH, MATCH_THRESHOLD)
            
            if coords:
                print(f"[成功] 找到图像! 坐标: {coords}")
                target_x, target_y = coords
                offset_x = random.randint(-3, 3)
                offset_y = random.randint(-3, 3)
                
                # 1. 移动
                smooth_move_to(target_x + offset_x, target_y + offset_y)
                
                # 2. 双击
                print(f"[动作] 硬件双击...")
                send_double_click()
                
                # 3. 等待焦点获取 (很重要！)
                # 双击后，输入框获取焦点可能需要几百毫秒
                time.sleep(1.0) 
                
                # 4. 开始打字
                print(f"[动作] 开始硬件输入...")
                hardware_type_complex_string(INPUT_STRING)
                
                found = True
                break
            
            time.sleep(0.5)
            sys.stdout.write(".")
            sys.stdout.flush()

        if not found:
            print(f"\n[超时]")
            while True:
                user_input = input("'r' 重试, 'c' 退出: ").strip().lower()
                if user_input == 'r': break 
                elif user_input == 'c': return 
        else:
            print("\n操作执行完毕。")
            user_input = input("回车继续，'c' 退出: ").strip().lower()
            if user_input == 'c': break

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt: pass
    finally:
        if 'ser' in globals() and ser.is_open: ser.close()
