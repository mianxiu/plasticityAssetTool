import psutil

# 定义要查找的进程名
process_name = "Plasticity.exe"

# 遍历当前所有进程
for process in psutil.process_iter(['pid', 'name']):
    if process.info['name'] == process_name:
        # 获取进程的打开文件列表
        open_files = process.open_files()
        
        print(f"Open files for process {process_name}:")
        for file in open_files:
            print(file.path)