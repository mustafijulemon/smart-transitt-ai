BEGIN;

ALTER TABLE bus_observations
    ADD COLUMN latitude DOUBLE PRECISION,
    ADD COLUMN longitude DOUBLE PRECISION,
    ADD COLUMN reviewed_by UUID REFERENCES users(id),
    ADD COLUMN reviewed_at TIMESTAMPTZ,
    ADD COLUMN review_note TEXT NOT NULL DEFAULT '',
    ADD COLUMN fine_amount_bdt NUMERIC(10, 2) NOT NULL DEFAULT 0,
    ADD COLUMN bonus_points_awarded INTEGER NOT NULL DEFAULT 0,
    ADD CONSTRAINT ck_bus_observation_coordinates
        CHECK (
            (latitude IS NULL AND longitude IS NULL)
            OR (
                latitude BETWEEN -90 AND 90
                AND longitude BETWEEN -180 AND 180
            )
        ),
    ADD CONSTRAINT ck_bus_observation_fine_nonnegative
        CHECK (fine_amount_bdt >= 0),
    ADD CONSTRAINT ck_bus_observation_bonus_nonnegative
        CHECK (bonus_points_awarded >= 0);

ALTER TABLE user_game_profiles
    ADD COLUMN driver_rating NUMERIC(2, 1),
    ADD COLUMN completed_trips INTEGER NOT NULL DEFAULT 0,
    ADD CONSTRAINT ck_driver_rating_range
        CHECK (driver_rating IS NULL OR driver_rating BETWEEN 1 AND 5),
    ADD CONSTRAINT ck_completed_trips_nonnegative
        CHECK (completed_trips >= 0);

CREATE TABLE driver_trips (
    id UUID PRIMARY KEY,
    driver_id UUID NOT NULL REFERENCES users(id),
    bus_number VARCHAR(50) NOT NULL,
    route_name VARCHAR(150) NOT NULL,
    status VARCHAR(20) NOT NULL
        CHECK (status IN ('IN_PROGRESS', 'COMPLETED')),
    safety_score INTEGER
        CHECK (safety_score IS NULL OR safety_score BETWEEN 0 AND 100),
    rating NUMERIC(2, 1)
        CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    CHECK (
        (status = 'IN_PROGRESS' AND completed_at IS NULL AND rating IS NULL)
        OR
        (status = 'COMPLETED' AND completed_at IS NOT NULL AND rating IS NOT NULL)
    )
);

CREATE UNIQUE INDEX uq_driver_trips_one_active_per_driver
    ON driver_trips(driver_id)
    WHERE status = 'IN_PROGRESS';

CREATE INDEX ix_bus_observations_pending_created
    ON bus_observations(created_at)
    WHERE status = 'PENDING';

CREATE INDEX ix_driver_trips_driver_completed
    ON driver_trips(driver_id, completed_at DESC)
    WHERE status = 'COMPLETED';

COMMIT;
