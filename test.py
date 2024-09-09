import wmi
import threading
import pythoncom



def process_creation_listener():
    try:
        print("----wmi listener----")
        pythoncom.CoInitialize()
        c = wmi.WMI()
        process_watcher = c.Win32_Process.watch_for("creation",name="Plasticity.exe")
        while True:
            new_process = process_watcher()
            print("进程创建：", new_process.Caption)
    except KeyboardInterrupt:
        print("捕捉到 Ctrl + C，退出监听循环")

# process_creation_listener()

t = threading.Thread(target=process_creation_listener)
t.daemon = True
t.start()
while t.is_alive():
    t.join(timeout=1)