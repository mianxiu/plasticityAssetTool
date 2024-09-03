import win32gui
import win32process



def get_pid_from_hwnd(hwnd):
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    return pid

def get_process_name(pid):
    import psutil
    process = psutil.Process(pid)
    return process.name()

def get_hwnd_from_process_name(process_name):
    hwnd_list = []

    def callback(hwnd, hwnd_list):
        if win32gui.IsWindowVisible(hwnd):
            try:
                pid = get_pid_from_hwnd(hwnd)
                if get_process_name(pid) == process_name:
                    hwnd_list.append((hwnd, pid))
            except psutil.NoSuchProcess:
                pass
        return True

    win32gui.EnumWindows(callback, hwnd_list)

    return hwnd_list

# 要查找的进程名
process_name = "Plasticity.exe"

# 获取包含进程名的窗口句柄和进程ID列表
hwnd_pid_list = get_hwnd_from_process_name(process_name)

# 打印窗口句柄和进程ID
for hwnd, pid in hwnd_pid_list:
    print(f"进程名: {process_name}, 窗口句柄: {hwnd}, 进程ID: {pid}")
    
    win32gui.SetWindowText(hwnd, str(hwnd))
    #ws url 倒序，和hwnd正序对应