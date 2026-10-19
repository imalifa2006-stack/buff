-- Baf study reports. PostgreSQL 14+.
-- Run once:  psql "$DATABASE_URL" -f schema.sql
CREATE EXTENSION IF NOT EXISTS citext;

-- Students we already know. Matched by Telegram username at first registration.
CREATE TABLE allowed_students (
  id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  telegram_username citext NOT NULL UNIQUE,
  note              text,
  used              boolean NOT NULL DEFAULT false
);

CREATE TABLE users (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  telegram_id   bigint NOT NULL UNIQUE,          -- the real identity (never changes)
  tg_username   text,                            -- can change in Telegram; refreshed on every login
  first_name    text NOT NULL,
  last_name     text,
  username      citext NOT NULL UNIQUE
                CHECK (username ~ '^[A-Za-z0-9_\u0600-\u06FF]{3,24}$'),  -- chosen by the student
  password_hash text,                            -- optional (argon2id), only for login outside Telegram
  field         text NOT NULL CHECK (field IN ('r','t','e')),
  grade         text NOT NULL CHECK (grade IN ('10','11','12','grad')),
  status        text NOT NULL DEFAULT 'approved' CHECK (status IN ('approved','blocked')),
  created_at    timestamptz NOT NULL DEFAULT now(),
  last_seen_at  timestamptz
);

CREATE TABLE sessions (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash   text NOT NULL UNIQUE,             -- sha256 of the token; the token itself is never stored
  user_agent   text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  last_used_at timestamptz NOT NULL DEFAULT now(),
  expires_at   timestamptz NOT NULL,
  revoked_at   timestamptz
);
CREATE INDEX sessions_user_idx ON sessions(user_id);

CREATE TABLE subjects (
  id     int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name   text NOT NULL UNIQUE,
  fields text[] NOT NULL                          -- which fields see this subject: r, t, e
);

CREATE TABLE study_reports (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id     bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  report_date date NOT NULL,
  sleep_hours numeric(3,1) NOT NULL CHECK (sleep_hours BETWEEN 0 AND 16),
  mood        smallint NOT NULL CHECK (mood BETWEEN 0 AND 4),
  focus       smallint NOT NULL CHECK (focus BETWEEN 1 AND 5),
  note        text NOT NULL DEFAULT '' CHECK (length(note) <= 300),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, report_date)                   -- one report per student per day; also serves as the index
);

CREATE TABLE report_entries (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  report_id  bigint NOT NULL REFERENCES study_reports(id) ON DELETE CASCADE,
  subject_id int NOT NULL REFERENCES subjects(id),
  minutes    int NOT NULL DEFAULT 0 CHECK (minutes BETWEEN 0 AND 1440),
  tests      int NOT NULL DEFAULT 0 CHECK (tests BETWEEN 0 AND 1000),
  correct    int NOT NULL DEFAULT 0 CHECK (correct >= 0),
  wrong      int NOT NULL DEFAULT 0 CHECK (wrong >= 0),
  CHECK (correct + wrong <= tests),
  UNIQUE (report_id, subject_id)
);

-- Not stored on purpose: blank answers, percentages, totals, streaks (all derived from the raw numbers).

INSERT INTO subjects (name, fields) VALUES
 ('ریاضی','{r,t}'),('فیزیک','{r,t}'),('شیمی','{r,t}'),('زیست‌شناسی','{t}'),
 ('ادبیات','{r,t}'),('عربی','{r,t}'),('دین و زندگی','{r,t,e}'),('زبان انگلیسی','{r,t,e}'),
 ('ادبیات اختصاصی','{e}'),('عربی اختصاصی','{e}'),('فلسفه و منطق','{e}'),('جامعه‌شناسی','{e}'),
 ('تاریخ','{e}'),('جغرافیا','{e}'),('اقتصاد','{e}'),('ریاضی و آمار','{e}');
