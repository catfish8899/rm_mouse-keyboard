# PC端控制脚本 - 自动化逻辑“大脑”
# 对应说明书：[说明书]
# 功能：图像识别定位 -> 计算路径 -> 通过串口发送硬件指令给 RP2350
# -----------------------------------------------------------------------------------

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

# ================= 用户配置区域 =================
# 请根据说明书第18-19条调整以下参数
TARGET_IMAGE_PATH = 'target.png'  # 你的目标截图文件名（需放在同目录下）
MATCH_THRESHOLD = 0.8             # 图像匹配相似度 (0.1 - 1.0，越低越容易误判)
TIMEOUT_SECONDS = 30              # 搜索目标的超时时间（秒）
COM_PORT = 'COM5'                 # 极其重要：请在设备管理器确认 RP2350 的端口号
BAUD_RATE = 115200                # 串口通信速率，通常保持默认即可
INPUT_STRING = "1#Aa甘蓝"         # 演示用的混合字符串（含中文、符号、英文）
# ===============================================

# [屏幕参数常量]
SM_CXSCREEN = 0
SM_CYSCREEN = 1

def get_screen_resolution():
    """获取当前屏幕分辨率，用于坐标计算"""
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(SM_CXSCREEN), user32.GetSystemMetrics(SM_CYSCREEN)

def get_current_mouse_pos():
    """获取当前鼠标的物理坐标"""
    point = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y

# [建立硬件连接]
# 尝试连接 RP2350 开发板，就像拨通了一个电话
try:
    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=0.1)
    print(f"[硬件] 已连接到 {COM_PORT} - 通信管道建立成功")
except Exception as e:
    print(f"[错误] 无法连接 RP2350，请检查 COM 号是否正确: {e}")
    sys.exit(1)

# =========================================================================
# 硬件指令发送函数集
# 这些函数负责将 Python 的意图翻译成 code.py 能听懂的字符串协议
# =========================================================================

def send_move(dx, dy):
    """发送移动指令 m,x,y"""
    if dx == 0 and dy == 0: return
    ser.write(f"m,{int(dx)},{int(dy)}\n".encode('utf-8'))

def send_double_click():
    """发送双击指令，中间加入微小的随机延迟模拟人类手速"""
    ser.write(b"c\n")
    time.sleep(random.uniform(0.08, 0.15))
    ser.write(b"c\n")

def send_key(key_name):
    """发送单个功能键，如 enter, space"""
    ser.write(f"k,{key_name}\n".encode('utf-8'))
    time.sleep(0.05)

def send_text(text):
    """发送纯ASCII文本（不支持中文），直接由键盘敲击输出"""
    if not text: return
    ser.write(f"w,{text}\n".encode('utf-8'))
    time.sleep(0.05 * len(text)) # 根据文本长度动态等待打字完成

def send_combo(mod, key):
    """发送组合键，如 combo,shift,u"""
    ser.write(f"combo,{mod},{key}\n".encode('utf-8'))
    time.sleep(0.1)

# =========================================================================
# [核心功能] 复杂混合输入逻辑
# 对应说明书“特色3”：解决办公软件拒绝复制粘贴的问题
# =========================================================================

def hardware_type_complex_string(content):
    """
    原理：利用小狼毫+雾凇拼音的 'U模式' 输入 Unicode 编码。
    这就好比我们不是在“粘贴”文字，而是在用键盘一个字一个字地“敲”出编码，
    任何软件都无法拒绝这种硬件级别的键盘敲击。
    """
    print(f" -> [输入系统] 开始处理字符串: {content}")
    
    i = 0
    while i < len(content):
        char = content[i]
        
        # === 情况 A: 处理中文字符 ===
        if '\u4e00' <= char <= '\u9fff': 
            # 1. 将汉字转换为 Unicode 十六进制码 (例如 '甘' -> '7518')
            hex_code = hex(ord(char))[2:] 
            print(f"    [中文] '{char}' -> Unicode: {hex_code}")
            
            # 2. 发送组合键 Shift + U (呼出输入法 Unicode 模式)
            send_combo('shift', 'u')
            time.sleep(0.1)
            
            # 3. 输入 Hex 码
            send_text(hex_code)
            time.sleep(0.1)
            
            # 4. 按空格确认上屏 (选中第一个候选字)
            send_key('space')
            time.sleep(0.2) # 中文上屏通常比英文慢，多给点时间
            i += 1
            
        # === 情况 B: 处理英文字母 ===
        elif ('a' <= char <= 'z') or ('A' <= char <= 'Z'):
            # 策略：将连续的字母收集起来一次性发送，提高效率
            temp_str = ""
            while i < len(content) and (('a' <= content[i] <= 'z') or ('A' <= content[i] <= 'Z')):
                temp_str += content[i]
                i += 1
            
            print(f"    [英文] '{temp_str}' + Enter确认")
            send_text(temp_str)
            time.sleep(0.1)
            # 发送回车是为了关闭中文输入法的联想框，防止英文粘连
            send_key('enter') 
            time.sleep(0.1)
            
        # === 情况 C: 处理数字和符号 ===
        else:
            # 策略：同样收集连续的数字符号
            temp_str = ""
            while i < len(content) and not ('\u4e00' <= content[i] <= '\u9fff') and not (('a' <= content[i] <= 'z') or ('A' <= content[i] <= 'Z')):
                temp_str += content[i]
                i += 1
            
            print(f"    [符号] '{temp_str}'")
            send_text(temp_str)
            time.sleep(0.1)
            # 数字符号通常不需要回车确认，直接上屏即可

# =========================================================================
# 鼠标拟人化移动算法 (V3版)
# =========================================================================

def smooth_move_to(target_x, target_y):
    """
    虽然 RP2350 是硬件鼠标，Windows 无条件信任，
    但为了视觉上的舒适和模拟人工操作，我们依然使用平滑移动算法，
    而不是瞬间跳跃到目标点。
    """
    max_loops = 300 
    loop_count = 0
    while loop_count < max_loops:
        cur_x, cur_y = get_current_mouse_pos()
        diff_x = target_x - cur_x
        diff_y = target_y - cur_y
        
        # 到达目标附近 3 像素范围内停止
        if abs(diff_x) <= 3 and abs(diff_y) <= 3: break
        
        distance = math.sqrt(diff_x**2 + diff_y**2)
        
        # 距离越远速度越快，距离越近速度越慢（阻尼效果）
        if distance > 100: speed_factor = 0.15 
        elif distance > 20: speed_factor = 0.3
        else: speed_factor = 0.6
            
        move_x = int(diff_x * speed_factor)
        move_y = int(diff_y * speed_factor)
        
        # 限制单次最大移动步长，防止甩飞
        max_step = 15
        move_x = max(-max_step, min(max_step, move_x))
        move_y = max(-max_step, min(max_step, move_y))
        
        # 防止因浮点数取整导致的死锁（永远不动）
        if move_x == 0 and abs(diff_x) > 0: move_x = 1 if diff_x > 0 else -1
        if move_y == 0 and abs(diff_y) > 0: move_y = 1 if diff_y > 0 else -1
        
        send_move(move_x, move_y)
        time.sleep(0.015) 
        loop_count += 1
        
    # 最后进行一次微小的修正
    cur_x, cur_y = get_current_mouse_pos()
    final_dx = target_x - cur_x
    final_dy = target_y - cur_y
    if abs(final_dx) > 0 or abs(final_dy) > 0:
        send_move(final_dx, final_dy)

def find_image_on_screen(template_path, threshold=0.8):
    """使用 OpenCV 在屏幕截图上寻找目标图片"""
    try:
        template = cv2.imread(template_path)
        if template is None: return None
        template_h, template_w = template.shape[:2]
        
        with mss.mss() as sct:
            monitor = sct.monitors[1] # 获取主显示器
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

# =========================================================================
# 主程序逻辑
# =========================================================================

def main_loop():
    print(f"\n[硬件模式 V4 - 键鼠一体] 启动。")
    print(f"待输入内容: {INPUT_STRING}")
    
    while True:
        print(f"\n[流程] 正在寻找目标图片 '{TARGET_IMAGE_PATH}' ...")
        start_time = time.time()
        found = False
        
        # 在超时时间内循环搜索
        while (time.time() - start_time) < TIMEOUT_SECONDS:
            coords = find_image_on_screen(TARGET_IMAGE_PATH, MATCH_THRESHOLD)
            
            if coords:
                print(f"[视觉] 找到目标! 坐标: {coords}")
                target_x, target_y = coords
                # 增加一点随机偏移，模拟真实点击
                offset_x = random.randint(-3, 3)
                offset_y = random.randint(-3, 3)
                
                # 1. 执行移动
                smooth_move_to(target_x + offset_x, target_y + offset_y)
                
                # 2. 执行双击
                print(f"[动作] 硬件左键双击...")
                send_double_click()
                
                # 3. 等待焦点获取 (关键步骤！)
                # 双击后，软件的输入框需要时间来响应并获得光标焦点
                time.sleep(1.0) 
                
                # 4. 执行输入
                print(f"[动作] 开始硬件输入文本...")
                hardware_type_complex_string(INPUT_STRING)
                
                found = True
                break
            
            time.sleep(0.5)
            sys.stdout.write(".")
            sys.stdout.flush()

        if not found:
            print(f"\n[超时] 未找到目标图片。")
            while True:
                user_input = input("'r' 重试, 'c' 退出: ").strip().lower()
                if user_input == 'r': break 
                elif user_input == 'c': return 
        else:
            print("\n[完成] 操作执行完毕。")
            user_input = input("按回车继续循环，输入 'c' 退出: ").strip().lower()
            if user_input == 'c': break

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt: pass
    finally:
        if 'ser' in globals() and ser.is_open: ser.close()
