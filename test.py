# import asyncio
# import random

# async def my_async_function(parameter):
#     print(f"正在处理参数 {parameter}...")
#     # 模拟异步操作随机等待时间
#     await asyncio.sleep(random.uniform(1, 10))
#     print(f"参数 {parameter} 处理完成")

# # 待处理的参数列表
# parameters = [1, 2, 3, 4, 5]

# async def main():
#     for param in parameters:
#         # 异步执行函数
#         await my_async_function(param)
#         print("等待下一次循环...")

# # 运行异步函数
# asyncio.run(main())
from websockets.sync.client import connect
import asyncio
import program_info
import cdp_method
import threading
import time
import win32gui
import json
from My_Modules import file_handle

# def load_program_info_tmp():
#todo 开始是hwnd倒序，4为第4个正确，前面倒序 会重复3次
def update_program_info_cache():
    p = program_info.PLASTICITY_INSTANCE_INFO 
    if p :
        print("in other py-update")
        # for all client
        # with connect("ws://127.0.0.1:15150/websocket") as ws:
        #     ws.send(f"Program_Info_Send:{p}")
        #     msg = ws.recv()
        #     print(msg)
        #     ws.close()

        
        #当成一个客户端，向服务器发送指有新info,服务器再推送全部
        # file_handle.File.write_program_info_cache(new_infos=p)

        print(p)
        for _ in p:
            _ws_url = _.ws_url
            _hwnd = _.hwnd   
            res =cdp_method.get_filename_from_ws_url(_ws_url)
            # print(res)
            if res is not None:
                # print(_.toDict())
                # print(res)
                
                win32gui.SetWindowText(_hwnd,res)
                pass
            

            
                
def remove_program_info_cache():
    print("in other py-remove")
    # p = program_info.PLASTICITY_INSTANCE_INFO
    
    # file_handle.File.remove_program_info_cache(p)
    
    


if __name__ == "__main__":
        
        try:  
            print("------load_cache------")
            
            print("------wait-------")
            
            program_info.process_listener_callback(has_new_callback=update_program_info_cache,has_remove_callback=remove_program_info_cache)
            program_info.run_process_listener()

            pass
        except KeyboardInterrupt:
            print("exit")
            
    