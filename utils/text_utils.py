import json
#处理 JSON 格式 的数据
import re
#用于处理 正则表达式,字符串匹配
from typing import Dict, Any, List
#从 typing 模块中导入类型注解工具。

DEFAULT_RESUME_FIELDS = {
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
}
#帮助程序识别不同简历里对同一个字段的不同写法
FIELD_ALIASES = {
    "姓名": ["姓名", "名字"],
    "性别": ["性别"],
    "民族": ["民族"],
    "出生年月": ["出生年月", "出生日期", "生日"],
    "年龄": ["年龄"],
    "电话": ["电话", "手机", "联系方式", "联系电话", "手机号"],
    "邮箱": ["邮箱", "电子邮箱", "Email", "E-mail"],
    "学历": ["学历"],
    "学校": ["学校", "毕业院校", "院校"],
    "专业": ["专业"],
    "求职意向": ["求职意向", "应聘岗位", "意向岗位", "期望岗位"],
    "现居住地": ["现居住地", "住址", "地址", "居住地"],
    "籍贯": ["籍贯", "贯籍"],
    "教育背景": ["教育背景", "教育经历"],
    "工作经历": ["工作经历", "工作经验", "实习经历"],
    "自我评价": ["自我评价", "个人评价"],
}
#创建一个空的 set（集合）
ALL_LABELS = set()
#遍历 FIELD_ALIASES 的所有值
for aliases in FIELD_ALIASES.values():
    # 把别名加入集合
    ALL_LABELS.update(aliases)
#程序在处理简历时，可以扫描文本里有没有这些词
COMMON_SKILLS = [
    "python", "java", "javascript", "typescript", "sql", "mysql", "postgresql",
    "mongodb", "redis", "linux", "docker", "kubernetes", "git", "flask",
    "django", "fastapi", "spring", "spring boot", "vue", "react", "node",
    "html", "css", "c++", "c#", "go", "php", "spark", "hadoop", "hive",
    "tensorflow", "pytorch", "opencv", "pandas", "numpy", "machine learning",
    "deep learning", "数据分析", "机器学习", "深度学习", "爬虫", "scrapy",
    "selenium", "rest", "api", "excel", "power bi", "tableau", "cad",
    "autocad", "ui", "ux", "photoshop", "figma"
]
#对文本做标准化清洗，让简历内容更整洁、更方便后续解析
def normalize_text(text: str) -> str:
    #如果文本为空，直接返回空串
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")#把不同系统里的换行格式统一成 \n。
    text = text.replace("\u200b", "").replace("\ufeff", "")#删除一些常见的隐藏字符。

    #准备一个列表存放清洗后的行
    lines = []
    # 按行处理文本
    for line in text.split("\n"):
        line = line.replace("\u00a0", " ").strip()#把不间断空格替换成普通空格，并去掉首尾空白
        line = re.sub(r"[ \t]+", " ", line)#把连续空格或制表符压缩成一个空格
        # 如果行不为空，则加入列表
        if line:
            lines.append(line)
    #把所有行重新拼接起来
    return "\n".join(lines).strip()

#从一段可能包含 Markdown 代码块、杂乱文本或前后说明的内容中，尽量提取出一个 JSON 对象（字典）
def extract_json_object(text: str) -> Dict[str, Any]:
    #如果文本为空，则返回错误
    if not text:
        raise ValueError("空文本，无法提取 JSON")
    #去掉首尾空白
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)#去掉开头的 Markdown JSON 代码块标记
    s = re.sub(r"\s*```$", "", s)

    try:
        obj = json.loads(s)
        #判断解析出来的结果是不是字典。
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    #找出文本中第一个 { 和最后一个 }
    start = s.find("{")
    end = s.rfind("}")
    #如果有 { 和 }，则尝试从文本中提取 JSON
    if start != -1 and end != -1 and end > start:
        candidate = s[start:end + 1]
        #尝试解析截取内容
        obj = json.loads(candidate)
        if isinstance(obj, dict):
            return obj
    #如果都失败了，抛出异常
    raise ValueError(f"无法从内容中解析 JSON：{text[:300]}")

#判断一行文本是不是“字段标签”或“字段名”，比如“姓名”“电话”“邮箱”等。
def _looks_like_label(line: str) -> bool:
    s = line.strip().replace("：", "").replace(":", "").strip()
    return s in ALL_LABELS
    #返回一个布尔值

#从一行文本中提取某个标签后面的值。
#比如从 "姓名：张三" 中提取出 "张三"
def _extract_value_from_line(line: str, alias: str) -> str:
    s = line.strip()
    #判断这一行是否以指定标签开头(alias)
    if not s.startswith(alias):
        return ""
    rest = s[len(alias):].strip()#截取标签后面的内容
    rest = rest.lstrip("：:").strip()#去掉冒号
    return rest.strip()

#从整段文本里补充提取邮箱和电话，如果 result 里还没有对应字段，就自动用正则去找,结构化解析没抓到电话/邮箱，就需要兜底扫描全文。
#这个函数不返回值，它直接修改 result
def _fill_phone_email(text: str, result: Dict[str, str]) -> None:
    #如果结果里没有“邮箱”，就尝试从全文找邮箱
    if not result.get("邮箱"):
        m = re.search(r"[\w.\-+]+@[\w\-]+\.[\w.\-]+", text)#全文 text 里查找类似邮箱的字符串。
        if m:
            result["邮箱"] = m.group(0)
    #如果结果里没有“电话”，就尝试从全文找电话
    if not result.get("电话"):
        phone_patterns = [
            r"(?:\+?86[-\s]?)?(1[3-9]\d{9})",
            r"\b\d{3,4}-\d{7,8}\b",#固定 电话
        ]
        #依次尝试每个电话模式
        for pat in phone_patterns:
            m = re.search(pat, text)
            if m:
                result["电话"] = m.group(1) if m.lastindex else m.group(0)
                break

#从一段简历文本中，按字段名和别名提取信息，整理成一个字典 result
def parse_resume_fields(text: str) -> Dict[str, str]:
    #先把原始文本做清洗。
    text = normalize_text(text)
    #按行切分文本
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    #初始化结果字典
    result: Dict[str, str] = {}

    #遍历每一行
    for i, line in enumerate(lines):
        #遍历所有字段及其别名
        for field, aliases in FIELD_ALIASES.items():
            #如果结果里已经包含这个字段，则跳过
            if field in result:
                continue
            #判断这一行是不是以某个别名开头
            for alias in aliases:
                #如果是，则尝试从这一行中提取字段值
                if line.startswith(alias):
                    #尝试从这一行中提取字段值
                    value = _extract_value_from_line(line, alias)
                    #如果这一行里已经有值，就直接保存
                    if value:
                        result[field] = value
                        break
                    #如果这一行没有值，但下一行不是标签，则尝试从下一行中提取字段值
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line and not _looks_like_label(next_line):#判断下一行是不是“可作为值”的内容
                            result[field] = next_line
                            break

                    break

    _fill_phone_email(text, result)#在主循环结束后，再从全文里补充找电话和邮箱
    return result

#把输入的数据补全成一份“完整的简历字段字典”，并确保每个字段都是字符串。
def complete_resume_fields(data: Dict[str, Any]) -> Dict[str, str]:
    result = dict(DEFAULT_RESUME_FIELDS)#避免直接修改原始默认配置。

    #如果输入不是字典，直接返回默认结果
    if not isinstance(data, dict):
        return result
    #遍历默认字段的所有 key
    for key in result.keys():
        #从输入数据中取同名字段
        value = data.get(key, "")
        if value is None:
            value = ""
        result[key] = str(value).strip()# 把值转成字符串并去掉首尾空白

    if not result["邮箱"] and data.get("email"):#如果中文“邮箱”为空，但有 email，就补到“邮箱”
        result["邮箱"] = str(data["email"]).strip()
    if not result["电话"] and data.get("phone"):#如果中文“邮箱”为空，但有 email，就补到“邮箱”
        result["电话"] = str(data["phone"]).strip()

    return result

#从一段文本里提取技能关键词，并去重后返回一个技能列表。
def extract_skills_from_text(text: str) -> List[str]:
    if not text:
        return []

    raw = normalize_text(text).lower()#先对文本做清洗，再统一转成小写。
    found = []
    #遍历预定义技能表
    for skill in COMMON_SKILLS:
        #判断技能是否出现在文本中
        if skill.lower() in raw:
            found.append(skill)

    # 中文技能去重后再补充
    unique = []#最终去重后的结果
    seen = set()#存储已经出现的技能
    for item in found:#遍历已找到的技能
        key = item.lower()#统一成小写作为去重
        #如果没见过，就保留
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique

#把各种形式的“列表文本”统一拆分成一个去重后的字符串列表
def split_list_text(value: Any) -> List[str]:
    #如果是 None，则返回空列表
    if value is None:
        return []
    #如果输入本来就是列表，直接使用
    if isinstance(value, list):
        items = value
    else:
        #把它转成字符串并统一分隔符
        s = str(value).replace("，", ",").replace("；", ",").replace("、", ",")
        items = [x.strip() for x in s.split(",")]
    #初始化结果和去重集合
    result = []
    seen = set()
    for item in items:
        item = str(item).strip()
        if not item:
            continue
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result

#把简历原文、解析出的字段、技能提取结果整合成一个统一的结果对象,传入一个简历原文、字段、技能提取结果
def build_resume_result(text: str, fields: Dict[str, Any], source: str) -> Dict[str, Any]:
    normalized_text = normalize_text(text)#先对文本做清洗
    completed_fields = complete_resume_fields(fields)#把输入的字段补全成完整字段
    skills = extract_skills_from_text(normalized_text)#从规范化文本里提取技能
    #返回统一结构
    return {
        "source": source,
        "text": normalized_text,
        "fields": completed_fields,
        "skills": skills,
    }