# -----------------------------------------------------------------------------------
# 脚本名称：code.py
# 适用硬件：树莓派 RP2350 (Pico 2)
# 对应文档：[说明书] -> 硬件级键鼠自动化案例
# -----------------------------------------------------------------------------------
# 【核心原理】
# 此脚本运行在开发板上，它的作用是将 RP2350 伪装成一个纯物理的“USB复合设备（键盘+鼠标）”。
# Windows 系统会认为这是一个真实的人类在操作，因此拥有极高的硬件级权限。
# 它充当“执行手”的角色，被动接收来自电脑串口的文本指令，并将其翻译为物理按键/鼠标动作。
# -----------------------------------------------------------------------------------

import usb_hid
from adafruit_hid.mouse import Mouse
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode
import usb_cdc
import supervisor
import time

# =========================================================================
# [1] 硬件对象初始化 (设备伪装)
# =========================================================================
# 在此处实例化后，Windows 设备管理器中就会出现“HID Keyboard Device”和“HID-compliant mouse”。
# 这里的 serial 对象通过 USB 线建立虚拟串口，用于监听电脑发来的指令。
mouse = Mouse(usb_hid.devices)
kbd = Keyboard(usb_hid.devices)
layout = KeyboardLayoutUS(kbd)
serial = usb_cdc.console

print("RP2350 硬件自动化执行端已就绪 - 正在监听串口指令...")

buffer = ""

# =========================================================================
# [2] 按键映射表
# =========================================================================
# 将串口收到的字符串指令（如 "enter"）映射为 CircuitPython 的物理按键对象。
KEY_MAP = {
    'shift': Keycode.SHIFT,
    'ctrl': Keycode.CONTROL,
    'alt': Keycode.ALT,
    'enter': Keycode.ENTER,
    'space': Keycode.SPACE,
    'backspace': Keycode.BACKSPACE,
    'tab': Keycode.TAB,
    'esc': Keycode.ESCAPE,
    # 下面这个 'u' 键非常关键，它是说明书中提到的“Unicode输入模式”的触发键
    'u': Keycode.U 
}

# =========================================================================
# [3] 主循环 (指令监听与执行)
# =========================================================================
while True:
    # 检查串口是否有数据流入
    if serial.in_waiting > 0:
        try:
            # 逐字节读取并拼凑指令，以换行符 '\n' 作为指令结束标志
            char = serial.read(1).decode("utf-8")
            if char == "\n":
                cmd = buffer.strip()
                buffer = ""
                # 通信协议：指令类型,参数1,参数2... (例如: m,100,200)
                parts = cmd.split(",") 
                action = parts[0]

                # --- 分支 A：鼠标物理操作 ---
                if action == 'm' and len(parts) == 3:
                    # 指令: m,x,y -> 鼠标相对移动 (用于移动到 OpenCV 识别到的坐标)
                    mouse.move(x=int(parts[1]), y=int(parts[2]))
                elif action == 'c':
                    # 指令: c -> 鼠标左键点击
                    mouse.click(Mouse.LEFT_BUTTON)
                
                # --- 分支 B：键盘文本输出 ---
                # 指令: w,text -> 快速输入纯 ASCII 字符 (如英文、数字、标点)
                # 注意：此模式无法直接输入中文，中文需要走下方的 combo 模式
                elif action == 'w' and len(parts) >= 2:
                    text_to_write = ",".join(parts[1:]) # 修复内容中包含逗号的情况
                    layout.write(text_to_write)
                
                # --- 分支 C：单个功能键 ---
                # 指令: k,key_name -> 按下并松开某个功能键 (如回车、空格)
                elif action == 'k' and len(parts) == 2:
                    key_name = parts[1].lower()
                    if key_name in KEY_MAP:
                        kbd.send(KEY_MAP[key_name])
                
                # --- 分支 D：组合键操作 (中文输入核心) ---
                # 指令: combo,modifier,key -> 组合按键
                # 对应说明书特色功能：通过发送 "combo,shift,u" 呼出雾凇拼音的 Unicode 输入框
                # 这是实现“无剪贴板依赖”输入中文的底层硬件基础
                elif action == 'combo' and len(parts) >= 3:
                    modifiers = []
                    target_key = None
                    valid = True
                    
                    # 解析修饰键 (如 shift)
                    for k in parts[1:-1]:
                        if k in KEY_MAP: modifiers.append(KEY_MAP[k])
                        else: valid = False
                    
                    # 解析主键 (如 u)
                    last = parts[-1]
                    if last in KEY_MAP: target_key = KEY_MAP[last]
                    elif len(last) == 1: pass 
                    else: valid = False

                    # 执行物理按键序列：按下修饰键 -> 按下主键 -> 全部释放
                    if valid and target_key:
                        kbd.press(*modifiers)
                        kbd.press(target_key)
                        kbd.release_all()

            else:
                buffer += char
        except Exception:
            # 发生通信错误时清空缓冲区，防止错误指令堆积
            buffer = ""
