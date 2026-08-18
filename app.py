import os
#导入 uuid4，用于生成唯一 ID。
from uuid import uuid4
#导入 pathlib，用于处理文件路径。
from pathlib import Path
#导入 Flask,Web 应用实例,渲染 HTML 模板,获取前端发来的请求数据,把 Python 字典转换成 JSON 响应返回给前端
from flask import Flask, render_template, request, jsonify
#从 config.py 里导入配置项
from config import UPLOAD_FOLDER, MAX_CONTENT_LENGTH, AUTO_DELETE_AFTER_PROCESS
# 业务服务导入
from services.resume_service import process_resume
#导入简历评分函数
from services.scoring_service import score_resume_against_job
#数据库服务导入
from services.db_service import (
    init_db,#初始化数据库
    save_resume,#保存简历
    list_resumes,#获取简历列表
    get_resume,#根据 ID 或其他条件获取某一份简历
    save_job,#保存职位信息
    list_jobs,#列出所有职位信息
    get_job,#根据 ID 或其他条件获取某份职位信息
    save_match,#保存匹配结果
    list_matches_by_job,#根据职位 ID 获取职位匹配结果
    get_conn,#获取数据库连接对象
)
#把列表文本统一拆分成去重后的字符串列表
from utils.text_utils import split_list_text

#把 Web 程序启动前的基础环境先准备好。
app = Flask(__name__)#创建 Flask 应用实例
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER#设置上传文件保存路径
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH#设置上传文件大小限制

os.makedirs(UPLOAD_FOLDER, exist_ok=True)#如果上传目录不存在，就自动创建
init_db()#初始化数据库

ALLOWED_EXTENSIONS = {"pdf", "docx", "png", "jpg", "jpeg"}#允许上传的文件类型

@app.route("/")#路由装饰器开始
#定义首页函数，并返回 index.html 页面给用户
def index():
    return render_template("index.html")

@app.route("/api/resumes/upload", methods=["POST"])#定义一个“上传简历”的 POST 接口路由。
#那么前端上传简历文件时，发送 POST 请求到这个地址，就会触发 upload_resume()。
#单文件简历上传接口
def upload_resume():
    """
    单文件上传，保留兼容
    """
    save_path = None#初始化保存路径
    #检查是否有上传文件
    if "file" not in request.files:
        return jsonify({"error": "没有上传文件"}), 400

    file = request.files["file"]#取出文件对象
    #检查文件名是否为空
    if not file.filename:
        return jsonify({"error": "文件名为空"}), 400

    #获取原始文件名和后缀
    original_filename = file.filename
    suffix = Path(original_filename).suffix.lower()
    #检查文件类型是否允许
    if suffix.lstrip(".") not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"不支持的文件类型：{suffix}"}), 400

    #生成新文件名
    save_name = f"{uuid4().hex}{suffix}"
    #生成保存路径
    save_path = os.path.join(UPLOAD_FOLDER, save_name)

    try:
        # 保存文件到本地
        file.save(save_path)
        #调用简历解析函数
        parsed = process_resume(save_path, original_filename=original_filename)
        #这里把解析结果整理成一个字典，准备保存到数据库
        resume_data = {
            "filename": original_filename,
            "saved_as": save_name,
            "file_path": save_path,
            "source": parsed.get("source", "unknown"),
            "raw_text": parsed.get("text", ""),
            "fields": parsed.get("fields", {}),
            "skills": parsed.get("skills", []),
        }
        #保存到数据库
        #把 ID 放回数据里
        resume_id = save_resume(resume_data)
        resume_data["id"] = resume_id
        #返回 JSON 给前端，说明上传和解析都成功了
        return jsonify({
            "success": True,
            "message": "上传并解析成功",
            "resume": resume_data,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    #不管成功还是失败，最后都会执行这里
    finally:
        #如果配置 AUTO_DELETE_AFTER_PROCESS 为 True，就删除刚才保存的临时文件
        if AUTO_DELETE_AFTER_PROCESS and save_path and os.path.exists(save_path):
            try:
                os.remove(save_path)
                #把服务器上的临时上传文件删掉
            except Exception:
                pass

#批量上传简历接口
@app.route("/api/resumes/upload-batch", methods=["POST"])
def upload_resume_batch():
    """
    批量上传简历
    前端字段名：files
    """
    #从请求中取出名为 files 的所有文件
    files = request.files.getlist("files")
    #检查是否有文件
    if not files:
        return jsonify({"error": "没有上传任何文件"}), 400

    results = []
    success_count = 0
    fail_count = 0
    #遍历所有文件
    for file in files:
        save_path = None
        #如果某个文件没有名字，就认为它失败
        if not file.filename:
            fail_count += 1
            results.append({
                "filename": "",
                "success": False,
                "error": "文件名为空"
            })
            continue
        #获取原始文件名和后缀
        original_filename = file.filename
        suffix = Path(original_filename).suffix.lower()
        #如果文件后缀不在允许列表里，就拒绝处理
        if suffix.lstrip(".") not in ALLOWED_EXTENSIONS:
            fail_count += 1
            results.append({
                "filename": original_filename,
                "success": False,
                "error": f"不支持的文件类型：{suffix}"
            })
            continue
        #生成新文件名和保存路径
        save_name = f"{uuid4().hex}{suffix}"
        save_path = os.path.join(UPLOAD_FOLDER, save_name)
        #核心处理逻辑
        try:
            file.save(save_path)
            #把上传文件写入本地。

            #调用 process_resume() 提取内容
            parsed = process_resume(save_path, original_filename=original_filename)
            #整理简历数据
            resume_data = {
                "filename": original_filename,
                "saved_as": save_name,
                "file_path": save_path,
                "source": parsed.get("source", "unknown"),
                "raw_text": parsed.get("text", ""),
                "fields": parsed.get("fields", {}),
                "skills": parsed.get("skills", []),
            }
            #把这份简历数据写入数据库，并拿到数据库生成的 id。
            #然后把 id 放回 resume_data，方便前端使用
            resume_id = save_resume(resume_data)
            resume_data["id"] = resume_id
            #这个文件处理成功，就加入结果列表，并把成功数加 1
            results.append({
                "filename": original_filename,
                "success": True,
                "resume": resume_data
            })
            success_count += 1
        #异常处理
        except Exception as e:
            results.append({
                "filename": original_filename,
                "success": False,
                "error": str(e)
            })
            fail_count += 1#失败数加 1
        #不管成功还是失败，最后都尝试删除临时文件
        finally:
            if AUTO_DELETE_AFTER_PROCESS and save_path and os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except Exception:
                    pass

    #接口最终返回批量处理的整体结果
    return jsonify({
        "success": True,
        "message": "批量上传完成",
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results
    })
#获取简历列表的接口。
@app.route("/api/resumes", methods=["GET"])
def api_resumes():
    return jsonify({"success": True, "data": list_resumes()})
#根据简历 ID 获取单条简历详情，如果不存在就返回 404
@app.route("/api/resume/<int:resume_id>", methods=["GET"])
def api_resume_detail(resume_id: int):
    data = get_resume(resume_id)
    if not data:
        return jsonify({"error": "简历不存在"}), 404
    return jsonify({"success": True, "data": data})

##删除简历的接口
@app.route("/api/resume/<int:resume_id>", methods=["DELETE"])
def delete_resume(resume_id: int):
    #获取数据库连接，并创建游标，用来执行 SQL
    conn = get_conn()
    cur = conn.cursor()
    #先从 resumes 表里查这条简历记录，取出它的 file_path
    row = cur.execute("SELECT file_path FROM resumes WHERE id = ?", (resume_id,)).fetchone()
    #如果简历不存在
    if not row:
        conn.close()
        return jsonify({"error": "简历不存在"}), 404
    #把数据库中的文件路径拿出来，后面用于删除本地文件
    file_path = row["file_path"]
    #删除关联数据和主数据
    try:
        cur.execute("DELETE FROM matches WHERE resume_id = ?", (resume_id,))#删除所有和这份简历相关的匹配记录。
        cur.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))#删除简历数据主表
        conn.commit()#提交事务，让删除真正生效。
    finally:
        conn.close()
    #初始化文件删除状态
    file_deleted = False
    file_error = ""
    #如果文件路径存在，而且文件确实在磁盘上，就尝试删除
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            file_deleted = True
        except Exception as e:
            file_error = str(e)

    return jsonify({
        "success": True,
        "message": "简历已删除",
        "file_deleted": file_deleted,
        "file_error": file_error
    })

#批量删除简历 的接口：前端一次传入多个简历 ID，后端统一删除对应的数据库记录、关联记录以及本地文件
@app.route("/api/resumes/delete-batch", methods=["POST"])
def delete_resume_batch():
    #从请求体中读取 JSON 数据
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    #校验 ids 是否有效,提供要删除的简历ID列表
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "请提供要删除的简历ID列表"}), 400
    #把前端传来的 ID 全部转换成整数
    clean_ids = []
    for x in ids:
        try:
            clean_ids.append(int(x))
        except Exception:
            pass

    clean_ids = list(dict.fromkeys(clean_ids))  # 去重且保序
    #如果没有有效 ID，就返回 400
    if not clean_ids:
        return jsonify({"error": "没有有效的简历ID"}), 400
    #获取数据库连接，并创建游标，用来执行 SQL
    conn = get_conn()
    cur = conn.cursor()
    #动态占位符字符串
    placeholders = ",".join(["?"] * len(clean_ids))
    #从 resumes 表中查询这些 ID 的数据
    rows = cur.execute(
        f"SELECT id, file_path FROM resumes WHERE id IN ({placeholders})",
        tuple(clean_ids),
    ).fetchall()

    if not rows:
        conn.close()
        return jsonify({"error": "未找到可删除的简历"}), 404
    #提取找到的 ID 和文件路径
    found_ids = [int(row["id"]) for row in rows]
    file_paths = [row["file_path"] for row in rows if row["file_path"]]
    # 删除关联表数据和主表数据
    try:
        cur.execute(
            f"DELETE FROM matches WHERE resume_id IN ({placeholders})",#删除这些简历相关的匹配记录。
            tuple(found_ids),
        )
        cur.execute(
            f"DELETE FROM resumes WHERE id IN ({placeholders})",#删除简历主记录。
            tuple(found_ids),
        )
        conn.commit()#提交事务，让删除真正生效。
    finally:
        conn.close()
    #初始化文件删除统计
    deleted_files = 0
    failed_files = []
    #逐个删除本地文件。
    for fp in file_paths:
        if fp and os.path.exists(fp):
            try:
                os.remove(fp)
                deleted_files += 1
            except Exception as e:
                failed_files.append({"file_path": fp, "error": str(e)})

    return jsonify({
        "success": True,
        "message": "批量删除完成",
        "deleted_count": len(found_ids),
        "deleted_files": deleted_files,
        "failed_files": failed_files,
    })

"""
实现的是一个 岗位（job）接口，同时支持：
GET：获取岗位列表
POST：创建新岗位
"""
@app.route("/api/jobs", methods=["GET", "POST"])
def api_jobs():
    #如果客户端发的是 GET /api/jobs，就直接返回岗位列表。
    if request.method == "GET":
        return jsonify({"success": True, "data": list_jobs()})
    #如果是 POST 请求，先读取数据
    data = request.get_json(silent=True) or request.form.to_dict()
    #从请求数据里读取 title，并去掉两边空格
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "岗位名称不能为空"}), 400
    #组装岗位数据
    job_data = {
        "title": title,
        "education": (data.get("education") or "").strip(),
        "years_experience": int(data.get("years_experience") or 0),
        "must_have_skills": split_list_text(data.get("must_have_skills", "")),
        "preferred_skills": split_list_text(data.get("preferred_skills", "")),
        "major_keywords": split_list_text(data.get("major_keywords", "")),
        "keywords": split_list_text(data.get("keywords", "")),
        "description": (data.get("description") or "").strip(),
    }
    #保存岗位数据
    job_id = save_job(job_data)
    job_data["id"] = job_id

    return jsonify({
        "success": True,
        "message": "岗位创建成功",
        "job": job_data,
    })

#获取岗位详情
@app.route("/api/jobs/<int:job_id>", methods=["GET"])
def api_job_detail(job_id: int):
    job = get_job(job_id)#调用 get_job() 去数据库里查询这条岗位记录
    if not job:
        return jsonify({"error": "岗位不存在"}), 404
    return jsonify({"success": True, "data": job})

#把某个岗位与所有简历进行匹配打分，并返回匹配结果。
@app.route("/api/jobs/<int:job_id>/match", methods=["POST"])
def match_job(job_id: int):
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "岗位不存在"}), 404
    #获取所有简历
    resumes = list_resumes()
    results = []
    # 遍历每份简历进行匹配
    for resume in resumes:
        result = score_resume_against_job(resume, job)#调用 score_resume_against_job()

        save_match(job_id, resume["id"], result["score"], result["level"], result)#保存匹配结果
        #组装返回结果
        results.append({
            "resume_id": resume["id"],
            "filename": resume.get("filename", ""),
            "candidate_name": resume.get("fields", {}).get("姓名", ""),
            "phone": resume.get("fields", {}).get("电话", ""),
            "email": resume.get("fields", {}).get("邮箱", ""),
            "school": resume.get("fields", {}).get("学校", ""),
            "major": resume.get("fields", {}).get("专业", ""),
            "skills": resume.get("skills", []),
            **result,
        })
    #按照 score 从高到低排序。
    results.sort(key=lambda x: x["score"], reverse=True)

    return jsonify({
        "success": True,
        "job": job,
        "total": len(results),
        "results": results,
    })

#获取某个岗位的匹配结果
@app.route("/api/jobs/<int:job_id>/matches", methods=["GET"])
def get_job_matches(job_id: int):
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "岗位不存在"}), 404
    #查询该岗位的所有匹配记录
    matches = list_matches_by_job(job_id)
    return jsonify({
        "success": True,
        "job": job,
        "total": len(matches),
        "results": matches,
    })

if __name__ == "__main__":
    app.run(debug=True)