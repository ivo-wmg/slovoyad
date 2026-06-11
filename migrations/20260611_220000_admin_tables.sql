CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin','editor','viewer') DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE sessions (
    token CHAR(64) PRIMARY KEY,
    user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE evaluation_groups (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status ENUM('pending','running','completed','failed') DEFAULT 'pending',
    total_urls INT DEFAULT 0,
    completed_urls INT DEFAULT 0,
    failed_urls INT DEFAULT 0,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_status (status),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE group_urls (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    url TEXT NOT NULL,
    status ENUM('pending','processing','completed','failed') DEFAULT 'pending',
    error_message TEXT,
    evaluation_id INT,
    retries TINYINT UNSIGNED DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES evaluation_groups(id) ON DELETE CASCADE,
    INDEX idx_group_status (group_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE evaluations ADD COLUMN group_id INT DEFAULT NULL AFTER raw_response;
ALTER TABLE evaluations ADD INDEX idx_group (group_id);
