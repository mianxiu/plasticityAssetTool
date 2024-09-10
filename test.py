import asyncio
import random

async def my_async_function(parameter):
    print(f"正在处理参数 {parameter}...")
    # 模拟异步操作随机等待时间
    await asyncio.sleep(random.uniform(1, 10))
    print(f"参数 {parameter} 处理完成")

# 待处理的参数列表
parameters = [1, 2, 3, 4, 5]

async def main():
    for param in parameters:
        # 异步执行函数
        await my_async_function(param)
        print("等待下一次循环...")

# 运行异步函数
asyncio.run(main())