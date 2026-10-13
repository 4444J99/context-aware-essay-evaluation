CREATE TABLE intake_submissions (
  id uuid PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now(),
  instructor_id uuid NOT NULL REFERENCES instructors(id),
  course_id uuid NOT NULL,
  request_id uuid NOT NULL,
  fixture_id text NOT NULL CHECK (fixture_id IN ('argument','literary','contextual','docx-argument','pdf-held')),
  source_revision uuid NOT NULL,
  original_object uuid NOT NULL,
  content_object uuid,
  review_generation integer NOT NULL DEFAULT 0 CHECK (review_generation >= 0),
  state text NOT NULL CHECK (state IN ('extraction_held','privacy_pending','privacy_reviewed')),
  holds text[] NOT NULL,
  UNIQUE (id, course_id, instructor_id),
  UNIQUE (instructor_id, course_id, request_id),
  FOREIGN KEY (course_id, instructor_id) REFERENCES courses(id, instructor_id)
);
CREATE TABLE intake_events (
  id uuid PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now(),
  instructor_id uuid NOT NULL REFERENCES instructors(id),
  course_id uuid NOT NULL,
  submission_id uuid NOT NULL,
  generation integer NOT NULL CHECK (generation >= 0),
  action text NOT NULL CHECK (action IN ('created','privacy_review')),
  private_object uuid NOT NULL,
  UNIQUE (submission_id, generation),
  FOREIGN KEY (submission_id, course_id, instructor_id) REFERENCES intake_submissions(id, course_id, instructor_id)
);
CREATE INDEX intake_course ON intake_submissions (instructor_id, course_id, id);
ALTER TABLE intake_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE intake_submissions FORCE ROW LEVEL SECURITY;
CREATE POLICY own_intake ON intake_submissions USING (instructor_id::text = current_setting('edu.instructor_id', true));
ALTER TABLE intake_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE intake_events FORCE ROW LEVEL SECURITY;
CREATE POLICY own_intake_events ON intake_events USING (instructor_id::text = current_setting('edu.instructor_id', true));
