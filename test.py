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

import getprograminfo
import threading
import time

def cc():
    print("in other py")
    print(getprograminfo.PLASTICITY_INSTANCE_INFO)
                

if __name__ == "__main__":

        try:  
            
            # t = threading.Thread(target=getprograminfo.run_process_listener)
            # # t.daemon = True
            # t.start()

            print("------wait-------")
            getprograminfo.process_listener_callback(callback=cc)
            getprograminfo.run_process_listener()
        
            # for _ in range(100):
            #     time.sleep(0.2)
            #     print(getprograminfo._PLASTICITY_INSTANCE_INFO)
            pass
        except KeyboardInterrupt:
            print("exit")
            
    