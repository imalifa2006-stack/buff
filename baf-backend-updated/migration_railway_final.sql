-- Run on a Neon BRANCH first. Existing user data and reports are retained.
BEGIN;
CREATE EXTENSION IF NOT EXISTS citext;
ALTER TABLE users ADD COLUMN IF NOT EXISTS role text NOT NULL DEFAULT 'student';
ALTER TABLE users ADD COLUMN IF NOT EXISTS advisor_id bigint;
ALTER TABLE users ALTER COLUMN telegram_id DROP NOT NULL;
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('student','advisor','admin','super_admin'));
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_status_check;
ALTER TABLE users ADD CONSTRAINT users_status_check CHECK (status IN ('approved','pending','rejected','blocked'));
CREATE TABLE IF NOT EXISTS verified_advisors (username citext PRIMARY KEY,active boolean NOT NULL DEFAULT true,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS advisor_allowlist (advisor_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,student_username citext NOT NULL,PRIMARY KEY(advisor_id,student_username));
CREATE TABLE IF NOT EXISTS advisor_change_requests (student_id bigint PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,advisor_id bigint NOT NULL REFERENCES users(id),status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS users_advisor_id_idx ON users(advisor_id);
COMMIT;
