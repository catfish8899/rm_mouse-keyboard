# RP2350 硬件自动化执行端固件
# 对应说明书：[说明书]
# 功能：将开发板伪装成纯硬件键鼠，接收来自电脑串口的文本指令并执行物理操作
# -----------------------------------------------------------------------------------

import usb_hid
from adafruit_hid.mouse import Mouse
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode
import usb_cdc
import supervisor
import time

# [初始化硬件对象]
# 这里的 mouse 和 kbd 就是 Windows 设备管理器里看到的“硬件设备”
# 它们的操作权限极高，属于物理层面的输入
mouse = Mouse(usb_hid.devices)
kbd = Keyboard(usb_hid.devices)
layout = KeyboardLayoutUS(kbd)
serial = usb_cdc.console  # 获取串口对象，用于监听电脑发来的指令

print("RP2350 Composite Ready (Mouse + Keyboard) - 等待指令中...")

buffer = ""

# [按键映射表]
# 将字符串指令映射到 CircuitPython 的按键对象
# 如果需要更多特殊键（如 F1-F12），可以在此处添加
KEY_MAP = {
    'shift': Keycode.SHIFT,
    'ctrl': Keycode.CONTROL,
    'alt': Keycode.ALT,
    'enter': Keycode.ENTER,
    'space': Keycode.SPACE,
    'backspace': Keycode.BACKSPACE,
    'tab': Keycode.TAB,
    'esc': Keycode.ESCAPE,
    'u': Keycode.U # 专门为了配合说明书中提到的“Unicode输入法”准备（Shift+U）
}

# [主循环]
# 这是一个死循环，开发板会一直在这里监听串口数据
while True:
    if serial.in_waiting > 0:
        try:
            # 逐字节读取串口数据，直到遇到换行符 '\n' 才算一条完整指令
            char = serial.read(1).decode("utf-8")
            if char == "\n":
                cmd = buffer.strip()
                buffer = ""
                parts = cmd.split(",") # 指令协议规定用逗号分隔，例如：m,100,200
                action = parts[0]

                # -----------------------------------------------------------
                # 协议分支 A：鼠标操作
                # -----------------------------------------------------------
                if action == 'm' and len(parts) == 3:
                    # 指令格式：m,x,y -> 移动鼠标相对距离
                    mouse.move(x=int(parts[1]), y=int(parts[2]))
                elif action == 'c':
                    # 指令格式：c -> 鼠标左键点击一次
                    mouse.click(Mouse.LEFT_BUTTON)
                
                # -----------------------------------------------------------
                # 协议分支 B：键盘操作
                # -----------------------------------------------------------
                # 指令格式：w,text -> 直接输入纯ASCII文本
                # 用于输入数字、英文符号等不需要输入法处理的内容
                elif action == 'w' and len(parts) >= 2:
                    text_to_write = ",".join(parts[1:]) # 重新拼接，防止文本内容本身包含逗号
                    layout.write(text_to_write)
                
                # 指令格式：k,key_name -> 按下单个功能键
                # 例如：k,enter (回车), k,space (空格)
                elif action == 'k' and len(parts) == 2:
                    key_name = parts[1].lower()
                    if key_name in KEY_MAP:
                        kbd.send(KEY_MAP[key_name])
                
                # 指令格式：combo,modifier,key -> 组合键操作
                # 这是实现“说明书”中特色功能 [3] 的核心：
                # 通过发送 combo,shift,u 呼出雾凇拼音的 Unicode 输入框
                elif action == 'combo' and len(parts) >= 3:
                    modifiers = []
                    target_key = None
                    valid = True
                    
                    # 1. 解析修饰键 (shift, ctrl...)
                    for k in parts[1:-1]:
                        if k in KEY_MAP: modifiers.append(KEY_MAP[k])
                        else: valid = False
                    
                    # 2. 解析最后一个主键
                    last = parts[-1]
                    if last in KEY_MAP: target_key = KEY_MAP[last]
                    elif len(last) == 1: 
                        # 简单的容错处理
                        pass 
                    else: valid = False

                    # 3. 执行组合键：按下修饰键 -> 按下主键 -> 全部松开
                    if valid and target_key:
                        kbd.press(*modifiers)
                        kbd.press(target_key)
                        kbd.release_all()

            else:
                buffer += char
        except Exception as e:
            buffer = ""
            # print(e) # 调试时可开启，生产环境建议关闭以免干扰通信
