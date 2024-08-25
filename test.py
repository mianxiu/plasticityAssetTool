import concurrent.futures

def square(n):
    return n**2

# 创建线程池
executor = concurrent.futures.ThreadPoolExecutor()

# 提交多个任务到线程池中
futures = {executor.submit(square, i): i for i in range(10)}

# 等待每个任务完成并即时获取结果
for future in concurrent.futures.as_completed(futures):
    result = future.result()
    print(f"Result for {futures[future]} : {result}")

# 关闭线程池
executor.shutdown()