def select_plasticity_file():
    import tkinter as tk
    from tkinter import filedialog

    # 创建主窗口
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    root.iconbitmap("plasticity asset tool.ico")

    # 显示文件选择对话框
    file_path = filedialog.askopenfilenames(title="Select file", filetypes=(
        ("All files", "*.plasticity *.plasticityassettooldb") ,("Plasticity files", "*.plasticity"),("Plasticity Asset Tool DB", "*.plasticityassettooldb")))

    if file_path:
        print("选择的文件路径为:", file_path)
        return file_path

    else:
        print("未选择任何文件")

    # 关闭主窗口
    root.destroy()

print(select_plasticity_file())