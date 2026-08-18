import json
import sqlite3
from datetime import datetime

from config import DB_PATH

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
#封装了 SQLite 数据库的创建/连接逻辑，并通过设置 row_factory 让查询结果可以用字段名（如 row["姓名"]）访问

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    #init_db() 通过 get_conn() 拿到数据库连接，再用 .cursor() 创建游标，之后拿着这个 cur 执行建表等 SQL 语句，完成数据库的初始化工作。

    cur.execute("""
    CREATE TABLE IF NOT EXISTS resumes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        saved_as TEXT,
        file_path TEXT,
        source TEXT,
        raw_text TEXT,
        fields_json TEXT,
        skills_json TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,


        title TEXT NOT NULL,
        education TEXT,
        years_experience INTEGER DEFAULT 0,
        must_have_skills TEXT,
        preferred_skills TEXT,
        major_keywords TEXT,
        keywords TEXT,
        description TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        resume_id INTEGER NOT NULL,
        score INTEGER NOT NULL,
        level TEXT NOT NULL,
        result_json TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(job_id, resume_id)
    )
    """)

    conn.commit()
    conn.close()
    #关闭与数据库文件的连接，释放系统资源。

def save_resume(resume: dict) -> int:#将简历数据存入数据库的函数，返回新插入记录的 ID
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO resumes (filename, saved_as, file_path, source, raw_text, fields_json, skills_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            resume.get("filename", ""),#从字典安全取值，如果键不存在则返回空字符串 ""
            resume.get("saved_as", ""),
            resume.get("file_path", ""),
            resume.get("source", ""),
            resume.get("raw_text", ""),
            json.dumps(resume.get("fields", {}), ensure_ascii=False),#将 Python 对象（字典、列表）转为 JSON 字符串
            json.dumps(resume.get("skills", []), ensure_ascii=False),
            datetime.now().isoformat(timespec="seconds"),#生成当前时间字符串，精确到秒
        ),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid
#提交并获取新记录 ID

#获取所有简历列表
def list_resumes():
    conn = get_conn()#函数获取数据库连接对象，赋值给变量 conn
    cur = conn.cursor()
    rows = cur.execute("SELECT * FROM resumes ORDER BY id DESC").fetchall()#将获取到的所有行数据存储到变量 rows 中。
    conn.close()#关闭数据库连接，释放资源。

    result = []#创建一个空列表 result，用于存储最终处理后的数据。
    for row in rows:#遍历查询结果的每一行，每次循环 row 代表一条简历记录。
        item = dict(row)#将行对象转换为字典。
        item["fields"] = json.loads(item.pop("fields_json") or "{}")#把数据库中存储的 JSON 格式字符串 fields_json 解析成 Python 字典，并用键名 fields 存放，同时删掉原始的 fields_json 键。
        item["skills"] = json.loads(item.pop("skills_json") or "[]")#把数据库中的 JSON 格式技能字符串转换成 Python 列表，用键名 skills 存放，同时删掉原始的 skills_json 键。
        result.append(item)#将处理后的数据添加到 result 列表中。
    return result

#定义一个名为 get_resume 的函数，接收一个参数 resume_id，类型注解标明应为整数（int），用于根据ID获取单条简历。
def get_resume(resume_id: int):
    conn = get_conn()#调用 get_conn() 获取数据库连接对象
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()#通过 SQL 语句从数据库中查询指定 ID 的简历数据
    conn.close()
    if not row:#如果没有查询到结果，则返回 None
        return None

    item = dict(row)#将行对象转换为字典，方便用键名访问各字段的值。
    item["fields"] = json.loads(item.pop("fields_json") or "{}")#把数据库中存储的 JSON 字符串字段取出、解析成 Python 对象，同时把键名从 fields_json 改为 fields。
    item["skills"] = json.loads(item.pop("skills_json") or "[]")#同理
    return item


#定义一个名为 save_job 的函数，接收一个字典类型的参数 job，返回值类型是整数（int），用于保存职位信息并返回新记录的ID。
def save_job(job: dict) -> int:
    conn = get_conn()#获取数据库连接对象
    cur = conn.cursor()#创建游标对象
    #向 jobs 表中插入数据，指定9个列名。
    cur.execute(
        """
        INSERT INTO jobs (title, education, years_experience, must_have_skills, preferred_skills, major_keywords, keywords, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ? ,?)
        """,
        (
            job.get("title", ""),#获取职位标题，如果 job 字典中没有 "title" 这个键，默认使用空字符串 ""
            job.get("education", ""),#获取学历信息
            int(job.get("years_experience") or 0),#获取工作年限,强制转换为整数，确保存入数据库的是数字类型。
            json.dumps(job.get("must_have_skills", []), ensure_ascii=False),#把 Python 对象转换成 JSON 字符串,用键名 must_have_skills 存放，同时删掉原始的 must_have_skills 键。
            json.dumps(job.get("preferred_skills", []), ensure_ascii=False),
            json.dumps(job.get("major_keywords", []), ensure_ascii=False),
            json.dumps(job.get("keywords", []), ensure_ascii=False),
            job.get("description", ""),#职位描述
            datetime.now().isoformat(timespec="seconds"),#生成当前时间字符串，精确到秒
        ),
    )
    conn.commit()#提交事务,确定数据已保存。
    jid = cur.lastrowid#获取刚插入记录的自增ID（即 id 字段的值），赋给变量 jid。
    conn.close()
    return jid#返回新插入记录的ID，调用者可以用这个ID来标识刚保存的职位。

def list_jobs():
    conn = get_conn()
    cur = conn.cursor()
    rows = cur.execute("SELECT * FROM jobs ORDER BY id DESC").fetchall()
    #查询 jobs 表中所有字段、所有记录,按 id 倒序排列，也就是最新的记录排在前面
    conn.close()

    result = []#创建一个空列表，用于存储处理后的数据。
    for row in rows:#遍历每一条查询结果 row
        item = dict(row)#将行对象转换为字典
        item["must_have_skills"] = json.loads(item.pop("must_have_skills") or "[]")#取出并删除字典中的 must_have_skills 字段
        item["preferred_skills"] = json.loads(item.pop("preferred_skills") or "[]")#同理
        item["major_keywords"] = json.loads(item.pop("major_keywords") or "[]")
        item["keywords"] = json.loads(item.pop("keywords") or "[]")
        result.append(item)
        #将处理后的数据添加到 result 列表中
    return result

#定义一个名为 get_job 的函数，接收一个参数 job_id，类型注解标明为整数（int），用于根据ID获取单条职位信息。
def get_job(job_id: int):
    conn = get_conn()
    cur = conn.cursor()
    #查询 jobs 表中 id 等于 job_id 的那一条记录
    row = cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()#关闭数据库连接
    if not row:
        return None

    item = dict(row)#将行对象转换为字典
    item["must_have_skills"] = json.loads(item.pop("must_have_skills") or "[]")#把 must_have_skills 字段取出、转换成 Python 对象，并删除原始的 must_have_skills 字段
    item["preferred_skills"] = json.loads(item.pop("preferred_skills") or "[]")#同理
    item["major_keywords"] = json.loads(item.pop("major_keywords") or "[]")
    item["keywords"] = json.loads(item.pop("keywords") or "[]")#把 keywords 字段取出、转换成 Python 对象，并删除原始的 keywords 字段
    return item#返回处理后的数据

#定义一个名为 save_match 的函数，接收4个参数 job_id、resume_id、score、level、result，返回值类型是布尔值（bool），用于保存职位匹配结果。
def save_match(job_id: int, resume_id: int, score: int, level: str, result: dict):
    conn = get_conn()
    cur = conn.cursor()
    #插入 matches 表中数据,职位ID、简历ID、得分、匹配等级、结果JSON字符串、创建时间,如果发生冲突，就用新数据覆盖旧数据：
    cur.execute(
        """
        INSERT INTO matches (job_id, resume_id, score, level, result_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id, resume_id) DO UPDATE SET
            score = excluded.score,
            level = excluded.level,
            result_json = excluded.result_json,
            created_at = excluded.created_at
        """,
        #这是传给 SQL 的实际参数值，顺序要和前面的 ? 一一对应
        (
            job_id,#职位ID
            resume_id,#简历ID
            int(score),#得分
            level,#匹配等级
            json.dumps(result, ensure_ascii=False),#把 Python 对象转换成 JSON 字符串，用键名 result_json 存放，同时删掉原始的 result 字段。
            datetime.now().isoformat(timespec="seconds"),#生成当前时间字符串，精确到秒
        ),
    )
    conn.commit()#让刚才的插入/更新真正写入数据库
    conn.close()

#定义一个名为 list_matches_by_job 的函数，接收一个参数 job_id，返回值类型是列表（list），用于根据职位ID获取职位匹配结果。
def list_matches_by_job(job_id: int):
    conn = get_conn()
    cur = conn.cursor()
    #查询 matches 表中 job_id 等于 job_id 的所有记录,根据简历 ID 找到对应的简历信息
    rows = cur.execute(
        """
        SELECT m.*, r.filename, r.saved_as, r.file_path, r.source, r.fields_json, r.skills_json
        FROM matches m
        JOIN resumes r ON m.resume_id = r.id
        WHERE m.job_id = ?
        ORDER BY m.score DESC, m.id ASC
        """,
        (job_id,),#这是 SQL 查询的参数
    ).fetchall()#fetchall() 表示把所有查询结果一次性取出来,最终 rows 是一个包含多条记录的列表
    conn.close()

    result = []#创建一个空列表 result
    for row in rows:
        item = dict(row)
        item["result"] = json.loads(item.pop("result_json") or "{}")
        item["fields"] = json.loads(item.pop("fields_json") or "{}")
        item["skills"] = json.loads(item.pop("skills_json") or "[]")
        #把 result_json 字段取出、转换成 Python 对象，并删除原始的 result_json 字段
        result.append(item)#将处理后的数据添加到 result 列表中
    return result