import usb_hid
from adafruit_hid.mouse import Mouse
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode
import usb_cdc
import supervisor
import time

# 初始化设备
mouse = Mouse(usb_hid.devices)
kbd = Keyboard(usb_hid.devices)
layout = KeyboardLayoutUS(kbd)
serial = usb_cdc.console

print("RP2350 Composite Ready (Mouse + Keyboard)")

buffer = ""

# 映射字符串按键名到 Keycode 对象
# 可以在这里添加更多需要的特殊键
KEY_MAP = {
    'shift': Keycode.SHIFT,
    'ctrl': Keycode.CONTROL,
    'alt': Keycode.ALT,
    'enter': Keycode.ENTER,
    'space': Keycode.SPACE,
    'backspace': Keycode.BACKSPACE,
    'tab': Keycode.TAB,
    'esc': Keycode.ESCAPE,
    'u': Keycode.U # 专门为了 Shift+U 准备
}

while True:
    if serial.in_waiting > 0:
        try:
            char = serial.read(1).decode("utf-8")
            if char == "\n":
                cmd = buffer.strip()
                buffer = ""
                parts = cmd.split(",")
                action = parts[0]

                # === 鼠标部分 ===
                if action == 'm' and len(parts) == 3:
                    mouse.move(x=int(parts[1]), y=int(parts[2]))
                elif action == 'c':
                    mouse.click(Mouse.LEFT_BUTTON)
                
                # === 键盘部分 ===
                # w,text -> 直接输入纯文本 (支持数字、字母、符号)
                elif action == 'w' and len(parts) >= 2:
                    text_to_write = ",".join(parts[1:]) # 防止文本里本来就有逗号
                    layout.write(text_to_write)
                
                # k,key_name -> 按下单键 (如 k,enter)
                elif action == 'k' and len(parts) == 2:
                    key_name = parts[1].lower()
                    if key_name in KEY_MAP:
                        kbd.send(KEY_MAP[key_name])
                
                # combo,shift,u -> 组合键 (按住前几个，点击最后一个，然后全松开)
                # 专门用于 shift+u 这种操作
                elif action == 'combo' and len(parts) >= 3:
                    modifiers = []
                    target_key = None
                    valid = True
                    
                    # 解析修饰键 (shift, ctrl...)
                    for k in parts[1:-1]:
                        if k in KEY_MAP: modifiers.append(KEY_MAP[k])
                        else: valid = False
                    
                    # 解析最后一个键
                    last = parts[-1]
                    if last in KEY_MAP: target_key = KEY_MAP[last]
                    elif len(last) == 1: 
                        # 如果是单个字符 'a'，尝试转为 keycode
                        # 这里简单处理，主要为了配合 shift+u
                        pass 
                    else: valid = False

                    if valid and target_key:
                        kbd.press(*modifiers)
                        kbd.press(target_key)
                        kbd.release_all()

            else:
                buffer += char
        except Exception as e:
            buffer = ""
            # print(e) # 调试用
