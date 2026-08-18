from utils.file_parser import extract_resume_from_file
#导入简历解析函数

def process_resume(file_path: str, original_filename: str = "") -> dict:
    return extract_resume_from_file(file_path, original_filename=original_filename)
"""
    处理简历文件
    参数：
        file_path: 简历文件路径
        original_filename: 原始文件名，默认空字符串
    返回：
        解析后的简历信息字典
"""
# 调用底层文件解析函数，解析简历内容并返回结果