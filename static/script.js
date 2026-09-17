const resumeFile = document.getElementById("resumeFile");
const uploadResumeBtn = document.getElementById("uploadResumeBtn");
const uploadStatus = document.getElementById("uploadStatus");
const uploadResultList = document.getElementById("uploadResultList");

const jobForm = document.getElementById("jobForm");
const jobStatus = document.getElementById("jobStatus");

const jobSelect = document.getElementById("jobSelect");
const matchBtn = document.getElementById("matchBtn");
const refreshBtn = document.getElementById("refreshBtn");
const matchStatus = document.getElementById("matchStatus");

const selectAllResumes = document.getElementById("selectAllResumes");
const deleteSelectedBtn = document.getElementById("deleteSelectedBtn");

const resumeTable = document.getElementById("resumeTable");
const jobTable = document.getElementById("jobTable");
const matchTable = document.getElementById("matchTable");
const detailBox = document.getElementById("detailBox");
//是把页面上的输入框、按钮、表格、提示框都拿到变量里，后面方便操作。
let currentMatches = [];//匹配结果

function esc(v) {
  return String(v ?? "")//字符串转义
    .replaceAll("&", "&amp;")//把所有 & 替换为 &amp;
    .replaceAll("<", "&lt;")//把所有 < 替换为 &lt;,防止它被浏览器当作标签开始符号。
    .replaceAll(">", "&gt;");//把所有 > 替换为 &gt;
}//字符串转义，防止恶意代码,把字符串中的特殊 HTML 字符转义掉，防止插入页面时出问题。

//把“列表/数组”转换成适合展示的文本。
function joinList(arr) {
  if (!arr) return "";//如果没有数据，返回空数组。
  if (Array.isArray(arr)) return arr.join(", ");//数组转字符串。
  return String(arr);//如果 arr 不是数组，但也不是空值，就直接转成字符串
}

//从后端获取简历列表，如果失败就报错，成功就返回数组。
async function fetchResumes() {
  const res = await fetch("/api/resumes");//向后端发送一个 GET 请求，访问 /api/resumes
  const data = await res.json();//把响应转成 JSON
  if (!data.success) throw new Error(data.error || "获取简历失败");//throw,主动抛出一个错误,停止当前代码执行，并把错误信息抛给调用者。
  return data.data || [];
}

//从后端获取岗位列表，如果失败就报错，成功就返回数组。
async function fetchJobs() {
  const res = await fetch("/api/jobs");
  const data = await res.json();
  if (!data.success) throw new Error(data.error || "获取岗位失败");
  return data.data || [];//如果成功，就返回数据
}
//根据每个简历复选框的勾选状态，自动更新“全选”复选框的状态
function updateSelectAllState() {
  const checkboxes = document.querySelectorAll(".resume-check");//获取所有简历复选框
  const checked = document.querySelectorAll(".resume-check:checked");//获取已勾选的复选框
  selectAllResumes.checked = checkboxes.length > 0 && checked.length === checkboxes.length;//设置全选复选框的状态
  selectAllResumes.indeterminate = checked.length > 0 && checked.length < checkboxes.length;//设置半选复选框的状态
}
//把简历数组渲染成表格，并给每一行加上勾选和删除功能。,参数是简历数组
function renderResumeTable(list) {
  //把列表转成表格 HTML
  resumeTable.innerHTML = list.map(item => {
    const fields = item.fields || {};//获取简历的 fields 字段,如果没有 fields 字段，就返回空对象
    return `
      <tr>
        <td>
          <input type="checkbox" class="resume-check" data-id="${esc(item.id)}" />
        </td>
        <td>${esc(item.id)}</td>
        <td>${esc(fields["姓名"] || "")}</td>
        <td>${esc(fields["电话"] || "")}</td>
        <td>${esc(fields["邮箱"] || "")}</td>
        <td>${esc(fields["学历"] || "")}</td>
        <td>${esc(fields["学校"] || "")}</td>
        <td>${esc(fields["专业"] || "")}</td>
        <td>${esc(joinList(item.skills || []))}</td>
        <td>
          <button class="delete-btn delete-one-btn" data-id="${esc(item.id)}">删除</button>
        </td>
      </tr>
    `;
  }).join("");//把所有 <tr> 拼成一个完整字符串
  //给复选框绑定事件,当用户勾选/取消勾选某个简历时，调用：updateSelectAllState
  document.querySelectorAll(".resume-check").forEach(cb => {
    cb.addEventListener("change", updateSelectAllState);
  });
  //给删除按钮绑定事件,当用户点击删除按钮时，调用：deleteResume
  document.querySelectorAll(".delete-one-btn").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();//防止点击删除按钮时，事件传到父元素，触发别的点击逻辑。

      const resumeId = btn.dataset.id;//获取简历 id
      if (!confirm("确定要删除这份简历吗？删除后无法恢复。")) return;
      //调用后端删除接口。
      try {
        const res = await fetch(`/api/resume/${resumeId}`, {
          method: "DELETE",
        });

        const data = await res.json();//把后端返回的数据转成 JSON。
        if (!res.ok) throw new Error(data.error || "删除失败");//如果 HTTP 状态不是成功状态，就抛出错误。

        alert("删除成功");
        await refreshAll();//成功就刷新
      } catch (err) {
        alert("删除失败：" + err.message);//如果删除接口请求失败，就弹出错误提示。
      }
    });
  });

  updateSelectAllState();//表格渲染完后，重新计算“全选”框是否应该勾选或半选
}

//把 list 里的岗位数据，显示成下拉菜单中的选项。
//定义一个函数，参数 list 是岗位数组。
function renderJobOptions(list) {
  jobSelect.innerHTML = `<option value="">请选择岗位</option>` + list.map(item => {
    return `<option value="${esc(item.id)}">${esc(item.title)}</option>`;
  }).join("");
}

//把岗位数组渲染成表格
function renderJobTable(list) {
  //把 list 里的每个岗位对象，转换成一段 HTML 字符串。
  jobTable.innerHTML = list.map(item => {
    return `
      <tr>
        <td>${esc(item.id)}</td>
        <td>${esc(item.title)}</td>
        <td>${esc(item.education || "")}</td>
        <td>${esc(item.years_experience || 0)}</td>
        <td>${esc(joinList(item.must_have_skills || []))}</td>
      </tr>
    `;
  }).join("");//把 map() 生成的多个表格行拼接成一个大字符串。
}

//把一条匹配结果渲染成可读的中文详情面板。
//
// 后端返回的是英文 key——那是给接口用的契约，不应该为了好看去改它：
// script.js 里有十几处按这些 key 取值，改了 API 的 key 名页面立刻就空。
// 所以「翻译成人话」这件事放在显示层做。
function renderDetail(d) {
  const name = d.candidate_name || d.filename || "(未识别姓名)";
  const level = String(d.level || "");
  //等级配色：A 绿 / B 蓝 / C 橙 / D 红
  const levelCls = level.startsWith("A") ? "lv-a"
    : level.startsWith("B") ? "lv-b"
    : level.startsWith("C") ? "lv-c" : "lv-d";

  //基本信息。同一个字段在响应里有两种 key 名（历史遗留），这里做一次归一。
  const infoPairs = [
    ["应聘岗位", d.job_title],
    ["学历", d.candidate_edu],
    ["学校", d.candidate_school || d.school],
    ["专业", d.candidate_major || d.major],
    ["电话", d.phone || d.candidate_phone],
    ["邮箱", d.email],
  ].filter(([, v]) => v);

  //评分明细：[中文名, 得分, 满分]
  const sd = d.score_detail || {};
  const dims = [
    ["学历", sd.education_score, 20],
    ["专业", sd.major_score, 15],
    ["技能", sd.skill_score, 35],
    ["工作年限", sd.experience_score, 20],
    ["关键词", sd.keyword_score, 10],
  ];
  const penalty = Number(sd.penalty || 0);

  const dimRows = dims.map(([label, got, max]) => {
    const g = Number(got) || 0;
    const pct = max ? Math.max(0, Math.min(100, (g / max) * 100)) : 0;
    return `
      <tr>
        <td>${esc(label)}</td>
        <td class="num">${esc(g)}<span class="max"> / ${esc(max)}</span></td>
        <td class="bar-cell"><span class="bar"><i style="width:${pct}%"></i></span></td>
      </tr>`;
  }).join("");

  const penaltyRow = penalty
    ? `<tr class="penalty"><td>缺失必须技能扣分</td><td class="num">${esc(penalty)}</td><td class="bar-cell"></td></tr>`
    : "";

  //技能徽章：命中绿色、缺失红色
  const badges = (arr, cls) => (arr && arr.length)
    ? arr.map(x => `<span class="badge ${cls}">${esc(x)}</span>`).join("")
    : `<span class="badge empty">无</span>`;

  const bulletList = (arr, cls) => (arr && arr.length)
    ? `<ul class="ai-list ${cls}">${arr.map(x => `<li>${esc(x)}</li>`).join("")}</ul>`
    : "";

  //AI 建议是可选项，调用失败时后端返回空对象
  const ai = d.ai_review || {};
  const aiBlock = Object.keys(ai).length ? `
    <div class="detail-section">
      <div class="sub-title">AI 辅助建议</div>
      ${ai.ai_summary ? `<p class="ai-summary">${esc(ai.ai_summary)}</p>` : ""}
      ${ai.ai_strengths ? `<div class="ai-label">优势</div>${bulletList(ai.ai_strengths, "ok")}` : ""}
      ${ai.ai_risks ? `<div class="ai-label">风险</div>${bulletList(ai.ai_risks, "warn")}` : ""}
      ${ai.ai_suggestion ? `<p class="ai-verdict">建议：<b>${esc(ai.ai_suggestion)}</b></p>` : ""}
      ${ai.ai_note ? `<p class="ai-note">${esc(ai.ai_note)}</p>` : ""}
    </div>` : `
    <div class="detail-section">
      <div class="sub-title">AI 辅助建议</div>
      <p class="ai-note muted">未生成（模型未配置或调用失败，不影响规则评分）</p>
    </div>`;

  return `
    <div class="detail-head">
      <div class="detail-name">${esc(name)}</div>
      <div class="detail-score ${levelCls}">
        <b>${esc(d.score ?? 0)}</b><span>${esc(level)}</span>
      </div>
    </div>

    ${infoPairs.length ? `
    <div class="detail-section">
      <div class="sub-title">基本信息</div>
      <div class="kv-grid">
        ${infoPairs.map(([k, v]) => `<div><span>${esc(k)}</span>${esc(v)}</div>`).join("")}
      </div>
    </div>` : ""}

    <div class="detail-section">
      <div class="sub-title">评分明细</div>
      <table class="detail-table">
        ${dimRows}
        ${penaltyRow}
        <tr class="total"><td>最终得分</td><td class="num">${esc(d.score ?? 0)}</td><td class="bar-cell"></td></tr>
      </table>
    </div>

    <div class="detail-section">
      <div class="sub-title">技能匹配</div>
      <div class="badge-row"><em>必备·命中</em>${badges(d.matched_must_have, "ok")}</div>
      <div class="badge-row"><em>必备·缺失</em>${badges(d.missing_must_have, "miss")}</div>
      <div class="badge-row"><em>加分·命中</em>${badges(d.matched_preferred, "ok")}</div>
    </div>

    ${(d.reasons && d.reasons.length) ? `
    <div class="detail-section">
      <div class="sub-title">判定理由</div>
      ${bulletList(d.reasons, "")}
    </div>` : ""}

    ${aiBlock}
  `;
}

//把匹配结果渲染到表格里,参数是匹配结果数组
function renderMatchTable(list) {
  currentMatches = list || [];//把匹配结果保存到全局变量 currentMatches 中。
  //把每个匹配结果对象转换成表格行 HTML
  matchTable.innerHTML = list.map((item, idx) => {
    const matchedMust = item.matched_must_have || item.result?.matched_must_have || [];//取出“已匹配的必备技能”。
    const missingMust = item.missing_must_have || item.result?.missing_must_have || [];//取出“缺少的必备技能”。
    //转换成 HTML,显示在表格中
    return `
      <tr data-index="${idx}">
        <td>${idx + 1}</td>
        <td>${esc(item.candidate_name || item.filename || "")}</td>
        <td>${esc(item.score ?? item.result?.score ?? 0)}</td>
        <td>${esc(item.level || item.result?.level || "")}</td>
        <td>${esc(item.phone || item.result?.candidate_phone || "")}</td>
        <td>${esc(item.school || item.result?.candidate_school || "")}</td>
        <td>${esc(item.major || item.result?.candidate_major || "")}</td>
        <td>${esc(joinList(matchedMust))}</td>
        <td>${esc(joinList(missingMust))}</td>
      </tr>
    `;
  }).join("");//把所有表格行拼接成一个大字符串。
  //给表格行绑定点击事件,当用户点击表格行时，显示该行数据的详情。
  document.querySelectorAll("#matchTable tr").forEach(tr => {
    //用户点击某一行时，执行里面的代码。
    tr.addEventListener("click", () => {
      const idx = Number(tr.dataset.index);//获取行索引
      const detail = currentMatches[idx];//根据索引找到当前这一条完整数据。
      detailBox.innerHTML = renderDetail(detail);//渲染成中文面板，而不是直接丢原始 JSON
      detailBox.scrollTop = 0;
    });
  });
}

//刷新所有数据
async function refreshAll() {
  try {
    const [resumes, jobs] = await Promise.all([fetchResumes(), fetchJobs()]);//同时请求简历和岗位数据。
    renderResumeTable(resumes);//把简历数据渲染成表格
    renderJobTable(jobs);//把岗位数据渲染成表格
    renderJobOptions(jobs);//把岗位数据渲染成下拉菜单
    //判断岗位下拉框有没有选中值
    if (jobSelect.value) {
      await loadMatches(jobSelect.value);//根据当前选中的岗位，去加载匹配结果。
    }
    //如果 try 里面有任何错误，就进入err这里。
  } catch (err) {
    matchStatus.textContent = "刷新失败：" + err.message;
  }
}

//根据岗位 ID 去加载这个岗位的匹配结果。,参数是岗位 ID
async function loadMatches(jobId) {
  //如果没有岗位 ID，就清空表格
  if (!jobId) {
    matchTable.innerHTML = "";
    detailBox.textContent = "请选择岗位后开始筛选";
    return;
  }

  const res = await fetch(`/api/jobs/${jobId}/matches`);//调用后端接口获取这个岗位的匹配结果。
  const data = await res.json();//把后端返回的数据转成 JSON。

  if (!data.success) throw new Error(data.error || "获取筛选结果失败");//如果 HTTP 状态不是成功状态，就抛出错误。
  renderMatchTable(data.results || []);//把匹配结果渲染成表格,无结果时，清空表格
}

//当用户点击全选按钮时，全选或取消所有简历的勾选
//给 selectAllResumes 这个元素绑定一个 change 事件。
selectAllResumes.addEventListener("change", () => {
  const checked = selectAllResumes.checked;//读取“全选”复选框当前是否被选中。
  //遍历所有简历的复选框，设置它们的选中状态。
  document.querySelectorAll(".resume-check").forEach(cb => {
    cb.checked = checked;//把每个简历复选框的状态设置成和“全选”复选框一样
  });
  updateSelectAllState();//更新“全选”复选框的状态。
});

//点击“删除选中”按钮后，收集所有已勾选的简历 ID，确认后发请求到后端批量删除，删除成功后刷新页面
//给“删除选中”按钮绑定点击事件
deleteSelectedBtn.addEventListener("click", async () => {
  //找到所有已经勾选的简历复选框，并把它们转成数组
  //获取每个复选框的 data-id 属性值，并转成数字
  //过滤掉非法的 ID，只保留有效数字。
  const selectedIds = Array.from(document.querySelectorAll(".resume-check:checked"))
    .map(cb => Number(cb.dataset.id))
    .filter(id => Number.isFinite(id));
  //判断有没有选中任何简历。
  if (selectedIds.length === 0) {
    alert("请先勾选要删除的简历");
    return;
  }
  //弹出一个确认框，让用户再次确认是否真的要删除。
  if (!confirm(`确定删除选中的 ${selectedIds.length} 份简历吗？删除后无法恢复。`)) {
    return;
  }
  //用于捕获删除过程中可能发生的错误。
  try {
    //发送一个 POST删除 请求到后端接口，把要删除的 ID 数组作为参数
    const res = await fetch("/api/resumes/delete-batch", {
      method: "POST",
      //设置请求头，告诉后端，我上传的是 JSON 数据
      headers: {
        "Content-Type": "application/json",
      },
      //把要删除的 ID 数组作为参数，发送给后端接口。
      body: JSON.stringify({ ids: selectedIds }),
    });

    const data = await res.json();//把后端返回的数据转成 JSON。
    if (!res.ok) throw new Error(data.error || "批量删除失败");//如果 HTTP 状态不是成功状态，就抛出错误。

    alert(`删除成功：${data.deleted_count} 份简历`);
    await refreshAll();//删除成功后，重新刷新页面上的数据。
  } catch (err) {
    alert("批量删除失败：" + err.message);//删除失败，弹出一个错误提示。
  }
});

//点击“上传简历”按钮后，收集所有上传的简历文件，并发送请求到后端批量上传，上传成功后刷新页面
//给“上传简历”按钮绑定点击事件
uploadResumeBtn.addEventListener("click", async () => {
  const files = resumeFile.files;//获取用户选择的文件列表
  //判断用户是否选择了任何文件
  if (!files || files.length === 0) {
    uploadStatus.textContent = "请先选择一个或多个简历文件";
    uploadResultList.innerHTML = "";//清空上传结果列表
    return;
  }

  //创建一个 FormData 对象，用于收集用户选择的文件
  //遍历用户选择的文件列表，把每个文件添加到 FormData 中
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  //显示上传中的提示信息。
  uploadStatus.textContent = `正在上传并解析 ${files.length} 份简历，请稍候...`;
  uploadResultList.innerHTML = "";

  try {
    //发送一个 POST 请求到后端接口，把 FormData 对象作为参数,向后端发送批量上传请求。
    const res = await fetch("/api/resumes/upload-batch", {
      method: "POST",
      body: formData,//把 FormData 对象作为参数发送给后端接口。
    });

    const data = await res.json();//把后端返回的数据转成 JSON。
    if (!res.ok) throw new Error(data.error || "批量上传失败");

    uploadStatus.textContent = `上传完成：成功 ${data.success_count} 份，失败 ${data.fail_count} 份`;//显示上传结果总统计。
    //遍历上传结果列表，生成 HTML，并显示在页面上。
    const html = (data.results || []).map(item => {
      //根据每个文件是否成功，生成不同的显示内容。
      if (item.success) {
        return `<div class="ok-line">✅ ${esc(item.filename)} 解析成功</div>`;
      }
      return `<div class="fail-line">❌ ${esc(item.filename || "未知文件")} 失败：${esc(item.error)}</div>`;
    }).join("");

    uploadResultList.innerHTML = html;//把生成的 HTML 显示到页面上。

    await refreshAll();//上传成功后，重新刷新页面上的数据。
  } catch (err) {
    uploadStatus.textContent = "错误：" + err.message;
  }
});

//给 jobForm 表单绑定 submit 提交事件,用户点击“提交”按钮时，就会执行后面的代码。
jobForm.addEventListener("submit", async (e) => {
  e.preventDefault();//阻止表单的默认提交行为。

  const formData = new FormData(jobForm);//创建一个 FormData 对象，收集用户填写的表单数据。
  const payload = Object.fromEntries(formData.entries());//把 FormData 对象转成对象。

  jobStatus.textContent = "保存岗位中...";

  try {
    //发送一个 POST 请求到后端接口，把用户填写的表单数据作为参数
    const res = await fetch("/api/jobs", {
      method: "POST",
      //设置请求头，告诉后端，我上传的是 JSON 数据
      headers: {
        "Content-Type": "application/json",
      },
      //把用户填写的表单数据作为参数，发送给后端接口。
      body: JSON.stringify(payload),
    });

    const data = await res.json();//把后端返回的数据转成 JSON。
    if (!res.ok) throw new Error(data.error || "保存岗位失败");//如果 HTTP 状态不是成功状态，就抛出错误。

    jobStatus.textContent = "岗位创建成功";
    jobForm.reset();//重置表单,让表单重新填写
    await refreshAll();//保存成功后，重新刷新页面上的数据。
    jobSelect.value = String(data.job.id);//把下拉框的选项切换到刚创建的岗位
    await loadMatches(data.job.id);//用户创建岗位后，页面会立即显示这个岗位的筛选结果
  } catch (err) {
    jobStatus.textContent = "错误：" + err.message;
  }
});

//给“筛选”按钮绑定点击事件
//用户点击“筛选”按钮后，先检查是否选中了岗位；如果选中了，就调用后端接口对全部简历进行匹配筛选，并把结果展示到页面上
matchBtn.addEventListener("click", async () => {
  const jobId = jobSelect.value;//读取当前选中的岗位 ID。
  //检查是否选中了岗位
  if (!jobId) {
    matchStatus.textContent = "请先选择一个岗位";
    return;
  }

  matchStatus.textContent = "正在筛选全部简历，请稍候...";

  try {
    //发送一个 POST 请求到后端接口，把当前选中的岗位 ID 作为参数,让后端根据这个岗位去匹配所有简历
    const res = await fetch(`/api/jobs/${jobId}/match`, {
      method: "POST",
    });
    const data = await res.json();//把后端返回的数据解析成 JSON 对象

    //检查请求是否成功
    if (!res.ok) throw new Error(data.error || "筛选失败");

    matchStatus.textContent = `筛选完成，共 ${data.total} 份简历`;
    renderMatchTable(data.results || []);//把筛选结果渲染到表格中。
  } catch (err) {
    //如果上面任意一步出错，就进入这里
    matchStatus.textContent = "错误：" + err.message;
  }
});

//当用户切换岗位下拉框时，自动重新加载这个岗位对应的简历匹配结果。
//函数会自动调用 loadMatches() 函数
//给岗位下拉框 jobSelect 绑定 change 事件
jobSelect.addEventListener("change", async () => {
  try {
    await loadMatches(jobSelect.value);//重新加载当前选中的岗位的匹配结果
  } catch (err) {
    matchStatus.textContent = "错误：" + err.message;
  }
});

//给“刷新”按钮绑定点击事件,当用户点击“刷新”按钮时，会重新加载页面上的数据。
refreshBtn.addEventListener("click", async () => {
  await refreshAll();
});

window.addEventListener("load", async () => {
  await refreshAll();
});
//当整个页面及其资源都加载完成后，自动执行 refreshAll()，初始化并刷新页面数据。