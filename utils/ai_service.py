import os
import base64
#于类型注解，帮助代码更清晰
from typing import Dict, Any

from config import DASHSCOPE_API_KEY, DASHSCOPE_MODEL, AI_TIMEOUT

#使用try安装openai,防止错误
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

from utils.text_utils import extract_json_object, complete_resume_fields

client = None
if DASHSCOPE_API_KEY and OpenAI is not None:
    client = OpenAI(
        api_key=DASHSCOPE_API_KEY,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
#把本地图片文件转换成 Data URL,传入文件路径，返回 Data URL
def _image_to_data_url(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()#从文件路径中提取扩展名，并转成小写
    #建立字典，用来把文件扩展名映射成对应的 MIME 类型。
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    mime_type = mime_map.get(ext, "image/png")#根据扩展名取出对应的 MIME 类型,如果没有则默认为 PNG
    #以二进制方式打开图片
    with open(file_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")#读取并编码成 Base64

    return f"data:{mime_type};base64,{img_b64}"# 返回 Data URL

#分析简历图片,传入的是图片文件路径，类型是字符串。
def analyze_resume_image(file_path: str) -> dict:
    if client is None:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY 或未安装 openai")

    if not DASHSCOPE_MODEL:
        raise RuntimeError("未配置 DASHSCOPE_MODEL")

    image_url = _image_to_data_url(file_path)#把图片转成 Data URL
#构造提示词
    prompt = """
你是一个简历解析助手。

请识别图片中的简历内容，并只输出合法 JSON，不要输出任何解释、不要输出 Markdown 代码块。

要求：
1. 尽量还原简历中的原始文本
2. 识别字段并填入对应值
3. 如果某个字段不存在，值写空字符串
4. 输出必须是严格合法 JSON

JSON 格式如下：
{
  "姓名": "",
  "性别": "",
  "民族": "",
  "出生年月": "",
  "年龄": "",
  "电话": "",
  "邮箱": "",
  "学历": "",
  "学校": "",
  "专业": "",
  "求职意向": "",
  "现居住地": "",
  "籍贯": "",
  "教育背景": "",
  "工作经历": "",
  "自我评价": "",
  "raw_text": ""
}

注意：
- 字段名必须使用中文
- raw_text 里尽量写出识别到的完整文本
- 如果有不确定内容，也尽量保留，不要乱编
"""
#发起请求，让模型分析图片。
    completion = client.chat.completions.create(
        model=DASHSCOPE_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
        temperature=0,
        timeout=AI_TIMEOUT,
    )
    #从模型返回结果中取出正文内容。
    content = completion.choices[0].message.content or ""
    data = extract_json_object(content)#提取 JSON 对象

    raw_text = str(data.pop("raw_text", "") or "")#从 data 里把 raw_text 取出来，同时删除这个键
    fields = complete_resume_fields(data)#补全缺失的字段
    """返回一个字典，里面包含三部分：
            "source": "ai"
            表示结果来自 AI 分析
            "text": raw_text
            原始识别文本
            "fields": fields
            结构化后的简历字段"""
    return {
        "source": "ai",
        "text": raw_text,
        "fields": fields,
    }

#让大模型根据“简历 + 岗位要求 + 规则评分结果”生成一份筛选建议，但不直接替代原有规则评分。
#传入resume 是简历信息，job 是岗位信息，base_result 是基础评分结果
def ai_review_match(resume: Dict[str, Any], job: Dict[str, Any], base_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    AI 辅助生成筛选建议，不直接替代规则评分。
    """
    if client is None:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY 或未安装 openai")

    prompt = f"""
你是一个招聘筛选助手。请根据“简历”和“岗位要求”给出判断。

请只输出严格 JSON，不要输出 Markdown，不要输出解释文本。

输出格式：
{{
  "ai_summary": "一句话总结",
  "ai_strengths": ["优点1", "优点2"],
  "ai_risks": ["风险1", "风险2"],
  "ai_suggestion": "推荐 / 待定 / 不推荐",
  "ai_note": "简短说明"
}}

岗位要求：
{job}

简历信息：
{resume}

系统已有规则评分结果：
{base_result}

要求：
- 结合岗位要求判断，不要只看学历
- 尽量给出可执行的筛选建议
- 保持客观，不要编造
"""

    completion = client.chat.completions.create(
        model=DASHSCOPE_MODEL,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        timeout=AI_TIMEOUT,
    )
    #从模型返回结果中取出正文内容。
    content = completion.choices[0].message.content or ""
    return extract_json_object(content)#提取 JSON 对象,返回结果