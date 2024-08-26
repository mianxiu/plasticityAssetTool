import concurrent.futures
import time

def worker(seconds):
    time.sleep(seconds)
    return f"Task completed in {seconds} seconds"

if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # 提交多个任务给线程池
        tasks = [executor.submit(worker, i) for i in range(1, 6)]

        # 使用as_completed迭代已完成的任务结果
        for future in concurrent.futures.as_completed(tasks):
            result = future.result()
            print(result)

    print("All tasks completed")