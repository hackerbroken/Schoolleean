-- SchoolLearn MySQL schema
-- Compatible with MySQL 8+

CREATE DATABASE IF NOT EXISTS schoollearn
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE schoollearn;

CREATE TABLE IF NOT EXISTS users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username VARCHAR(120) NOT NULL,
  email VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  grade VARCHAR(32) NULL,
  school VARCHAR(255) NULL,
  is_admin TINYINT(1) NOT NULL DEFAULT 0,
  joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS quiz_subject_settings (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  subject_key VARCHAR(64) NOT NULL,
  subject_name VARCHAR(120) NOT NULL,
  is_enabled TINYINT(1) NOT NULL DEFAULT 1,
  updated_by BIGINT UNSIGNED NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_subject_key (subject_key),
  KEY idx_subject_updated_by (updated_by),
  CONSTRAINT fk_subject_updated_by
    FOREIGN KEY (updated_by) REFERENCES users(id)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS quiz_questions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  subject_key VARCHAR(64) NOT NULL,
  qid VARCHAR(80) NOT NULL,
  source ENUM('base', 'custom') NOT NULL DEFAULT 'custom',
  question_text TEXT NOT NULL,
  option_a TEXT NOT NULL,
  option_b TEXT NOT NULL,
  option_c TEXT NOT NULL,
  option_d TEXT NOT NULL,
  answer_index TINYINT UNSIGNED NOT NULL,
  explanation TEXT NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_subject_qid (subject_key, qid),
  KEY idx_questions_subject (subject_key),
  KEY idx_questions_created_by (created_by),
  CONSTRAINT fk_questions_created_by
    FOREIGN KEY (created_by) REFERENCES users(id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT chk_answer_index
    CHECK (answer_index BETWEEN 0 AND 3)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS quiz_attempts (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  attempt_uuid CHAR(25) NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  subject_key VARCHAR(64) NOT NULL,
  subject_title VARCHAR(120) NOT NULL,
  score INT UNSIGNED NOT NULL,
  total_questions INT UNSIGNED NOT NULL,
  percentage DECIMAL(5,2) NOT NULL,
  attempted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_attempt_uuid (attempt_uuid),
  KEY idx_attempts_user_time (user_id, attempted_at),
  KEY idx_attempts_subject_time (subject_key, attempted_at),
  CONSTRAINT fk_attempts_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT chk_attempt_totals
    CHECK (total_questions > 0 AND score <= total_questions)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS marks_entries (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  mark_uuid CHAR(25) NOT NULL,
  student_id BIGINT UNSIGNED NOT NULL,
  uploaded_by BIGINT UNSIGNED NOT NULL,
  exam_name VARCHAR(160) NOT NULL,
  subject VARCHAR(120) NOT NULL,
  score DECIMAL(8,2) NOT NULL,
  total DECIMAL(8,2) NOT NULL,
  percentage DECIMAL(5,2) NOT NULL,
  remarks TEXT NULL,
  exam_date DATE NULL,
  recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_mark_uuid (mark_uuid),
  KEY idx_marks_student_time (student_id, recorded_at),
  KEY idx_marks_subject (subject),
  KEY idx_marks_uploaded_by (uploaded_by),
  CONSTRAINT fk_marks_student
    FOREIGN KEY (student_id) REFERENCES users(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_marks_uploaded_by
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT chk_marks_values
    CHECK (total > 0 AND score >= 0 AND score <= total)
) ENGINE=InnoDB;

INSERT INTO quiz_subject_settings (subject_key, subject_name, is_enabled)
VALUES
  ('computer', 'Computer', 1),
  ('math', 'Mathematics', 1),
  ('science', 'Science', 1),
  ('english', 'English', 1),
  ('gujarati', 'Gujarati', 1),
  ('social-science', 'Social Science', 1)
ON DUPLICATE KEY UPDATE
  subject_name = VALUES(subject_name),
  is_enabled = VALUES(is_enabled);
