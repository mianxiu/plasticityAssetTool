import json
import re
from enum import Enum

"""
"fov": 50, 
"translation": [4.9999999999999964, -4.999999999999997, 4.999999999999997], 
"rotation": [0.4247082002778669, 0.17591989660616117, 0.33985114297998736, 0.8204732385702832], 
"zoom": 0.8196762725940084 }, 
"target": [0, 0, 0], 
"focalOffset": [0, 0, 0], 
"constructionPlane": { "normal": [0, 0, 1], "translation": [0, 0, 1] }, "isXRay": true, "shading": { "type": "solid", "matcap": ".././img/ceramic_dark.exr" } }],
"""

class Plasticity_Object_Type(Enum):
    GROUP = "group",
    ITEM = "item",
    NAME = "name"
    EMPTY = "empty"
    pass


def get_node_tree(file_json_str:json):


    _file_json = json.loads(file_json_str)
    _nodes = _file_json["nodes"]
    _items = _file_json["items"]
    _groups = _file_json["groups"]
    
    global _index, _deep
    
    _index = 0
    _deep = 0
    
    def _loop_tree(index:int,group_handle,item_handle,empty_handle):
        global _index,_deep
        
        _groups_root = _groups[index]["children"]
        
        for root_index in _groups_root:

            _node = _nodes[root_index]
            _node_type = list(_node.keys())[0]
            _node_item_value = _node[_node_type]

            match _node_type:
                case "group":
                    print(_deep,f"root index {root_index}",_node)
                    # do something
                    
                    _deep += 1          
                    _index += 1
                    _loop_tree(_index,None,None,None)
                    
                case "item":
                    # do someting
                    print(_deep,f"root index {root_index}",_node,f"item {_node_item_value}",)
                
                case "empty":
                    print(_deep,_node)
       
        _deep -=1      


    _loop_tree(_index,None,None,None)

with open('test file\worker 2.plasticity', 'rb') as file:
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
    e = re.findall("JSON(.*}]})",d)
    # 使用正则表达式替换提取 JSON 数据

    #print(d)
    get_node_tree(file_json_str=e[0])
    
    with open('test file/output.json','w') as j:
        j.write(e[0])
        