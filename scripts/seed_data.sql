-- ============================================================================
-- 示例数据：默认账号 + 演示教师/学生/班级/课程/题目（幂等，可重复执行）
-- 运行方式： mysql -u root -p ai_edu < scripts/seed_data.sql
-- 默认密码：管理员 admin123 / 教师 teacher123 / 学生 student123
-- ============================================================================
USE ai_edu;
SET NAMES utf8mb4;

-- ---------- 默认账号（管理员 / 教师 / 学生） ----------
INSERT IGNORE INTO `users` (username, password_hash, email, full_name, role, is_active) VALUES
  ('admin',    'pbkdf2_sha256$100000$P4r0IEKTDhK/CXTr5J0QAQ==$tpSdczdOeiv7aQjGNrTqec/zywmqaEjFHsMAEvFWa30=', 'admin@ai-edu.local',    '系统管理员', 'admin',   TRUE),
  ('teacher1', 'pbkdf2_sha256$100000$TPG3XbI+YcB63rfUxSklwQ==$P1HrwTK2jULcwV5aJxMXcrvIDUZUP0Gain0ntOkWzcg=', 'teacher1@ai-edu.local', '张老师',     'teacher', TRUE),
  ('student1', 'pbkdf2_sha256$100000$oyQShcQm0AShcGKAROUyKg==$tFR11gier9Qt17KnaH+BYV2NXIlE1YLedat6AWIF05o=', 'student1@ai-edu.local', '李明',       'student', TRUE);

-- 默认学生资料（学号 S100001，年级七年级）
INSERT IGNORE INTO `students` (user_id, student_no, grade)
SELECT id, 'S100001', '七年级' FROM `users` WHERE username = 'student1';

-- 默认班级：七年级1班（teacher1 班主任），student1 加入该班
INSERT IGNORE INTO `classes` (name, class_no, teacher_id, grade, description)
SELECT '七年级1班', 'C2026001', id, '七年级', '示例班级' FROM `users` WHERE username = 'teacher1';
INSERT IGNORE INTO `class_students` (class_id, student_id)
SELECT c.id, s.id FROM `classes` c JOIN `students` s ON s.student_no = 'S100001' WHERE c.name = '七年级1班';


INSERT IGNORE INTO `users` (username, password_hash, email, full_name, role, is_active) VALUES
  ('wang', 'pbkdf2_sha256$100000$TPG3XbI+YcB63rfUxSklwQ==$P1HrwTK2jULcwV5aJxMXcrvIDUZUP0Gain0ntOkWzcg=', 'wang@ai-edu.local', '王老师', 'teacher', TRUE),
  ('li',   'pbkdf2_sha256$100000$TPG3XbI+YcB63rfUxSklwQ==$P1HrwTK2jULcwV5aJxMXcrvIDUZUP0Gain0ntOkWzcg=', 'li@ai-edu.local',   '李老师', 'teacher', TRUE),
  ('zhao', 'pbkdf2_sha256$100000$TPG3XbI+YcB63rfUxSklwQ==$P1HrwTK2jULcwV5aJxMXcrvIDUZUP0Gain0ntOkWzcg=', 'zhao@ai-edu.local', '赵老师', 'teacher', TRUE),
  ('qian', 'pbkdf2_sha256$100000$TPG3XbI+YcB63rfUxSklwQ==$P1HrwTK2jULcwV5aJxMXcrvIDUZUP0Gain0ntOkWzcg=', 'qian@ai-edu.local', '钱老师', 'teacher', TRUE);

INSERT INTO `teachers` (user_id, employee_no, subjects, title, department)
SELECT u.id, 't260001', JSON_ARRAY('数学'), '高级教师', '数学教研组' FROM `users` u WHERE u.username = 'teacher1'
ON DUPLICATE KEY UPDATE employee_no = VALUES(employee_no), subjects = VALUES(subjects);
INSERT INTO `teachers` (user_id, employee_no, subjects, title, department)
SELECT u.id, 't260002', JSON_ARRAY('语文'), '一级教师', '语文教研组' FROM `users` u WHERE u.username = 'wang'
ON DUPLICATE KEY UPDATE employee_no = VALUES(employee_no), subjects = VALUES(subjects);
INSERT INTO `teachers` (user_id, employee_no, subjects, title, department)
SELECT u.id, 't260003', JSON_ARRAY('英语'), '一级教师', '英语教研组' FROM `users` u WHERE u.username = 'li'
ON DUPLICATE KEY UPDATE employee_no = VALUES(employee_no), subjects = VALUES(subjects);
INSERT INTO `teachers` (user_id, employee_no, subjects, title, department)
SELECT u.id, 't260004', JSON_ARRAY('物理'), '高级教师', '物理教研组' FROM `users` u WHERE u.username = 'zhao'
ON DUPLICATE KEY UPDATE employee_no = VALUES(employee_no), subjects = VALUES(subjects);
INSERT INTO `teachers` (user_id, employee_no, subjects, title, department)
SELECT u.id, 't260005', JSON_ARRAY('化学'), '一级教师', '化学教研组' FROM `users` u WHERE u.username = 'qian'
ON DUPLICATE KEY UPDATE employee_no = VALUES(employee_no), subjects = VALUES(subjects);

INSERT IGNORE INTO `users` (username, password_hash, email, full_name, role, is_active) VALUES
  ('s2', 'pbkdf2_sha256$100000$oyQShcQm0AShcGKAROUyKg==$tFR11gier9Qt17KnaH+BYV2NXIlE1YLedat6AWIF05o=', 's2@ai-edu.local', '王芳', 'student', TRUE),
  ('s3', 'pbkdf2_sha256$100000$oyQShcQm0AShcGKAROUyKg==$tFR11gier9Qt17KnaH+BYV2NXIlE1YLedat6AWIF05o=', 's3@ai-edu.local', '刘洋', 'student', TRUE),
  ('s4', 'pbkdf2_sha256$100000$oyQShcQm0AShcGKAROUyKg==$tFR11gier9Qt17KnaH+BYV2NXIlE1YLedat6AWIF05o=', 's4@ai-edu.local', '陈静', 'student', TRUE),
  ('s5', 'pbkdf2_sha256$100000$oyQShcQm0AShcGKAROUyKg==$tFR11gier9Qt17KnaH+BYV2NXIlE1YLedat6AWIF05o=', 's5@ai-edu.local', '杨帆', 'student', TRUE),
  ('s6', 'pbkdf2_sha256$100000$oyQShcQm0AShcGKAROUyKg==$tFR11gier9Qt17KnaH+BYV2NXIlE1YLedat6AWIF05o=', 's6@ai-edu.local', '赵磊', 'student', TRUE),
  ('s7', 'pbkdf2_sha256$100000$oyQShcQm0AShcGKAROUyKg==$tFR11gier9Qt17KnaH+BYV2NXIlE1YLedat6AWIF05o=', 's7@ai-edu.local', '孙悦', 'student', TRUE),
  ('s8', 'pbkdf2_sha256$100000$oyQShcQm0AShcGKAROUyKg==$tFR11gier9Qt17KnaH+BYV2NXIlE1YLedat6AWIF05o=', 's8@ai-edu.local', '周杰', 'student', TRUE),
  ('s9', 'pbkdf2_sha256$100000$oyQShcQm0AShcGKAROUyKg==$tFR11gier9Qt17KnaH+BYV2NXIlE1YLedat6AWIF05o=', 's9@ai-edu.local', '吴桐', 'student', TRUE),
  ('s10', 'pbkdf2_sha256$100000$oyQShcQm0AShcGKAROUyKg==$tFR11gier9Qt17KnaH+BYV2NXIlE1YLedat6AWIF05o=', 's10@ai-edu.local', '郑爽', 'student', TRUE);

INSERT IGNORE INTO `students` (user_id, student_no, grade)
SELECT u.id, 'S100002', '七年级' FROM `users` u WHERE u.username = 's2';
INSERT IGNORE INTO `students` (user_id, student_no, grade)
SELECT u.id, 'S100003', '七年级' FROM `users` u WHERE u.username = 's3';
INSERT IGNORE INTO `students` (user_id, student_no, grade)
SELECT u.id, 'S100004', '七年级' FROM `users` u WHERE u.username = 's4';
INSERT IGNORE INTO `students` (user_id, student_no, grade)
SELECT u.id, 'S100005', '七年级' FROM `users` u WHERE u.username = 's5';
INSERT IGNORE INTO `students` (user_id, student_no, grade)
SELECT u.id, 'S100006', '八年级' FROM `users` u WHERE u.username = 's6';
INSERT IGNORE INTO `students` (user_id, student_no, grade)
SELECT u.id, 'S100007', '八年级' FROM `users` u WHERE u.username = 's7';
INSERT IGNORE INTO `students` (user_id, student_no, grade)
SELECT u.id, 'S100008', '八年级' FROM `users` u WHERE u.username = 's8';
INSERT IGNORE INTO `students` (user_id, student_no, grade)
SELECT u.id, 'S100009', '九年级' FROM `users` u WHERE u.username = 's9';
INSERT IGNORE INTO `students` (user_id, student_no, grade)
SELECT u.id, 'S100010', '九年级' FROM `users` u WHERE u.username = 's10';

INSERT IGNORE INTO `classes` (name, class_no, teacher_id, grade, description)
SELECT '七年级2班', 'C2026002', u.id, '七年级', '示例班级' FROM `users` u WHERE u.username = 'wang';
INSERT IGNORE INTO `classes` (name, class_no, teacher_id, grade, description)
SELECT '八年级1班', 'C2026003', u.id, '八年级', '示例班级' FROM `users` u WHERE u.username = 'li';
INSERT IGNORE INTO `classes` (name, class_no, teacher_id, grade, description)
SELECT '八年级2班', 'C2026004', u.id, '八年级', '示例班级' FROM `users` u WHERE u.username = 'zhao';
INSERT IGNORE INTO `classes` (name, class_no, teacher_id, grade, description)
SELECT '九年级1班', 'C2026005', u.id, '九年级', '示例班级' FROM `users` u WHERE u.username = 'qian';

INSERT IGNORE INTO `class_students` (class_id, student_id)
SELECT c.id, s.id FROM `classes` c JOIN `students` s ON s.student_no = 'S100002' WHERE c.name = '七年级1班';
INSERT IGNORE INTO `class_students` (class_id, student_id)
SELECT c.id, s.id FROM `classes` c JOIN `students` s ON s.student_no = 'S100003' WHERE c.name = '七年级1班';
INSERT IGNORE INTO `class_students` (class_id, student_id)
SELECT c.id, s.id FROM `classes` c JOIN `students` s ON s.student_no = 'S100004' WHERE c.name = '七年级1班';
INSERT IGNORE INTO `class_students` (class_id, student_id)
SELECT c.id, s.id FROM `classes` c JOIN `students` s ON s.student_no = 'S100005' WHERE c.name = '七年级1班';
INSERT IGNORE INTO `class_students` (class_id, student_id)
SELECT c.id, s.id FROM `classes` c JOIN `students` s ON s.student_no = 'S100006' WHERE c.name = '七年级2班';
INSERT IGNORE INTO `class_students` (class_id, student_id)
SELECT c.id, s.id FROM `classes` c JOIN `students` s ON s.student_no = 'S100007' WHERE c.name = '七年级2班';
INSERT IGNORE INTO `class_students` (class_id, student_id)
SELECT c.id, s.id FROM `classes` c JOIN `students` s ON s.student_no = 'S100008' WHERE c.name = '八年级1班';
INSERT IGNORE INTO `class_students` (class_id, student_id)
SELECT c.id, s.id FROM `classes` c JOIN `students` s ON s.student_no = 'S100009' WHERE c.name = '八年级1班';
INSERT IGNORE INTO `class_students` (class_id, student_id)
SELECT c.id, s.id FROM `classes` c JOIN `students` s ON s.student_no = 'S100010' WHERE c.name = '八年级2班';

INSERT IGNORE INTO `courses` (name, grade, subject, chapter_tree, description) VALUES
  ('初中语文（七年级）', '七年级', '语文', '[{"chapter":"第一单元 四季美景","sections":["1 春","2 济南的冬天"]},{"chapter":"第二单元 至爱亲情","sections":["5 秋天的怀念","6 散步"]}]', '七年级上册语文示例课程'),
  ('初中英语（八年级）', '八年级', '英语', '[{"chapter":"Unit 1 Where did you go on vacation?","sections":["Section A","Section B"]},{"chapter":"Unit 2 How often do you exercise?","sections":["Section A","Section B"]}]', '八年级英语示例课程'),
  ('初中物理（八年级）', '八年级', '物理', '[{"chapter":"第一章 机械运动","sections":["1.1 长度和时间的测量","1.2 运动的描述"]},{"chapter":"第二章 声现象","sections":["2.1 声音的产生与传播"]}]', '八年级物理示例课程'),
  ('初中化学（九年级）', '九年级', '化学', '[{"chapter":"第一单元 走进化学世界","sections":["1.1 物质的变化和性质","1.2 化学是一门以实验为基础的科学"]},{"chapter":"第二单元 我们周围的空气","sections":["2.1 空气"]}]', '九年级化学示例课程');

INSERT IGNORE INTO `exercises` (course_id, `type`, chapter, content, options, answer, analysis, difficulty, knowledge_points)
VALUES
  ((SELECT id FROM `courses` WHERE name = '初中语文（七年级）'), 'single', '第一单元 四季美景', '朱自清《春》中“小草偷偷地从土里钻出来”使用了什么修辞手法？', '[{"key":"A","text":"比喻"},{"key":"B","text":"拟人"},{"key":"C","text":"夸张"},{"key":"D","text":"排比"}]', 'B', '“偷偷地”“钻”赋予小草人的情态，是拟人手法。', 'easy', '["修辞手法"]'),
  ((SELECT id FROM `courses` WHERE name = '初中语文（七年级）'), 'single', '第二单元 至爱亲情', '《秋天的怀念》的作者是？', '[{"key":"A","text":"朱自清"},{"key":"B","text":"老舍"},{"key":"C","text":"史铁生"},{"key":"D","text":"冰心"}]', 'C', '《秋天的怀念》是史铁生的作品。', 'medium', '["文学常识"]'),
  ((SELECT id FROM `courses` WHERE name = '初中语文（七年级）'), 'fill', '第一单元 四季美景', '“________________，草色遥看近却无。”请填写上句。', '[]', '天街小雨润如酥', '诗句填空，注意易错字“酥”。', 'medium', '["古诗默写"]'),
  ((SELECT id FROM `courses` WHERE name = '初中英语（八年级）'), 'single', 'Unit 1 Where did you go on vacation?', '— Where did you go on vacation? — I ____ to Beijing.', '[{"key":"A","text":"go"},{"key":"B","text":"went"},{"key":"C","text":"gone"},{"key":"D","text":"going"}]', 'B', '一般过去时，用 went。', 'easy', '["一般过去时"]'),
  ((SELECT id FROM `courses` WHERE name = '初中英语（八年级）'), 'single', 'Unit 2 How often do you exercise?', 'How often ____ you exercise?', '[{"key":"A","text":"do"},{"key":"B","text":"does"},{"key":"C","text":"did"},{"key":"D","text":"are"}]', 'A', '主语 you，一般现在时用 do。', 'easy', '["疑问副词 how often"]'),
  ((SELECT id FROM `courses` WHERE name = '初中英语（八年级）'), 'fill', 'Unit 1 Where did you go on vacation?', 'It was my first time ____ (visit) the Great Wall. 用所给词适当形式填空。', '[]', 'to visit', 'It is the first time to do sth. 固定搭配。', 'hard', '["非谓语动词"]'),
  ((SELECT id FROM `courses` WHERE name = '初中物理（八年级）'), 'single', '第一章 机械运动', '下列估测最接近实际的是：', '[{"key":"A","text":"课桌高度约 0.8m"},{"key":"B","text":"人步行的速度约 20m/s"},{"key":"C","text":"中学生身高约 1.6dm"},{"key":"D","text":"教室长度约 8mm"}]', 'A', '课桌高度约 0.8m 正确；步行速度约 1.2m/s。', 'medium', '["长度的估测"]'),
  ((SELECT id FROM `courses` WHERE name = '初中物理（八年级）'), 'single', '第二章 声现象', '声音在下列哪种介质中传播最快？', '[{"key":"A","text":"空气"},{"key":"B","text":"水"},{"key":"C","text":"钢铁"},{"key":"D","text":"真空"}]', 'C', '声音在固体中传播最快；真空不能传声。', 'easy', '["声音的传播"]'),
  ((SELECT id FROM `courses` WHERE name = '初中物理（八年级）'), 'judge', '第一章 机械运动', '物体运动速度越快，其路程一定越大。', '[]', '错', '路程还与时间有关。', 'medium', '["速度"]'),
  ((SELECT id FROM `courses` WHERE name = '初中化学（九年级）'), 'single', '第一单元 走进化学世界', '下列变化属于化学变化的是：', '[{"key":"A","text":"冰雪融化"},{"key":"B","text":"粮食酿酒"},{"key":"C","text":"玻璃破碎"},{"key":"D","text":"酒精挥发"}]', 'B', '粮食酿酒生成新物质，属于化学变化。', 'easy', '["物理变化与化学变化"]'),
  ((SELECT id FROM `courses` WHERE name = '初中化学（九年级）'), 'single', '第二单元 我们周围的空气', '空气中含量最多的气体是：', '[{"key":"A","text":"氧气"},{"key":"B","text":"氮气"},{"key":"C","text":"二氧化碳"},{"key":"D","text":"稀有气体"}]', 'B', '氮气约占空气体积的 78%。', 'easy', '["空气的组成"]'),
  ((SELECT id FROM `courses` WHERE name = '初中化学（九年级）'), 'fill', '第二单元 我们周围的空气', '氧气约占空气体积的 ____%。', '[]', '21', '氧气约占空气体积的 21%。', 'medium', '["空气的组成"]'),
  ((SELECT id FROM `courses` WHERE name = '初中数学（七年级）'), 'single', '第一章 有理数', '计算：(-2) × (-3) = ?', '[{"key":"A","text":"-6"},{"key":"B","text":"6"},{"key":"C","text":"5"},{"key":"D","text":"-5"}]', 'B', '同号两数相乘得正：(-2)×(-3)=6。', 'easy', '["有理数乘法"]'),
  ((SELECT id FROM `courses` WHERE name = '初中数学（七年级）'), 'single', '第二章 整式的加减', '化简：2(x + 1) - x = ?', '[{"key":"A","text":"x+2"},{"key":"B","text":"x+1"},{"key":"C","text":"2x+2"},{"key":"D","text":"3x+2"}]', 'A', '2(x+1)-x = 2x+2-x = x+2。', 'medium', '["去括号与合并同类项"]'),
  ((SELECT id FROM `courses` WHERE name = '初中数学（七年级）'), 'judge', '第一章 有理数', '0 既不是正数也不是负数。', '[]', '对', '0 是正数与负数的分界。', 'easy', '["正数和负数"]');