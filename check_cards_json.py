#!/usr/bin/env python3
"""
查看 CrystMiku/PokemonTCG-Data-Raw 仓库的 cards.json 文件格式
只下载前 10KB 数据来分析结构
"""

import requests
import json
import sys

url = "https://raw.githubusercontent.com/CrystMiku/PokemonTCG-Data-Raw/main/cards.json"

print(f"正在下载 {url} 的前 10KB 数据...")

try:
    # 使用 stream 模式只下载前 10KB
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()
    
    # 只读取前 10KB
    content = b""
    for chunk in response.iter_content(chunk_size=1024):
        content += chunk
        if len(content) >= 10240:  # 10KB
            break
    
    print(f"已下载 {len(content)} 字节")
    
    # 尝试解析 JSON（可能需要修复不完整的 JSON）
    try:
        # 如果内容以 '[' 开头，尝试找到最后一个完整的 ']'
        if content.startswith(b'['):
            # 找到最后一个完整的对象
            text = content.decode('utf-8')
            # 尝试解析
            data = json.loads(text + '}]')  # 尝试补全
        else:
            text = content.decode('utf-8')
            data = json.loads(text)
        
        print(f"\n数据格式: {type(data)}")
        if isinstance(data, list):
            print(f"卡牌数量（部分）: {len(data)}")
            if len(data) > 0:
                print(f"\n第一张卡牌数据:")
                print(json.dumps(data[0], ensure_ascii=False, indent=2))
    except json.JSONDecodeError as e:
        print(f"JSON 解析错误: {e}")
        print(f"\n原始内容（前 500 字符）:")
        print(content.decode('utf-8')[:500])
        
except Exception as e:
    print(f"错误: {e}")
    sys.exit(1)
