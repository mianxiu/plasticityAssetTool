import json
import re
with open('test file\worker.plasticity', 'rb') as file:
    # start_sequence = b'4A534F4E7B'
    # end_sequence = b'F858000042'

    data = b''  # 用于存储读取的数据
    found_start_sequence = False

    while True:
        chunk = file.read(8192)  # 每次读取 8192 字节的数据
        if not chunk:  # 如果读取到文件末尾
            break

        # if not found_start_sequence:
        #     # 查找起始序列
        #     start_index = chunk.find(start_sequence)
        #     if start_index != -1:
        #         chunk = chunk[start_index + len(start_sequence):]
        #         found_start_sequence = True

        # end_index = chunk.find(end_sequence)
        # if end_index != -1:
        #     # 找到结束序列，截取数据并退出循环
        #     data += chunk[:end_index]
        #     break

        data += chunk  # 将读取的数据添加到存储区
        
    d = data.decode("utf-8",errors="ignore")
    e = re.findall("JSON(.*)X\x00\x00BIN\x00PS\x00\x00\x003: ",d)
    # 使用正则表达式替换提取 JSON 数据

    print(e[0])
    
    with open('test file/output.json','w') as j:
        j.write(e[0])
        