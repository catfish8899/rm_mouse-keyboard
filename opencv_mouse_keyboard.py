# -----------------------------------------------------------------------------------
# 脚本名称：opencv_mouse_keyboard.py (需修改后缀为 .py 运行)
# 运行环境：Windows 11 PC (Python 3.12)
# 对应文档：[说明书] -> 电脑端控制脚本
# -----------------------------------------------------------------------------------
# 【核心逻辑】
# 此脚本是整个系统的“大脑”。它负责：
# 1. 视觉感知：通过 OpenCV 截取屏幕，寻找目标图片的位置。
# 2. 路径规划：计算鼠标移动路径。
# 3. 指令下发：通过串口向 RP2350 发送硬件指令，指挥“机械手”行动。
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

# =========================================================================
# [1] 用户配置区域 (请对照说明书第18-19条修改)
# =========================================================================
TARGET_IMAGE_PATH = 'target.png'  # 必须与本脚本在同一目录下的目标截图文件
MATCH_THRESHOLD = 0.8             # 图像识别的严谨度 (0.8代表需要80%相似)
TIMEOUT_SECONDS = 30              # 寻找目标的耐心值（秒）
COM_PORT = 'COM5'                 # 【重要】请在设备管理器查看 RP2350 的实际端口号
BAUD_RATE = 115200                # 串口通信速率 (保持默认)
INPUT_STRING = "1#Aa甘蓝"         # 演示内容：包含数字、符号、英文、中文的混合字符串
# =========================================================================

# 屏幕参数常量
SM_CXSCREEN = 0
SM_CYSCREEN = 1

def get_current_mouse_pos():
    """获取当前鼠标在屏幕上的物理坐标"""
    point = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y

# =========================================================================
# [2] 建立硬件连接
# =========================================================================
# 尝试打通与 RP2350 的电话线 (串口)。如果失败，请检查 COM_PORT 是否填写正确。
try:
    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=0.1)
    print(f"[硬件连接] 成功连接至 {COM_PORT}。RP2350 已就绪。")
except Exception as e:
    print(f"[连接失败] 无法找到 RP2350，请检查设备管理器中的 COM 号: {e}")
    sys.exit(1)

# =========================================================================
# [3] 硬件指令协议封装
# =========================================================================
# 这些函数负责将 Python 的意图翻译成 code.py 能听懂的字符串协议 (如 "m,10,20")

def send_move(dx, dy):
    """发送鼠标相对移动指令"""
    if dx == 0 and dy == 0: return
    ser.write(f"m,{int(dx)},{int(dy)}\n".encode('utf-8'))

def send_double_click():
    """发送双击指令 (包含微小的随机间隔，模拟人类手速)"""
    ser.write(b"c\n")
    time.sleep(random.uniform(0.08, 0.15))
    ser.write(b"c\n")

def send_key(key_name):
    """发送功能键 (如 enter, space)"""
    ser.write(f"k,{key_name}\n".encode('utf-8'))
    time.sleep(0.05)

def send_text(text):
    """发送纯英文/数字文本 (直接敲击键盘)"""
    if not text: return
    ser.write(f"w,{text}\n".encode('utf-8'))
    time.sleep(0.05 * len(text)) 

def send_combo(mod, key):
    """发送组合键 (如 shift+u)"""
    ser.write(f"combo,{mod},{key}\n".encode('utf-8'))
    time.sleep(0.1)

# =========================================================================
# [4] 混合内容输入逻辑 (本案例的核心黑科技)
# =========================================================================
# 对应说明书“特色3”：解决办公软件拒绝复制粘贴的问题。
# 原理：利用小狼毫+雾凇拼音的 'U模式'，通过输入 Unicode 编码来“敲”出汉字。
# 这样任何软件都无法拒绝，因为它看起来就是键盘一个字一个字敲进去的。

def hardware_type_complex_string(content):
    print(f" -> [输入系统] 开始处理字符串: {content}")
    i = 0
    while i < len(content):
        char = content[i]
        
        # --- 分支 A: 处理中文字符 ---
        # 逻辑：获取汉字的 Unicode 码 -> 呼出输入法 U 模式 -> 输入编码 -> 空格上屏
        if '\u4e00' <= char <= '\u9fff': 
            hex_code = hex(ord(char))[2:] # 例如 '甘' -> '7518'
            print(f"    [中文] '{char}' -> Unicode: {hex_code}")
            
            send_combo('shift', 'u')      # 呼出雾凇拼音 U 模式
            time.sleep(0.1)
            send_text(hex_code)           # 输入十六进制码
            time.sleep(0.1)
            send_key('space')             # 空格确认上屏
            time.sleep(0.2)               # 中文上屏由于经过输入法，需要多一点缓冲时间
            i += 1
            
        # --- 分支 B: 处理英文字符 ---
        # 逻辑：识别连续的英文字符串 -> 一次性发送 -> 回车防止输入法粘连
        elif ('a' <= char <= 'z') or ('A' <= char <= 'Z'):
            temp_str = ""
            while i < len(content) and (('a' <= content[i] <= 'z') or ('A' <= content[i] <= 'Z')):
                temp_str += content[i]
                i += 1
            print(f"    [英文] '{temp_str}'")
            send_text(temp_str)
            time.sleep(0.1)
            send_key('enter') # 关键：关闭中文输入法的联想框，避免英文被吸入输入法
            time.sleep(0.1)
            
        # --- 分支 C: 处理数字和符号 ---
        # 逻辑：直接发送，无需特殊处理
        else:
            temp_str = ""
            while i < len(content) and not ('\u4e00' <= content[i] <= '\u9fff') and not (('a' <= content[i] <= 'z') or ('A' <= content[i] <= 'Z')):
                temp_str += content[i]
                i += 1
            print(f"    [符号] '{temp_str}'")
            send_text(temp_str)
            time.sleep(0.1)

# =========================================================================
# [5] 拟人化平滑移动算法
# =========================================================================
def smooth_move_to(target_x, target_y):
    """
    即使拥有硬件权限，为了避免过于生硬的瞬移吓到用户（或触发某些风控），
    我们使用算法让鼠标有一个加速-减速的拟人化移动过程。
    """
    max_loops = 300 
    loop_count = 0
    while loop_count < max_loops:
        cur_x, cur_y = get_current_mouse_pos()
        diff_x = target_x - cur_x
        diff_y = target_y - cur_y
        
        # 接近目标 3 像素内停止
        if abs(diff_x) <= 3 and abs(diff_y) <= 3: break
        
        distance = math.sqrt(diff_x**2 + diff_y**2)
        # 动态阻尼：距离越近，速度越慢
        if distance > 100: speed_factor = 0.15 
        elif distance > 20: speed_factor = 0.3
        else: speed_factor = 0.6
            
        move_x = int(diff_x * speed_factor)
        move_y = int(diff_y * speed_factor)
        
        # 限制单步最大跨度，防止甩飞
        max_step = 15
        move_x = max(-max_step, min(max_step, move_x))
        move_y = max(-max_step, min(max_step, move_y))
        
        # 防止死锁微调
        if move_x == 0 and abs(diff_x) > 0: move_x = 1 if diff_x > 0 else -1
        if move_y == 0 and abs(diff_y) > 0: move_y = 1 if diff_y > 0 else -1
        
        send_move(move_x, move_y)
        time.sleep(0.015) 
        loop_count += 1
        
    # 最终微调修正
    cur_x, cur_y = get_current_mouse_pos()
    final_dx = target_x - cur_x
    final_dy = target_y - cur_y
    if abs(final_dx) > 0 or abs(final_dy) > 0:
        send_move(final_dx, final_dy)

def find_image_on_screen(template_path, threshold=0.8):
    """使用 OpenCV 进行屏幕找图"""
    try:
        template = cv2.imread(template_path)
        if template is None: return None
        template_h, template_w = template.shape[:2]
        
        with mss.mss() as sct:
            monitor = sct.monitors[1] # 主显示器
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
# [6] 主程序流程
# =========================================================================
def main_loop():
    print(f"\n[系统启动] 自动化脚本运行中...")
    print(f"待输入内容: {INPUT_STRING}")
    
    while True:
        print(f"\n[流程] 正在屏幕上寻找目标图片 '{TARGET_IMAGE_PATH}' ...")
        start_time = time.time()
        found = False
        
        # 循环搜索直到超时
        while (time.time() - start_time) < TIMEOUT_SECONDS:
            coords = find_image_on_screen(TARGET_IMAGE_PATH, MATCH_THRESHOLD)
            
            if coords:
                print(f"[视觉] 发现目标! 坐标: {coords}")
                target_x, target_y = coords
                # 添加±3像素的随机偏移，模拟真实点击误差
                offset_x = random.randint(-3, 3)
                offset_y = random.randint(-3, 3)
                
                # 1. 移动鼠标到目标
                smooth_move_to(target_x + offset_x, target_y + offset_y)
                
                # 2. 执行物理双击
                print(f"[动作] 执行硬件左键双击...")
                send_double_click()
                
                # 3. 等待输入框激活 (关键! 必须给软件反应时间)
                time.sleep(1.0) 
                
                # 4. 执行防屏蔽输入
                print(f"[动作] 执行硬件文本输入...")
                hardware_type_complex_string(INPUT_STRING)
                
                found = True
                break
            
            time.sleep(0.5)
            sys.stdout.write(".")
            sys.stdout.flush()

        if not found:
            print(f"\n[超时] 未找到目标。请检查屏幕上是否有目标图片，或调整 MATCH_THRESHOLD。")
            choice = input("输入 'r' 重试, 'c' 退出: ").strip().lower()
            if choice == 'c': return 
        else:
            print("\n[完成] 自动化流程执行完毕。")
            choice = input("按回车再次执行，输入 'c' 退出: ").strip().lower()
            if choice == 'c': break

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt: pass
    finally:
        if 'ser' in globals() and ser.is_open: ser.close()
