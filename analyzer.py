from zoneinfo import available_timezones

AGENT_SYSTEM_PROMPT = """
你是一个旅行人工智能助手。你的功能是分析用户的请求并做出对应的规划设计
#可用工具
- 'get_weather(city: str)'查询指定城市的天气情况
- 'get_attraction(city: str, weather: str)':根据城市和天气搜索推荐对应的旅游景点
 
# 格式要求
你的回复必须遵循以下格式，包含一对Thought和Action：
Thought：[你的思考过程和下一步计划]
Action：[你要执行的具体操作]

#Action回复格式须是以下之一：
1.调用工具：function_name(arg_name="arg_value")
2.结束任务：Finish[最终答案]

#重要提示：
- 每次只输出一对Thought-Action
- Action必须在同一行不要换行
- 当收集到足够信息可以回答用户的问题的时候必须以Thought＋Action [最终答案]回复
 
 请开始

"""


import os
from tavily import TavilyClient
import requests
def get_weather(city: str) -> str:
    url = f"https://wttr.in/{city}?format=j1"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        current_condition = data["current_condition"][0]
        weather_desc = current_condition["weatherDesc"][0]['value']
        temp_c = current_condition["temp_C"]
        
        return f"{city}当前天气：{weather_desc}，气温{temp_c}摄氏度"
    
    except requests.exceptions.RequestException as e:
        return f"错误查询天气时遇到网络问题- {e}"
    except (KeyError, IndexError) as e:
        return  f"错误可能是城市名称不存在- {e}"
    
    
def get_attraction(city: str, weather: str) -> str:
    api_key = os.environ.get("API_KEY")
    if not api_key:
        return "错误：未配置TAVLILY_APIKEY环境变量"
    tavily = TavilyClient(api_key=api_key)
    query = f"'{city}'在'{weather}'天气下最值得去的旅游景点推荐及理由"
    
    try:
        response = tavily.search(query=query, search_depth="basic", include_answers=Ture)
        
        if response.get("answer"):
            answer = response["answer"]
        formatted_result = []
        for result in response.get("results",[]):
            formatted_result.append(f"-{result['title']}: {result['content']}")
            
        if not formatted_result:
            return f"抱歉没找到对应景点推荐"
        return "根据搜索找到以下信息：\n"+"\n".join(formatted_result)
    except Exception as e:
        return f"错误"
        

available_tools = {
    "get_weather": get_weather,
    "get_attraction": get_attraction,
}
