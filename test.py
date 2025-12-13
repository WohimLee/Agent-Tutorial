      
from transformers import AutoModel, AutoTokenizer
import torch
import random
from typing import  Annotated


def get_weather(city: Annotated[str, 'The name of the city to be queried', True]):
    """
    Get the current weather for `city_name`
    """

    if not isinstance(city, str):
        raise TypeError("City name must be a string")

    key_selection = {
        "current_condition": ["temp_C", "FeelsLikeC", "humidity", "weatherDesc", "observation_time"],
    }
    import requests
    try:
        resp = requests.get(f"https://wttr.in/{city}?format=j1")
        resp.raise_for_status()
        resp = resp.json()
        ret = {k: {_v: resp[k][0][_v] for _v in v} for k, v in key_selection.items()}
    except:
        import traceback
        ret = "Error encountered while fetching weather data!\n" + traceback.format_exc()

    return str(ret)

# # 获取某一个城市的天气
# def get_weather2(city):
#     if city == "北京":
#         return "北京当前的最高温度为 -1, 最低温为-10"
#     else:
#         return f"{city}当前的最高温度为 3, 最低温为 0"


# 随机获取一个地名
# def get_a_chengshi():
#     citys = ["北京", "武汉", "广州", "青岛"]
#     city = random.choice(citys)
#     return city


all_tools = [
    {
        "name": "get_weather",
        "description": "根据提供的城市，获取对应的天气",
        "parameters":
            {
                "type": "object",
                "properties": {

                    "city": {
                        "description": "城市名称",
                    }
                },
                "required": ["city"]
            }

    }
]



def model_chat_new(query):
    system_prompt = "请根据提供的工具，回复用户,工具如下："
    system_info = {
        "role": "system",
        "content": system_prompt,
        "tools": all_tools
    }

    his = [system_info]
    while True:
        res, his = model.chat(tokenizer, query, history=his)
        if isinstance(res, dict):
            fun_name = res.get("name")
            fun_param = res.get("parameters")
            fun_res = eval(f"{fun_name}(**fun_param)")

            query = fun_res

        else:
            break
    return res


if __name__ == "__main__":

    tokenizer = AutoTokenizer.from_pretrained("D:\\shouxie_ai\\model\\chatglm3-6b-chat", trust_remote_code=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = AutoModel.from_pretrained("D:\\shouxie_ai\\model\\chatglm3-6b-chat", trust_remote_code=True)
    if device == "cuda":
        model = model.half().to(device)
    else:
        model = model.float().to(device)
    model = model.eval()
    # ans,his = model.chat(tokenizer,"北京今天的天气如何？",history=[])

    while True:
        input_text = input("输入：")
        # ans = model_chat_new("请随机一个地名，根据该地的天气，推荐穿衣？")
        ans = model_chat_new(input_text)
        print("输出：", ans)
        print("\\n")


    