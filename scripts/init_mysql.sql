-- ============================================================================
-- AI 教育智能备课与个性化学习辅导智能体 - MySQL 8 建表脚本
-- 运行方式（先启动 MySQL 服务，再以 root 或具备建库权限的账号执行）：
--   mysql -u root -p < scripts/init_mysql.sql
--
-- 设计说明：
--   1) 幂等：表使用 CREATE TABLE IF NOT EXISTS，可重复执行；示例数据见 scripts/seed_data.sql。
--   2) 引擎必须用 InnoDB：MySQL 只有 InnoDB 支持外键约束。
--   3) 字符集用 utf8mb4：完整 Unicode，支持中文与 emoji；
--      MySQL 的 utf8 实际是 utf8mb3（3 字节），会丢失部分字符。
--   4) learning_records 不建 (student_id, exercise_id, created_at) 唯一约束：
--      MySQL DATETIME 默认秒级精度，同一秒重复作答会撞唯一索引，学习记录应允许多次作答。
--   5) 默认账号与示例数据见 scripts/seed_data.sql。
-- ============================================================================

CREATE DATABASE IF NOT EXISTS ai_edu CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ai_edu;
SET NAMES utf8mb4;

-- ---------- 用户表（admin / teacher / student 三种角色） ----------
CREATE TABLE IF NOT EXISTS `users` (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(64)  NOT NULL,          -- 用户名允许重复（教师由工号唯一确定）
    password_hash VARCHAR(255) NOT NULL,
    email         VARCHAR(128) UNIQUE,
    full_name     VARCHAR(64),
    role          VARCHAR(16)  NOT NULL DEFAULT 'student',
    avatar        VARCHAR(255),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_users_role (role),
    KEY idx_users_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 教师扩展表 ----------
CREATE TABLE IF NOT EXISTS `teachers` (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT NOT NULL UNIQUE REFERENCES `users`(id) ON DELETE CASCADE,
    employee_no VARCHAR(32) NOT NULL UNIQUE, -- 工号（唯一，教师主标识）
    subjects   JSON DEFAULT (JSON_ARRAY()),   -- 负责科目（如 ["数学","物理"]）
    title      VARCHAR(64),
    department VARCHAR(128),
    bio        TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 学生扩展表 ----------
CREATE TABLE IF NOT EXISTS `students` (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT NOT NULL UNIQUE REFERENCES `users`(id) ON DELETE CASCADE,
    student_no VARCHAR(32) NOT NULL UNIQUE, -- 学号唯一（学生主标识）
    grade      VARCHAR(32),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_students_student_no (student_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 班级（关联教师 users.id） ----------
CREATE TABLE IF NOT EXISTS `classes` (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(64) NOT NULL,
    class_no    VARCHAR(32) UNIQUE,       -- 班级编号唯一
    teacher_id  INT NOT NULL REFERENCES `users`(id) ON DELETE CASCADE,
    grade       VARCHAR(32),
    description TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_classes_teacher (teacher_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 班级课表（weekday×period 单元格为科目） ----------
CREATE TABLE IF NOT EXISTS `class_schedules` (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    class_id   INT NOT NULL REFERENCES `classes`(id) ON DELETE CASCADE,
    weekday    INT NOT NULL,              -- 1-7 周一~周日
    period     INT NOT NULL,              -- 第几节
    subject    VARCHAR(32),               -- 系统固定科目或空
    UNIQUE KEY uq_schedule_cell (class_id, weekday, period)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 课表单元格的可代课老师（一节课可有多个可代课老师） ----------
CREATE TABLE IF NOT EXISTS `class_schedule_teachers` (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    schedule_id     INT NOT NULL REFERENCES `class_schedules`(id) ON DELETE CASCADE,
    teacher_user_id INT NOT NULL REFERENCES `users`(id) ON DELETE CASCADE,
    KEY idx_schedule_teachers_schedule (schedule_id),
    KEY idx_schedule_teachers_teacher (teacher_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 班级-学生 关联表 ----------
CREATE TABLE IF NOT EXISTS `class_students` (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    class_id   INT NOT NULL REFERENCES `classes`(id) ON DELETE CASCADE,
    student_id INT NOT NULL REFERENCES `students`(id) ON DELETE CASCADE,
    UNIQUE KEY uq_class_student (class_id, student_id),
    KEY idx_class_students_class (class_id),
    KEY idx_class_students_student (student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 课程（含章节树 JSON） ----------
CREATE TABLE IF NOT EXISTS `courses` (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(128) NOT NULL,
    grade        VARCHAR(32),
    subject      VARCHAR(32),
    teacher_id   INT REFERENCES `users`(id) ON DELETE SET NULL,
    chapter_tree JSON DEFAULT (JSON_ARRAY()),
    description  TEXT,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 题库（题目/选项/答案/解析/难度/知识点标签） ----------
CREATE TABLE IF NOT EXISTS `exercises` (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    course_id        INT REFERENCES `courses`(id) ON DELETE SET NULL,
    chapter          VARCHAR(128),                  -- 章节
    `type`           VARCHAR(16) NOT NULL DEFAULT 'single',  -- single/multiple/judge/fill/qa
    content          TEXT NOT NULL,
    options          JSON DEFAULT (JSON_ARRAY()),            -- [{"key":"A","text":"..."}]
    answer           TEXT,
    analysis         TEXT,
    difficulty       VARCHAR(16) NOT NULL DEFAULT 'medium',  -- easy/medium/hard
    knowledge_points JSON DEFAULT (JSON_ARRAY()),            -- ["知识点1","知识点2"]
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_exercises_course (course_id),
    KEY idx_exercises_difficulty (difficulty)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 学习记录（学生答题历史、正确与否；允许同一题多次作答，不建时间唯一约束） ----------
CREATE TABLE IF NOT EXISTS `learning_records` (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    student_id       INT NOT NULL REFERENCES `students`(id) ON DELETE CASCADE,
    exercise_id      INT NOT NULL REFERENCES `exercises`(id) ON DELETE CASCADE,
    user_answer      TEXT,
    is_correct       BOOLEAN NOT NULL DEFAULT FALSE,
    duration_seconds INT,
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_learning_records_student (student_id),
    KEY idx_learning_records_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 错题本 ----------
CREATE TABLE IF NOT EXISTS `wrong_book` (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    student_id  INT NOT NULL REFERENCES `students`(id) ON DELETE CASCADE,
    exercise_id INT NOT NULL REFERENCES `exercises`(id) ON DELETE CASCADE,
    reason      TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_wrong_book (student_id, exercise_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 教案记录（结构化 JSON） ----------
CREATE TABLE IF NOT EXISTS `lesson_plans` (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    teacher_id          INT NOT NULL REFERENCES `users`(id) ON DELETE CASCADE,
    grade               VARCHAR(32) NOT NULL,
    subject             VARCHAR(32) NOT NULL,
    chapter             VARCHAR(128) NOT NULL,
    teaching_objectives TEXT,
    content             JSON,
    status              VARCHAR(16) NOT NULL DEFAULT 'generated',
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_lesson_plans_teacher (teacher_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 知识库文件记录 ----------
CREATE TABLE IF NOT EXISTS `knowledge_files` (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    filename    VARCHAR(255) NOT NULL,
    file_key    VARCHAR(64) NOT NULL UNIQUE,     -- 存储文件唯一标识（uuid 文件名）
    file_type   VARCHAR(16) NOT NULL,            -- pdf/docx/txt/md
    subject     VARCHAR(64),                  -- 所属科目（教师只能建/管本科目）
    file_path   VARCHAR(512) NOT NULL,
    file_size   INT NOT NULL DEFAULT 0,
    status      VARCHAR(16) NOT NULL DEFAULT 'pending',  -- pending/indexed/failed
    chunk_count INT NOT NULL DEFAULT 0,
    error       TEXT,
    uploaded_by INT REFERENCES `users`(id) ON DELETE SET NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 问答会话（多轮） ----------
CREATE TABLE IF NOT EXISTS `chat_sessions` (
    id         VARCHAR(36) PRIMARY KEY,
    user_id    INT NOT NULL REFERENCES `users`(id) ON DELETE CASCADE,
    title      VARCHAR(128) NOT NULL DEFAULT '新对话',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_chat_sessions_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 问答消息（含引用来源 JSON） ----------
CREATE TABLE IF NOT EXISTS `chat_messages` (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL REFERENCES `chat_sessions`(id) ON DELETE CASCADE,
    role       VARCHAR(16) NOT NULL,             -- user / assistant
    content    TEXT NOT NULL,
    sources    JSON DEFAULT (JSON_ARRAY()),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_chat_messages_session (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 个性化学习 Agent 任务记录 ----------
CREATE TABLE IF NOT EXISTS `agent_tasks` (
    id         VARCHAR(36) PRIMARY KEY,
    student_id INT REFERENCES `students`(id) ON DELETE CASCADE,
    user_id    INT NOT NULL REFERENCES `users`(id) ON DELETE CASCADE,
    task_type  VARCHAR(32) NOT NULL DEFAULT 'personalized_plan',
    input_data JSON DEFAULT (JSON_OBJECT()),
    output     JSON DEFAULT (JSON_OBJECT()),
    steps      JSON DEFAULT (JSON_ARRAY()),
    status     VARCHAR(16) NOT NULL DEFAULT 'running',   -- running/completed/failed
    error      TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_agent_tasks_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;



-- ---------- 教师给学生留言 ----------
CREATE TABLE IF NOT EXISTS `student_messages` (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL REFERENCES `students`(id) ON DELETE CASCADE,
    teacher_id INT NOT NULL REFERENCES `users`(id) ON DELETE CASCADE,
    content    TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_student_messages_student (student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 系统操作日志 ----------
CREATE TABLE IF NOT EXISTS `system_logs` (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT REFERENCES `users`(id) ON DELETE SET NULL,
    username   VARCHAR(64),
    action     VARCHAR(128) NOT NULL,
    detail     TEXT,
    ip         VARCHAR(64),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_system_logs_user (user_id),
    KEY idx_system_logs_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
