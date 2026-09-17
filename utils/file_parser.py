import logging
import os
#BytesIO 可以把二进制数据当作文件对象来处理。
from io import BytesIO
#用来处理 PDF 文件
import fitz  # PyMuPDF
#用于读写 Word 文档
import docx
#这是 Tesseract OCR 的 Python 接口,识别图片中的文字
import pytesseract
#从 Pillow 库中导入多个图像处理工具。
"""ImageOps
图片基础操作工具，比如：
灰度化
翻转
裁剪
自动对比度
ImageEnhance
用于增强图像效果，比如：
对比度增强
亮度增强
锐化
ImageFilter
用于给图片应用滤镜，比如：
模糊
边缘增强
平滑"""
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
#从 .docx 文件中提取纯文本
try:
    import docx2txt
except Exception:
    docx2txt = None
#用于配置 pytesseract，让程序知道 Tesseract 安装在哪里,配合ocr
from config import TESSERACT_EXE, TESSDATA_DIR
from utils.ai_service import analyze_resume_image
from utils.text_utils import normalize_text, parse_resume_fields, build_resume_result

logger = logging.getLogger(__name__)

# Tesseract 配置
#检查 Tesseract 可执行文件是否存在
if os.path.exists(TESSERACT_EXE):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE
#检查语言数据目录是否存在
if os.path.isdir(TESSDATA_DIR):
    os.environ["TESSDATA_PREFIX"] = TESSDATA_DIR
#预处理图片,传入图片对象
def _preprocess_image(img: Image.Image) -> Image.Image:
    img = img.convert("L")#转换为灰度图像
    img = ImageOps.autocontrast(img)#自动对比度
    img = ImageEnhance.Contrast(img).enhance(1.6)#手动对比度
    img = ImageEnhance.Sharpness(img).enhance(1.8)#锐化
    img = img.filter(ImageFilter.SHARPEN)#再次锐化,提升文字清晰
    return img

_CJK_START = "一"
_CJK_END = "鿿"


def _ocr_quality(text: str) -> tuple:
    """给一次 OCR 结果打分，用于在多个识别方案之间择优。

    不能只比长度——这是踩过的坑：中文排版如果被当成英文识别，每个汉字会被拆成
    好几个字母，垃圾结果的字符数反而更多。实测同一张中文简历：
      chi_sim+eng 识别出 192 个字符的正确中文
      eng         识别出 203 个字符的乱码（"姓名" -> "TAR"）
    「选最长」于是扔掉了正确答案。改成先比中文汉字个数、再比总长度。
    """
    cjk = sum(1 for ch in text if _CJK_START <= ch <= _CJK_END)
    return (cjk, len(text))


#使用 Tesseract OCR 识别图片中的文字,传入图片对象
def _ocr_with_tesseract(img: Image.Image) -> str:
    img = _preprocess_image(img)#预处理图片
    #多试几种组合，提升识别成功率
    attempts = [
        ("chi_sim+eng", r"--oem 3 --psm 6"),
        ("chi_sim+eng", r"--oem 3 --psm 11"),
        ("eng", r"--oem 3 --psm 6"),
    ]
    #空字符串
    best_text = ""
    for lang, config in attempts:
        try:
            text = pytesseract.image_to_string(img, lang=lang, config=config)#使用 Tesseract OCR 识别图片中的文字
            text = (text or "").strip()#去除空字符串
            if not text:
                continue
            if _ocr_quality(text) > _ocr_quality(best_text):#择优：先比中文数，再比长度
                best_text = text
        except Exception as e:
            # 某一个方案失败不影响其他方案，但必须留痕，
            # 否则「chi_sim 语言包没装」这类问题会表现为「OCR 结果莫名其妙很差」
            logger.warning("OCR 方案 %s %s 执行失败：%s", lang, config, e)

    if not best_text:
        logger.warning("所有 OCR 方案都没有识别出内容")
    elif _ocr_quality(best_text)[0] == 0:
        # 一个汉字都没认出来，但结果非空——大概率是中文被当成拉丁字母识别了
        logger.warning("OCR 结果中未识别到任何中文，可能是语言包缺失或图片质量过差")

    return best_text.strip()
#从 PDF 文件中提取纯文本,传入 PDF 文件路径
def extract_text_from_pdf(file_path: str) -> str:
    doc = fitz.open(file_path)#打开 PDF 文件
    text_parts = []#准备一个列表存文本
    #遍历每一页
    for page in doc:
        page_text = (page.get_text("text") or "").strip()#尝试直接提取文字
        #如果长度超过 20 个字符，就加入结果列表
        if len(page_text) >= 20:
            text_parts.append(page_text)
            continue
        # 如果文字太少，就转成图片,尝试OCR
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        img = Image.open(BytesIO(pix.tobytes("png")))#把渲染结果转成 PIL 图片
        ocr_text = _ocr_with_tesseract(img)#使用 Tesseract OCR 识别图片中的文字

        if ocr_text:
            text_parts.append(ocr_text)
    #把所有页的内容拼接成一个大字符串，再做文本归一化。
    return normalize_text("\n".join(text_parts))
#从 DOCX 文件中提取文本，优先尝试 docx2txt，再用 python-docx 读取段落和表格内容，最后统一清洗
def extract_text_from_docx(file_path: str) -> str:
    text_parts = []
    # 尝试使用 docx2txt
    if docx2txt is not None:
        try:
            text = (docx2txt.process(file_path) or "").strip()
            if text:
                text_parts.append(text)
        except Exception:
            pass
#尝试用 python-docx 打开文件
    try:
        document = docx.Document(file_path)
        #遍历所有段落，提取每一段的文本。
        for para in document.paragraphs:
            t = para.text.strip()#para.text：段落文本.strip()：去掉前后空白
            if t:
                text_parts.append(t)
        #遍历所有表格，提取表格内容
        for table in document.tables:
            for row in table.rows:#遍历表格的行
                row_text = []
                for cell in row.cells:#遍历这一行中的每个单元格。
                    t = cell.text.strip()#cell.text：单元格文本.strip()：去掉前后空白
                    if t:
                        row_text.append(t)
                if row_text:
                    text_parts.append(" | ".join(row_text))# 连接同一行的多个单元格，方便阅读。
    #如果 python-docx 在解析时出错,如果前面已经提取到了一些内容，就不报错,如果前面什么都没提取到，就抛出一个更明确的错误
    except Exception as e:
        if not text_parts:
            raise RuntimeError(f"DOCX 提取失败：{e}") from e

    return normalize_text("\n".join(text_parts))
#从图片中提取文本
def extract_text_from_image(file_path: str) -> dict:
    """
    图片简历：
    1. 优先 AI 解析
    2. 失败再 OCR
    """
    try:
        ai_result = analyze_resume_image(file_path)#调用 analyze_resume_image(file_path) 对图片做 AI 解析
        if ai_result:
            text = normalize_text(ai_result.get("text", ""))#去掉多余空格规范换行清理脏字符
            fields = ai_result.get("fields", {})#从 AI 结果中取出字段信息
            return build_resume_result(text, fields, source="ai")#生成统一的简历结果
    except Exception as e:
        # AI 是"优先"而不是"必须"，失败要降级到 OCR，不能中断。
        # 但这里绝对不能静默——API Key 失效、模型名写错、网络不通都会走到这里，
        # 全部吞掉的话，现象只会是"OCR 效果莫名其妙很差"，根本查不到根因。
        logger.warning("AI 图片解析失败，降级到本地 OCR：%s", e)
    #如果 AI 解析出错，就直接跳过，进入 OCR 方案。
    try:
        img = Image.open(file_path)
        text = normalize_text(_ocr_with_tesseract(img))
        fields = parse_resume_fields(text)
        return build_resume_result(text, fields, source="ocr")
    except Exception as e:
        raise RuntimeError(f"图片解析失败：{e}") from e

#根据文件扩展名，自动选择对应的简历解析方式：PDF、DOCX、图片。
def extract_resume_from_file(file_path: str, original_filename: str = "") -> dict:
    ext = os.path.splitext(original_filename or file_path)[1].lower()#提取文件扩展名，并转成小写。

    if ext == ".pdf":
        text = extract_text_from_pdf(file_path)
        fields = parse_resume_fields(text)
        return build_resume_result(text, fields, source="pdf")

    if ext == ".docx":
        text = extract_text_from_docx(file_path)
        fields = parse_resume_fields(text)
        return build_resume_result(text, fields, source="docx")

    if ext in [".png", ".jpg", ".jpeg"]:
        return extract_text_from_image(file_path)

    raise ValueError(f"不支持的文件类型：{ext}")