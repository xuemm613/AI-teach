# AI 教育智能体

> AI 教育智能备课与个性化学习辅导系统：面向教师备课、课程知识库建设（RAG）、学生智能问答与 AI 出题练习、个性化学习 Agent 辅导的教育平台。

## 一、功能概览

| 角色 | 主要功能 |
| :--- | :--- |
| 学生 | 学习看板（今日课程安排 + 学习进度）、智能问答（**流式 Markdown 回答**）、AI 出题练习（答错自动推荐相似例题）、个性化学习辅导方案、错题本、学习记录 |
| 教师 | 教师首页（今日安排）、智能备课（生成/编辑/导出教案）、知识库管理（上传文档 → 向量化 → **RAG 问答**）、班级管理与学生学情分析、个人中心 |
| 管理员 | 数据看板、用户管理（教师/学生）、班级管理、课表管理、题库管理、系统登录记录 |

## 二、技术栈

- **前端**：Vue 3（Composition API）+ Vite + Element Plus + Pinia + ECharts
- **后端**：Python 3.10+ / FastAPI（异步）+ SQLAlchemy 2.0
- **数据库**：MySQL 8（utf8mb4）
- **向量检索**：Milvus Lite（本地，后端启动自动创建集合，无需 Docker；不可用时自动降级本地向量存储）
- **嵌入模型**：本地 sentence-transformers 模型（`E:/Models/ritrievev1`，输出 1792 维）
- **大模型**：兼容 OpenAI 接口（DeepSeek / 通义千问 / 智谱 GLM 等）

## 三、目录结构

```text
project-root/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI 入口（路由、审计日志、异常处理、启动初始化）
│   │   ├── api/
│   │   │   ├── deps.py            # JWT 校验、角色守卫
│   │   │   ├── subject_utils.py   # 固定 13 门学科 + 教师科目权限
│   │   │   └── v1/                # auth / users / knowledge / qa / lesson / tutor / admin
│   │   ├── core/                  # config / database / security / llm / embedding_service / milvus_client
│   │   ├── models/                # SQLAlchemy ORM（users/teachers/students/classes/...）
│   │   ├── schemas/               # Pydantic 请求/响应模型
│   │   ├── services/              # rag_service / lesson_service / agent_service
│   │   └── utils/                 # 文档解析 / 文本切分 / 提示词模板 / 默认管理员种子
│   ├── .env.example               # 环境变量模板（复制为 .env 后修改）
│   ├── requirements.txt           # Python 依赖
│   └── uploads/                   # 上传文件（运行时自动创建）
├── frontend/
│   ├── src/
│   │   ├── api/                   # 接口封装
│   │   ├── components/            # MarkdownView / CitationList
│   │   ├── router/  stores/  constants.js / App.vue / main.js / style.css
│   │   └── views/                 # student(4) / teacher(5) / admin(6) / Login
│   ├── package.json
│   └── vite.config.js             # 开发代理：/api、/uploads → http://localhost:8000
└── scripts/
    ├── init_mysql.sql             # ★ 初始化数据库（建库建表，首次使用执行一次）
    └── seed_data.sql              # ★ 示例数据（默认账号 + 演示教师/学生/班级/课程/题目）
```

## 四、环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8（本机安装并启动服务）
- 本地嵌入模型目录 `E:\Models\ritrievev1`（或修改 `backend/.env` 的 `EMBEDDING_MODEL_NAME` 指向其它模型）
- 可访问的大模型 API（`.env` 中配置 Key，如 DeepSeek）

## 五、快速开始

### 1. 安装依赖

```bash
# 后端
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 前端
cd ../frontend
npm install
```

### 2. 配置后端

```bash
cd backend
copy .env.example .env            # Windows
# 编辑 .env，至少修改：
#   DATABASE_URL        MySQL 连接串（账号/密码/库名）
#   LLM_API_KEY / LLM_API_BASE / LLM_MODEL_NAME   大模型配置
#   EMBEDDING_MODEL_NAME  本地嵌入模型路径（默认 E:/Models/ritrievev1）
```

### 3. 初始化数据库

```bash
# ① 建库建表（首次使用执行一次，可重复执行）
mysql -u root -p < scripts/init_mysql.sql

# ② 导入示例数据（默认账号 + 演示数据，可重复执行）
mysql -u root -p ai_edu < scripts/seed_data.sql
```

### 4. 启动后端（端口 8000）

```bash
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

启动时会自动：初始化数据表（幂等）、加载本地嵌入模型、创建向量集合、确保默认管理员存在。

### 5. 启动前端（端口 5173）

```bash
cd frontend
npm run dev
```

浏览器打开 `http://localhost:5173`。

### 6. 默认账号

| 角色 | 登录标识 | 密码 |
| :--- | :--- | :--- |
| 管理员 | `admin` | `admin123` |
| 教师 | 工号 `t260001`（teacher1） | `teacher123` |
| 学生 | 学号 `S100001`（student1） | `student123` |

> 登录规则：**教师使用工号登录、学生使用学号登录、管理员使用用户名登录**（学生/教师不再使用用户名登录）。

### 7. 加载测试数据（可选）

如需查看带数据的展示效果（学习记录、错题本、教案、知识库文件、班级课表等），先配置好 `.env` 并启动 MySQL，再执行：

```bash
cd backend
.venv\Scripts\activate              # Windows（Linux/macOS：source .venv/bin/activate）
python ../scripts/seed_demo_data.py # 幂等，可重复执行
```

## 六、主要功能说明

### 学生端
- **学习看板**：个人信息、今日课程安排（按所在班级课表自动读取今天要上的课）、学习进度概览。
- **智能问答**：选择固定科目 + 输入章节 → 大模型**流式逐字回答**（Markdown 格式，表格/公式正常显示）；支持多轮追问、语音输入、收藏错题。
- **AI 出题练习**：按科目/章节生成题目并入库；答错后自动推荐相似例题，点击下一题为相似例题。
- **学情分析**：个性化学习 Agent 辅导方案（生成过一次后一直展示，再次点击才重新生成，生成过程显示进度提示）；学习统计/错题本/学习记录。
- **个人中心**：头像、资料、密码、学号、班级与任课教师。

### 教师端
- **教师首页**：个人信息（含工号/职称/教研组）、统计、**今日安排**（自动取今天星期，按班级课表查询自己上课的课）。
- **智能备课**：选固定科目（仅限负责科目）+ 年级/章节/目标 → 生成结构化教案，可编辑、导出 Word、历史检索。
- **知识库管理**：学科固定为当前教师负责科目（不可选）；上传 PDF/Word/TXT/MD 后**自动轮询刷新状态**；右侧**RAG 问答**（基于向量化知识库，带引用来源；无命中不显示来源）。
- **班级管理/学情**：班级列表、详情、学生学情分析（雷达图/错题/趋势）。
- **个人中心**：头像、资料、密码、工号、职称、教研组。

### 管理员端
- **数据看板**：用户角色分布、每日答题量、活跃用户。
- **用户管理**：教师（工号自动生成 t26xxxx、职称/教研组下拉、负责科目单选、可删除）、学生（学号自动分配、转班仅限同年级、编辑可改年级并选择同年级转入班级）。
- **班级管理**：创建/编辑/删除班级、成员管理（一名学生只能在一个班级，学生年级需与班级年级一致；班级名称唯一、一位老师只能担任一个班级班主任）。
- **课表管理**：按班级设置科目 + 上课老师（单选，每天固定 8 节）；同一老师同一时段不能上两个班；该科目无可安排老师时不允许其他科目老师代课。
- **题库管理**：增删改（列表只显示最近 100 条，其余可筛选查询），按科目自动关联课程。
- **系统登录记录**：显示何时（年-月-日 时:分）哪位用户（工号/学号 + 姓名）登录系统。

### 全局规则
- 固定 13 门学科：语文、数学、英语、物理、化学、生物、政治、地理、历史、体育、音乐、美术、劳动（全部下拉选择，不允许自定义）。
- 唯一性：教师工号唯一、学生学号唯一、班级名称唯一、班级编号唯一；用户名允许重复。

## 七、API 一览（`/api/v1`，统一 `{code, message, data}`）

| 模块 | 主要接口 |
| :--- | :--- |
| auth | 注册（学生选年级、教师选学科）、登录（学号/工号/用户名）、刷新 Token |
| users | 个人信息、学生看板/问答/练习/错题/时间线、教师工作台/班级/学情、管理员用户管理 |
| knowledge | 上传/列表/删除知识文件、RAG 问答、知识检索 |
| qa | 流式问答（SSE）、会话管理、收藏 |
| lesson | 教案生成/列表/编辑/导出/删除 |
| tutor | 学情分析（生成/获取最近方案）、错因分析、AI 出题、只读 SQL 查询 |
| admin | 数据看板、班级/课表/题库 CRUD、学生转班、登录记录 |

## 八、常见问题

1. **上传文件一直“处理中”或“失败”**：
   - 首次处理需要加载本地嵌入模型，会稍慢（正常现象，稍候自动刷新）。
   - 失败原因会显示在“状态”标签上（悬停可见）：若提示“文档解析后为空”，说明该文件是扫描件/图片型或旧版 .doc，请上传文本版 .docx / .txt / .md。
   - 确认 `backend/.env` 中 `EMBEDDING_MODEL_NAME` 指向正确的本地模型路径，且 `sentence-transformers`、`pdfplumber` 已安装。

2. **RAG 问答无回答**：确认大模型 API（DeepSeek 等）可访问，且知识库中已上传并完成向量化的文件。

3. **登录失败**：教师请使用工号（如 `t260001`）、学生请使用学号（如 `S100001`）、管理员使用 `admin`。

4. **端口冲突**：后端默认 8000（前端代理指向 8000），如需改动请同步修改 `frontend/vite.config.js`。

## 九、目录与文件说明

- `scripts/init_mysql.sql`：建库建表脚本（首次使用执行；可重复执行）。
- `scripts/seed_data.sql`：示例数据（默认账号 + 演示数据；可重复执行）。
- `backend/.env`：本地环境配置（含密钥，不提交）。
- `backend/uploads/`：知识库上传文件与头像（运行时生成）。
