DROP TABLE IF EXISTS
  key_qualification,
  cv_role,
  blog_publication,
  position,
  education,
  course,
  certification,
  work_experience,
  project_experience,
  cv_language,
  cv_technology,
  dim_language,
  dim_technology,
  dim_industry,
  dim_project_type,
  cvs,
  users
CASCADE;

CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    cv_partner_user_id TEXT UNIQUE NOT NULL,
    name_multilang JSONB NOT NULL,
    nationality_multilang JSONB,
    email TEXT,
    upn TEXT,
    external_user_id TEXT,
    phone_number TEXT,
    landline TEXT,
    birth_year INTEGER,
    department TEXT,
    country TEXT,
    user_created_at DATE
);

CREATE INDEX ix_users_cv_partner_user_id ON users (cv_partner_user_id);

CREATE TABLE cvs (
  cv_id SERIAL PRIMARY KEY,
  cv_partner_cv_id TEXT UNIQUE NOT NULL,
  user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  title_multilang JSONB,
  years_of_education INTEGER,
  years_since_first_work_experience INTEGER,
  has_profile_image BOOLEAN,
  owns_reference_project BOOLEAN,
  read_privacy_notice BOOLEAN,
  cv_last_updated_by_owner DATE,
  cv_last_updated DATE,
  sfia_level INTEGER,
  cpd_level INTEGER,
  cpd_band TEXT,
  cpd_label TEXT
);

CREATE INDEX ix_cvs_user_id ON cvs (user_id);
CREATE INDEX ix_cvs_cv_partner_cv_id ON cvs (cv_partner_cv_id);

CREATE TABLE dim_technology (
  technology_id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE dim_language (
  language_id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE dim_industry (
  industry_id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE dim_project_type (
  project_type_id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE cv_technology (
  cv_id INTEGER NOT NULL REFERENCES cvs(cv_id) ON DELETE CASCADE,
  technology_id INTEGER NOT NULL REFERENCES dim_technology(technology_id),
  years_experience INTEGER,
  proficiency INTEGER,
  is_official_masterdata JSONB,
  PRIMARY KEY (cv_id, technology_id)
);

CREATE TABLE cv_language (
  cv_id INTEGER NOT NULL REFERENCES cvs(cv_id) ON DELETE CASCADE,
  language_id INTEGER NOT NULL REFERENCES dim_language(language_id),
  level TEXT,
  highlighted BOOLEAN,
  is_official_masterdata JSONB,
  updated DATE,
  updated_by_owner DATE,
  PRIMARY KEY (cv_id, language_id)
);

CREATE TABLE project_experience (
  cv_id INTEGER NOT NULL REFERENCES cvs(cv_id) ON DELETE CASCADE,
  cv_partner_section_id TEXT NOT NULL,
  external_unique_id TEXT,
  month_from INTEGER, year_from INTEGER,
  month_to INTEGER,   year_to INTEGER,
  customer_int TEXT,
  customer_multilang JSONB,
  customer_anon_int TEXT,
  customer_anon_multilang JSONB,
  description_int TEXT,
  description_multilang JSONB,
  long_description_int TEXT,
  long_description_multilang JSONB,
  industry_id INTEGER REFERENCES dim_industry(industry_id),
  project_type_id INTEGER REFERENCES dim_project_type(project_type_id),
  percent_allocated INTEGER,
  extent_individual_hours INTEGER,
  extent_hours INTEGER,
  extent_total_hours INTEGER,
  extent_unit TEXT,
  extent_currency TEXT,
  extent_total INTEGER,
  extent_total_currency TEXT,
  project_area INTEGER,
  project_area_unit TEXT,
  highlighted BOOLEAN,
  updated DATE,
  updated_by_owner DATE,
  PRIMARY KEY (cv_id, cv_partner_section_id)
);

CREATE TABLE work_experience (
  cv_id INTEGER NOT NULL REFERENCES cvs(cv_id) ON DELETE CASCADE,
  cv_partner_section_id TEXT NOT NULL,
  external_unique_id TEXT,
  month_from INTEGER, year_from INTEGER,
  month_to INTEGER,   year_to INTEGER,
  highlighted BOOLEAN,
  employer TEXT,
  description TEXT,
  long_description TEXT,
  updated DATE,
  updated_by_owner DATE,
  PRIMARY KEY (cv_id, cv_partner_section_id)
);

CREATE TABLE certification (
  cv_id INTEGER NOT NULL REFERENCES cvs(cv_id) ON DELETE CASCADE,
  cv_partner_section_id TEXT NOT NULL,
  external_unique_id TEXT,
  month INTEGER, year INTEGER,
  month_expire INTEGER, year_expire INTEGER,
  updated DATE,
  updated_by_owner DATE,
  PRIMARY KEY (cv_id, cv_partner_section_id)
);

CREATE TABLE course (
  cv_id INTEGER NOT NULL REFERENCES cvs(cv_id) ON DELETE CASCADE,
  cv_partner_section_id TEXT NOT NULL,
  external_unique_id TEXT,
  month INTEGER, year INTEGER,
  name TEXT,
  organiser TEXT,
  long_description TEXT,
  highlighted BOOLEAN,
  is_official_masterdata JSONB,
  attachments TEXT,
  updated DATE,
  updated_by_owner DATE,
  PRIMARY KEY (cv_id, cv_partner_section_id)
);

CREATE TABLE education (
  cv_id INTEGER NOT NULL REFERENCES cvs(cv_id) ON DELETE CASCADE,
  cv_partner_section_id TEXT NOT NULL,
  external_unique_id TEXT,
  month_from INTEGER, year_from INTEGER,
  month_to INTEGER,   year_to INTEGER,
  highlighted BOOLEAN,
  attachments TEXT,
  place_of_study TEXT,
  degree TEXT,
  description TEXT,
  updated DATE,
  updated_by_owner DATE,
  PRIMARY KEY (cv_id, cv_partner_section_id)
);

CREATE TABLE position (
  cv_id INTEGER NOT NULL REFERENCES cvs(cv_id) ON DELETE CASCADE,
  cv_partner_section_id TEXT NOT NULL,
  external_unique_id TEXT,
  year_from INTEGER,
  year_to INTEGER,
  highlighted BOOLEAN,
  name TEXT,
  description TEXT,
  updated DATE,
  updated_by_owner DATE,
  PRIMARY KEY (cv_id, cv_partner_section_id)
);

CREATE TABLE blog_publication (
  cv_id INTEGER NOT NULL REFERENCES cvs(cv_id) ON DELETE CASCADE,
  cv_partner_section_id TEXT NOT NULL,
  external_unique_id TEXT,
  name TEXT,
  description TEXT,
  highlighted BOOLEAN,
  updated DATE,
  updated_by_owner DATE,
  PRIMARY KEY (cv_id, cv_partner_section_id)
);

CREATE TABLE cv_role (
  cv_id INTEGER NOT NULL REFERENCES cvs(cv_id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  highlighted BOOLEAN,
  updated DATE,
  updated_by_owner DATE,
  PRIMARY KEY (cv_id, name)
);

CREATE TABLE key_qualification (
  cv_id INTEGER NOT NULL REFERENCES cvs(cv_id) ON DELETE CASCADE,
  cv_partner_section_id TEXT NOT NULL,
  external_unique_id TEXT,
  label TEXT,
  summary TEXT,
  short_description TEXT,
  updated DATE,
  updated_by_owner DATE,
  PRIMARY KEY (cv_id, cv_partner_section_id)
);

CREATE INDEX ix_cvtech_cv ON cv_technology (cv_id);
CREATE INDEX ix_cvlang_cv ON cv_language (cv_id);
CREATE INDEX ix_proj_cv ON project_experience (cv_id);
CREATE INDEX ix_work_cv ON work_experience (cv_id);
CREATE INDEX ix_cert_cv ON certification (cv_id);
CREATE INDEX ix_course_cv ON course (cv_id);
CREATE INDEX ix_edu_cv ON education (cv_id);
CREATE INDEX ix_pos_cv ON position (cv_id);
CREATE INDEX ix_blog_cv ON blog_publication (cv_id);
CREATE INDEX ix_kq_cv ON key_qualification (cv_id);

CREATE TABLE IF NOT EXISTS dim_clearance (
  clearance_id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS user_clearance (
  user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  clearance_id INTEGER NOT NULL REFERENCES dim_clearance(clearance_id) ON DELETE RESTRICT,
  valid_from DATE NOT NULL,
  valid_to DATE,
  verified_by TEXT,
  notes TEXT,
  PRIMARY KEY (user_id, clearance_id, valid_from)
);

CREATE INDEX IF NOT EXISTS ix_user_clearance_user ON user_clearance (user_id);
CREATE INDEX IF NOT EXISTS ix_user_clearance_clearance ON user_clearance (clearance_id);

CREATE TABLE IF NOT EXISTS user_availability (
  user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  date DATE NOT NULL,
  percent_available INTEGER NOT NULL CHECK (percent_available BETWEEN 0 AND 100),
  source TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, date)
);

CREATE INDEX IF NOT EXISTS ix_user_availability_user ON user_availability (user_id);
CREATE INDEX IF NOT EXISTS ix_user_availability_date ON user_availability (date);
