import win32clipboard
import win32con
import ctypes
import pickle
import io

PLASTICITY_CUSTOM_FORMAT_NAME = "application/vnd.plasticity.items"

# 指定要保存到的文件路径
file_path = "./test file/clipboard_binary_data.bin"

def get_plasticity_clipboard_data(path:str):
    
    RegisterClipboardFormat = ctypes.windll.user32.RegisterClipboardFormatA
    format_id = RegisterClipboardFormat(PLASTICITY_CUSTOM_FORMAT_NAME.encode("utf-8"))

    print(f"Registered custom clipboard format '{PLASTICITY_CUSTOM_FORMAT_NAME}' with ID: {format_id}")

    win32clipboard.OpenClipboard()
    try:
        # 尝试获取剪贴板数据
        clipboard_data = win32clipboard.GetClipboardData(format_id)

        with open(path, 'wb') as file:
            file.write(clipboard_data)
            
        print(f"剪贴板数据已保存为二进制文件: {path}")
    except Exception as e:
        print("无法获取剪贴板数据或数据无法保存为二进制格式")

    # 关闭剪贴板
    win32clipboard.CloseClipboard()
    


def set_plasticity_clipboard_data(path:str):
    
    RegisterClipboardFormat = ctypes.windll.user32.RegisterClipboardFormatA
    format_id = RegisterClipboardFormat(PLASTICITY_CUSTOM_FORMAT_NAME.encode("utf-8"))

    print(f"Registered custom clipboard format '{PLASTICITY_CUSTOM_FORMAT_NAME}' with ID: {format_id}")

    # 打开剪贴板
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    
    try:
        with open(path, 'rb') as f:
            clipboard_data = f.read()
        
        buffer = io.BytesIO()
        buffer.write(clipboard_data)
        win32clipboard.SetClipboardData(format_id,buffer.getvalue())
    except Exception as e:
        print("无法设置剪贴板内容")

    # 关闭剪贴板
    win32clipboard.CloseClipboard()

    
set_plasticity_clipboard_data(file_path)