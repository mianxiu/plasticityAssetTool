from peewee import SqliteDatabase,CharField,TimeField,BooleanField,Model
from enum import Enum
import tkinter as tk
from tkinter import filedialog


RECENT_PATH_DB = "recent_path.db"

class File(Enum):
    def run_command(command):
        match command:
            case "select_plasticity_file":
                return File.select_plasticity_file()

    def select_plasticity_file():
        root = tk.Tk()
        root.iconbitmap("plasticity asset tool.ico")
        root.withdraw()

        t = tk.Toplevel(root)
        t.iconbitmap("plasticity asset tool.ico")
        t.geometry("300x0")
        t.wm_title("plasticity asset tool")
        t.wm_attributes("-topmost", True)
        t.wm_attributes("-topmost", False)

        file_paths = filedialog.askopenfilenames(
            title="Select file",
            parent=t,
            filetypes=(
                ("All files", "*.plasticity *.plasticityassettooldb"),
                ("Plasticity files", "*.plasticity"),
                ("Plasticity Asset Tool DB", "*.plasticityassettooldb"),
            ),
        )

        if file_paths and len(file_paths) > 0:
            root.destroy()
            File.write_recent_db_file(file_paths)
            return file_paths

        root.destroy()

    def open_plasticity_file(file_path: str):
        pass

    def open_plasticity_asset_tool_db(file_path: str):
        pass

    def write_recent_db_file(file_paths: list):
        db = SqliteDatabase(f"{RECENT_PATH_DB}")
        db.connect()

        class FilePath(Model):
            name = CharField()
            path = CharField()
            last_read_date = TimeField()
            has_db = BooleanField()

            class Meta:
                database = db

        db.create_tables([FilePath])

        # 插入文件路径数据
        for file in file_paths:
            filename = os.path.basename(file)
            l = time.time()
            s = FilePath.create(
                name=f"{filename}", path=file, last_read_date=l, has_db=False
            )
            s.has_db = True
            s.save()

        for file_paths in FilePath.select():
            print(file_paths.path)
        # 关闭数据库连接
        db.close()
        pass

    def read_recent_db_file(file_paths: list):
        pass
