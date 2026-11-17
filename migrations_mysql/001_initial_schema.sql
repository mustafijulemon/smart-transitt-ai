CREATE TABLE IF NOT EXISTS users (
    id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(30) NOT NULL UNIQUE,
    profile_image_url VARCHAR(2048) NULL,
    identity_type VARCHAR(32) NULL,
    nid_passport_number VARCHAR(100) NULL UNIQUE,
    user_role VARCHAR(16) NOT NULL DEFAULT 'CITIZEN',
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_users_role CHECK (user_role IN ('CITIZEN', 'POLICE', 'DRIVER'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_game_profiles (
    user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    total_points INT NOT NULL DEFAULT 0,
    current_level INT NOT NULL DEFAULT 1,
    is_police_eligible BOOLEAN NOT NULL DEFAULT FALSE,
    is_driver_trained BOOLEAN NOT NULL DEFAULT FALSE,
    has_gov_license BOOLEAN NOT NULL DEFAULT FALSE,
    driver_rating DECIMAL(2, 1) NULL,
    completed_trips INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_profile_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT ck_profile_points CHECK (total_points >= 0),
    CONSTRAINT ck_profile_level CHECK (current_level >= 1),
    CONSTRAINT ck_profile_rating CHECK (driver_rating IS NULL OR driver_rating BETWEEN 1 AND 5),
    CONSTRAINT ck_profile_trips CHECK (completed_trips >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS bus_observations (
    id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    reporter_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    bus_number VARCHAR(50) NOT NULL,
    route_name VARCHAR(150) NOT NULL,
    issue_type VARCHAR(40) NOT NULL,
    image_url VARCHAR(2048) NULL,
    latitude DOUBLE NOT NULL,
    longitude DOUBLE NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_by CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
    reviewed_at TIMESTAMP NULL,
    review_note TEXT NOT NULL,
    fine_amount_bdt DECIMAL(10, 2) NOT NULL DEFAULT 0,
    bonus_points_awarded INT NOT NULL DEFAULT 0,
    CONSTRAINT fk_observation_reporter FOREIGN KEY (reporter_id) REFERENCES users(id),
    CONSTRAINT fk_observation_reviewer FOREIGN KEY (reviewed_by) REFERENCES users(id),
    CONSTRAINT ck_observation_coordinates CHECK (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180),
    CONSTRAINT ck_observation_status CHECK (status IN ('PENDING', 'VERIFIED', 'REJECTED')),
    CONSTRAINT ck_observation_fine CHECK (fine_amount_bdt >= 0),
    CONSTRAINT ck_observation_bonus CHECK (bonus_points_awarded >= 0),
    INDEX ix_observations_status_created (status, created_at),
    INDEX ix_observations_reporter_created (reporter_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS driver_trips (
    id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    driver_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    bus_number VARCHAR(50) NOT NULL,
    route_name VARCHAR(150) NOT NULL,
    status VARCHAR(20) NOT NULL,
    active_driver_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NULL,
    safety_score INT NULL,
    rating DECIMAL(2, 1) NULL,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    CONSTRAINT fk_trip_driver FOREIGN KEY (driver_id) REFERENCES users(id),
    CONSTRAINT ck_trip_status CHECK (status IN ('IN_PROGRESS', 'COMPLETED')),
    CONSTRAINT ck_trip_safety_score CHECK (safety_score IS NULL OR safety_score BETWEEN 0 AND 100),
    CONSTRAINT ck_trip_rating CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
    UNIQUE INDEX uq_driver_trips_one_active (active_driver_id),
    INDEX ix_driver_trips_driver_status (driver_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    portal_role VARCHAR(16) NOT NULL,
    message_role VARCHAR(16) NOT NULL,
    encrypted_content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_chat_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT ck_chat_portal CHECK (portal_role IN ('CITIZEN', 'POLICE', 'DRIVER')),
    CONSTRAINT ck_chat_message_role CHECK (message_role IN ('USER', 'ASSISTANT')),
    INDEX ix_chat_user_portal_created (user_id, portal_role, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS police_stations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    address VARCHAR(500) NOT NULL,
    area VARCHAR(150) NOT NULL,
    phone VARCHAR(40) NULL,
    latitude DOUBLE NOT NULL,
    longitude DOUBLE NOT NULL,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT ck_station_coordinates CHECK (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180),
    INDEX ix_station_verified_area (verified, area)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
