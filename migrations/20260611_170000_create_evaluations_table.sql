-- Migration: Create evaluations table
-- Date: 2026-06-11 17:00:00

CREATE TABLE IF NOT EXISTS `evaluations` (
    `id`                      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `url`                     TEXT NOT NULL,
    `url_hash`                CHAR(64) NOT NULL COMMENT 'SHA-256 hex digest of url',
    `domain`                  VARCHAR(255) DEFAULT NULL,
    `version`                 INT UNSIGNED NOT NULL DEFAULT 1,
    `title_scraped`           TEXT DEFAULT NULL,
    `classification`          VARCHAR(255) DEFAULT NULL,

    `originality`             TINYINT UNSIGNED DEFAULT NULL,
    `significance_locality`   TINYINT UNSIGNED DEFAULT NULL,
    `quality_and_depth`       TINYINT UNSIGNED DEFAULT NULL,
    `trust_and_sources`       TINYINT UNSIGNED DEFAULT NULL,
    `domain_specific_score`   TINYINT UNSIGNED DEFAULT NULL,

    `final_overall_score`     DECIMAL(4,2) DEFAULT NULL,

    `justifications`          JSON DEFAULT NULL,
    `strengths`               JSON DEFAULT NULL,
    `weaknesses`              JSON DEFAULT NULL,

    `evaluated_at`            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `raw_response`            JSON DEFAULT NULL,

    PRIMARY KEY (`id`),
    UNIQUE KEY `unique_url_version` (`url_hash`, `version`),
    INDEX `idx_url_hash` (`url_hash`),
    INDEX `idx_domain` (`domain`),
    INDEX `idx_evaluated_at` (`evaluated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
