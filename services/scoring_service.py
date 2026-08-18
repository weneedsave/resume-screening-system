import re
#导入正则表达式模块
#导入类型标注工具
from typing import Dict, Any, List, Tuple
#导入一个 AI 分析函数
from utils.ai_service import ai_review_match
from utils.text_utils import normalize_text, split_list_text, extract_skills_from_text
"""
导入几个文本处理工具：
normalize_text：规范化文本
split_list_text：把字符串或列表整理成统一列表
extract_skills_from_text：从文本里提取技能
"""
#把一份简历进行打分，最后输出一个综合评分、等级、命中项、风险点，还可选地调用 AI 做进一步分析。
EDU_RANK = {
    "高中": 1,
    "中专": 2,
    "技校": 2,
    "大专": 3,
    "专科": 3,
    "本科": 4,
    "学士": 4,
    "硕士": 5,
    "研究生": 5,
    "博士": 6,
    "博士后": 7,
}#把学历转换成“等级数字”，这样方便比较

def _resume_fields(resume: Dict[str, Any]) -> Dict[str, Any]:#从简历数据里取出“字段信息”。
    if "fields" in resume and isinstance(resume["fields"], dict):
        return resume["fields"]#简历里有 fields
    return resume

def _resume_text(resume: Dict[str, Any]) -> str:
    fields = _resume_fields(resume)#从简历数据里取出“字段信息”
    parts = [
        str(resume.get("raw_text", "") or ""),# 原始文本
        str(resume.get("text", "") or ""), # 解析后的正文文本
        str(fields.get("教育背景", "") or ""),
        str(fields.get("工作经历", "") or ""),
        str(fields.get("自我评价", "") or ""),
        str(fields.get("专业", "") or ""),
        str(fields.get("学校", "") or ""),
        str(fields.get("求职意向", "") or ""),
    ]
    # 把这些内容用换行拼接成一整段文本，并做文本规范化处理
    return normalize_text("\n".join(parts))

def _parse_education_rank(text: str) -> int:
    t = normalize_text(text)
    for k, v in EDU_RANK.items():
        if k in t:
            return v
    return 0

def _edu_score(candidate_edu: str, required_edu: str) -> Tuple[int, str]:
    if not required_edu:
        return 10, "岗位未设置学历硬要求，默认给予基础分"

    c_rank = _parse_education_rank(candidate_edu)
    r_rank = _parse_education_rank(required_edu)

    if c_rank == 0:
        return 0, f"未能识别候选人学历，要求：{required_edu}"

    if c_rank >= r_rank and r_rank > 0:
        return 20, f"学历满足要求：{candidate_edu} >= {required_edu}"

    if c_rank + 1 == r_rank:
        return 8, f"学历接近要求：{candidate_edu}，岗位要求：{required_edu}"

    return 0, f"学历不满足：{candidate_edu} < {required_edu}"

#根据简历里的技能，去匹配岗位要求的技能，并计算一个技能分数,传入候选人技能、必须技能、加分技能、简历文本，然后返回技能评分结果。
def _skill_match_score(candidate_skills: List[str], must_skills: List[str], preferred_skills: List[str], text: str) -> Tuple[int, List[str], List[str], List[str]]:
    cset = {s.lower() for s in candidate_skills}#把候选人技能转成小写集合
    text_lower = text.lower()#把简历文本转成小写
    #准备三个空列表
    matched_must = []
    missing_must = []
    matched_pref = []
    #如果岗位有必须技能
    if must_skills:
        each = 28 / max(len(must_skills), 1)#计算每个必须技能的分值,最多28分
        for s in must_skills:
            key = s.lower()
            #如果技能在候选人技能里或者简历文本里,候选人技能列表里有或者简历正文里出现过
            if key in cset or key in text_lower:
                matched_must.append(s)
            else:
                missing_must.append(s)
    else:#如果没有必须技能
        each = 0
    #处理加分技能
    if preferred_skills:
        for s in preferred_skills:
            key = s.lower()
            if key in cset or key in text_lower:
                matched_pref.append(s)

    score = int(min(28, len(matched_must) * each))#计算必须技能分
    score += int(min(7, len(matched_pref) * 1.5))#计算加分技能分,一个1.5,最多7分
    #返回技能分、必须技能、缺少技能、加分技能
    return score, matched_must, missing_must, matched_pref

#根据简历里的专业、学校、技能、学历、工作年限、技能、关键词等信息，去匹配岗位要求，并计算一个综合评分，传入简历数据、岗位要求、简历文本，然后返回综合评分结果。
def _major_score(major: str, text: str, major_keywords: List[str]) -> Tuple[int, List[str]]:
    if not major_keywords:
        # 岗位未设置专业要求，给基础分8
        return 8, ["岗位未设置专业要求，给基础分"]

    haystack = (major + "\n" + text).lower()#把专业、技能、学历、工作年限、关键词等信息转成小写
    matched = []#用来存储命中的专业关键词
    #逐个检查关键词
    for kw in major_keywords:
        if kw.lower() in haystack:#如果关键词出现在 major 或 text 中
            matched.append(kw)

    if matched:#只要命中了至少一个关键词,返回15分,返回命中的关键词
        return 15, matched
    #否则返回0
    return 0, []
#看简历里的专业和内容，是否命中岗位要求的专业关键词；命中就给分，没命中就不给分。

#
def _experience_years(text: str) -> int:
    t = text.lower()
    ## 把文本转成小写，方便匹配英文内容
    #定义了多个正则表达式，用来匹配不同的经验表达方式。
    patterns = [
        r"(\d+)\s*年\s*工作经验",
        r"工作经验[:：]?\s*(\d+)\s*年",
        r"(\d+)\s*年经验",
        r"(\d+)\s*years?",
        r"(\d+)\+?\s*年",
    ]
    #逐个尝试匹配
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            try:
                return int(m.group(1))#取出数字并返回
            except Exception:#如果数字转换失败，就跳过，不报错，继续尝试后面的模式。
                pass

    return 0

#根据简历里的工作年限、岗位要求、简历文本，计算一个工作年限评分，传入简历文本、岗位要求、简历文本，然后返回工作年限评分结果。
def _experience_score(text: str, required_years: int) -> Tuple[int, str]:
    if not required_years or required_years <= 0:
        return 10, "岗位未设置工作年限要求，默认给予基础分"
    #如果岗位没有写工作经验要求,给基础分10

    years = _experience_years(text)#获取简历里工作年限

    if years >= required_years:#工作年限满足要求
        return 20, f"工作年限满足：{years} 年 >= {required_years} 年"

    if years == 0:#工作年限未识别
        return 0, "未识别到明确工作年限"

    ratio = years / required_years
    #如果经验年限低于要求，但不是 0，就按比例给分。
    return max(0, int(20 * ratio)), f"工作年限不足：{years} 年 < {required_years} 年"

#根据简历里的关键词、岗位要求、简历文本，计算一个关键词评分，传入简历文本、岗位要求、简历文本，然后返回关键词评分结果。
def _keyword_score(text: str, keywords: List[str]) -> Tuple[int, List[str]]:
    if not keywords:#如果岗位没有设置关键词，就给基础分0
        return 0, []

    haystack = text.lower()#把简历文本转成小写
    matched = [kw for kw in keywords if kw.lower() in haystack]
    #找出命中的关键词

    score = min(10, len(matched) * 2)#每命中 1 个关键词，得 2 分,最多 10 分
    return score, matched
#统计文本里命中了多少个关键词，并按数量给分，最高 10 分

#根据评分结果，返回推荐等级
def _level(score: int) -> str:
    if score >= 85:
        return "A-推荐"
    if score >= 70:
        return "B-合格"
    if score >= 55:
        return "C-谨慎"
    return "D-不推荐"

#把“简历”和“岗位要求”做匹配，算出一个综合评分，并返回详细分析结果。
def score_resume_against_job(resume: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
    fields = _resume_fields(resume)#取出简历里的结构化字段
    text = _resume_text(resume)#取出简历全文文本
    #获取简历里的学历、专业、姓名、学校、技能,默认值空
    candidate_edu = str(fields.get("学历", "") or "")
    candidate_major = str(fields.get("专业", "") or "")
    candidate_name = str(fields.get("姓名", "") or "")
    candidate_school = str(fields.get("学校", "") or "")

    candidate_skills = resume.get("skills") or extract_skills_from_text(text)#优先使用简历里已有的 skills 字段,否则从简历全文里提取

    #获取岗位要求里的学历、专业、技能、工作年限、关键词等信息
    job_title = job.get("title", "")
    required_edu = str(job.get("education", "") or "")
    required_years = int(job.get("years_experience") or 0)
    must_skills = split_list_text(job.get("must_have_skills", []))
    preferred_skills = split_list_text(job.get("preferred_skills", []))
    major_keywords = split_list_text(job.get("major_keywords", []))
    keywords = split_list_text(job.get("keywords", []))
    description = str(job.get("description", "") or "")

    #计算学历、专业、技能、工作年限、关键词等信息的评分
    edu_score, edu_reason = _edu_score(candidate_edu, required_edu)
    major_score, major_matched = _major_score(candidate_major + " " + candidate_school, text, major_keywords)#有些学校或院系名称里会带专业信息，这样可以增加命中率。
    skill_score, matched_must, missing_must, matched_pref = _skill_match_score(candidate_skills, must_skills, preferred_skills, text)
    exp_score, exp_reason = _experience_score(text, required_years)#岗位要求里设置了工作年限要求，就计算工作年限评分
    keyword_score, keyword_matched = _keyword_score(text + "\n" + description, keywords)

    base_score = edu_score + major_score + skill_score + exp_score + keyword_score#计算基础总分

    # 对必须技能做扣分，强化硬要求
    penalty = min(30, len(missing_must) * 8)
    final_score = max(0, min(100, base_score - penalty))#计算最终分数

    result = {
        #这部分是把候选人和岗位的基本信息放进结果里
        "candidate_name": candidate_name,
        "candidate_school": candidate_school,
        "candidate_major": candidate_major,
        "candidate_edu": candidate_edu,
        "job_title": job_title,

        #这里记录每一项的分数。
        "score_detail": {
            "education_score": edu_score,
            "major_score": major_score,
            "skill_score": skill_score,
            "experience_score": exp_score,
            "keyword_score": keyword_score,
            "penalty": -penalty,#技能扣分
        },
        "score": final_score,#最终分数
        "level": _level(final_score),#推荐等级

        #这里记录匹配结果
        "matched_must_have": matched_must,
        "missing_must_have": missing_must,
        "matched_preferred": matched_pref,
        "major_matched": major_matched,
        "keyword_matched": keyword_matched,
        #这里记录匹配原因
        "reasons": [
            edu_reason,
            exp_reason,
            f"已匹配必须技能：{', '.join(matched_must) if matched_must else '无'}",
            f"已匹配加分技能：{', '.join(matched_pref) if matched_pref else '无'}",
            f"专业命中：{', '.join(major_matched) if major_matched else '无'}",
            f"关键词命中：{', '.join(keyword_matched) if keyword_matched else '无'}",
        ],
        #风险提示,建立一个空列表
        "risks": [],
    }
    #如果缺少必须技能，就加入风险
    if missing_must:
        result["risks"].append(f"缺少必须技能：{', '.join(missing_must)}")
    #如果分数低于 70，就加入风险
    if final_score < 70:
        result["risks"].append("综合匹配度较低，请检查")

    # AI 辅助分析（可选）
    #在已有评分结果的基础上，再让 AI 做一次辅助复核，并把 AI 的分析结果放进最终返回值里。
    try:
        ai_review = ai_review_match(
            #传入简历信息
            resume={
                "姓名": candidate_name,
                "学历": candidate_edu,
                "专业": candidate_major,
                "学校": candidate_school,
                "skills": candidate_skills,
                "text": text[:3000],#截取前 3000 个字符
            },
            #传入岗位信息
            job={
                "岗位名称": job_title,
                "学历要求": required_edu,
                "工作年限要求": required_years,
                "必须技能": must_skills,
                "加分技能": preferred_skills,
                "专业要求": major_keywords,
                "关键词": keywords,
                "岗位描述": description[:3000],
            },
            base_result=result,#传入基础评分结果
        )
        result["ai_review"] = ai_review
        #把 AI 的分析结果放进最终返回值里
    #异常处理
    except Exception:
        result["ai_review"] = {}

    return result