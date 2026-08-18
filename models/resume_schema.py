from dataclasses import dataclass, asdict
from typing import Dict

"""简历信息结构化数据模型
    使用 @dataclass 装饰器自动生成 __init__、__repr__ 等方法，
    所有字段默认为空字符串，方便逐步填充 OCR 或大模型提取的结果。
    字段命名采用中文，与简历中的实际字段名保持一致，便于理解和映射。
"""
@dataclass
class jianli:
    姓名: str = ""
    性别: str = ""
    民族: str = ""
    出生年月: str = ""
    年龄: str = ""
    电话: str = ""
    邮箱: str = ""
    学历: str = ""
    学校: str = ""
    专业: str = ""
    求职意向: str = ""
    教育背景: str = ""
    工作经历: str = ""
    项目经历: str = ""
    技能证书: str = ""
    技能掌握: str = ""
    自我评价: str = ""
    其他信息: str = ""

    @classmethod
    def empty(cls) -> "jianli":

        return cls()

    def to_dict(self) -> Dict[str, str]:
        """将实例转换为字典格式
                便于后续序列化为 JSON、保存到数据库或通过 API 返回。
                利用 asdict() 将 dataclass 实例递归转换为普通字典。
                Returns:
                    Dict[str, str]: 包含所有字段名和对应值的字典
                """
        return asdict(self)