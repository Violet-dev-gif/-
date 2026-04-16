CREATE TABLE IF NOT EXISTS solve_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    trace_id VARCHAR(64) NOT NULL UNIQUE,
    user_id VARCHAR(64) NULL,
    question_hash VARCHAR(64) NOT NULL,
    question_text TEXT NOT NULL,
    question_type VARCHAR(32) NOT NULL DEFAULT 'unknown',
    final_answer TEXT NOT NULL,
    normalized_answer VARCHAR(255) NOT NULL DEFAULT '',
    confidence DOUBLE NOT NULL DEFAULT 0,
    model_source VARCHAR(64) NOT NULL DEFAULT '',
    latency_ms INT NOT NULL DEFAULT 0,
    token_cost INT NOT NULL DEFAULT 0,
    cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_question_hash (question_hash),
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
);

CREATE TABLE IF NOT EXISTS user_profile (
    user_id VARCHAR(64) PRIMARY KEY,
    solved_count INT NOT NULL DEFAULT 0,
    profile_tags TEXT NULL,
    solve_preference VARCHAR(64) NOT NULL DEFAULT 'standard',
    level INT NOT NULL DEFAULT 0,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_call_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    trace_id VARCHAR(64) NOT NULL,
    agent_name VARCHAR(32) NOT NULL,
    model_name VARCHAR(64) NOT NULL,
    success BOOLEAN NOT NULL DEFAULT FALSE,
    latency_ms INT NOT NULL DEFAULT 0,
    token_cost INT NOT NULL DEFAULT 0,
    response_excerpt TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_trace_id (trace_id),
    INDEX idx_agent_name (agent_name)
);
