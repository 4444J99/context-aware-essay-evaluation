CREATE TABLE instructors (
  id uuid PRIMARY KEY,
  issuer text NOT NULL,
  subject text NOT NULL,
  active boolean NOT NULL DEFAULT true,
  UNIQUE (issuer, subject)
);
CREATE TABLE terms (
  id uuid PRIMARY KEY,
  instructor_id uuid NOT NULL REFERENCES instructors(id),
  label text NOT NULL CHECK (length(label) BETWEEN 1 AND 160),
  starts_on date NOT NULL,
  ends_on date NOT NULL CHECK (ends_on >= starts_on),
  UNIQUE (id, instructor_id)
);
CREATE TABLE courses (
  id uuid PRIMARY KEY,
  instructor_id uuid NOT NULL REFERENCES instructors(id),
  term_id uuid NOT NULL,
  title text NOT NULL CHECK (length(title) BETWEEN 1 AND 160),
  UNIQUE (id, instructor_id),
  FOREIGN KEY (term_id, instructor_id) REFERENCES terms(id, instructor_id)
);
CREATE TABLE sections (
  id uuid PRIMARY KEY,
  instructor_id uuid NOT NULL REFERENCES instructors(id),
  course_id uuid NOT NULL,
  label text NOT NULL CHECK (length(label) BETWEEN 1 AND 160),
  UNIQUE (id, course_id, instructor_id),
  FOREIGN KEY (course_id, instructor_id) REFERENCES courses(id, instructor_id)
);
CREATE TABLE enrollments (
  id uuid PRIMARY KEY,
  instructor_id uuid NOT NULL REFERENCES instructors(id),
  course_id uuid NOT NULL,
  section_id uuid NOT NULL,
  student_ref uuid NOT NULL,
  UNIQUE (section_id, student_ref),
  UNIQUE (id, course_id, instructor_id),
  FOREIGN KEY (section_id, course_id, instructor_id) REFERENCES sections(id, course_id, instructor_id)
);
CREATE TABLE external_references (
  id uuid PRIMARY KEY,
  instructor_id uuid NOT NULL REFERENCES instructors(id),
  course_id uuid NOT NULL,
  source text NOT NULL CHECK (source IN ('teacher_dashboard', 'aetheria', 'edu')),
  kind text NOT NULL CHECK (kind IN ('course', 'section', 'enrollment')),
  external_id text NOT NULL CHECK (length(external_id) BETWEEN 1 AND 128),
  target_id uuid NOT NULL,
  UNIQUE (instructor_id, course_id, source, kind, external_id),
  FOREIGN KEY (course_id, instructor_id) REFERENCES courses(id, instructor_id)
);
CREATE INDEX courses_term ON courses (instructor_id, term_id);
CREATE INDEX sections_course ON sections (instructor_id, course_id);
CREATE INDEX enrollments_section ON enrollments (instructor_id, course_id, section_id);
ALTER TABLE instructors ENABLE ROW LEVEL SECURITY;
ALTER TABLE instructors FORCE ROW LEVEL SECURITY;
CREATE POLICY own_identity ON instructors USING (
  issuer = current_setting('edu.issuer', true) AND subject = current_setting('edu.subject', true)
);
ALTER TABLE terms ENABLE ROW LEVEL SECURITY;
ALTER TABLE terms FORCE ROW LEVEL SECURITY;
CREATE POLICY own_terms ON terms USING (instructor_id::text = current_setting('edu.instructor_id', true));
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses FORCE ROW LEVEL SECURITY;
CREATE POLICY own_courses ON courses USING (instructor_id::text = current_setting('edu.instructor_id', true));
ALTER TABLE sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE sections FORCE ROW LEVEL SECURITY;
CREATE POLICY own_sections ON sections USING (instructor_id::text = current_setting('edu.instructor_id', true));
ALTER TABLE enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE enrollments FORCE ROW LEVEL SECURITY;
CREATE POLICY own_enrollments ON enrollments USING (instructor_id::text = current_setting('edu.instructor_id', true));
ALTER TABLE external_references ENABLE ROW LEVEL SECURITY;
ALTER TABLE external_references FORCE ROW LEVEL SECURITY;
CREATE POLICY own_references ON external_references USING (instructor_id::text = current_setting('edu.instructor_id', true));
CREATE FUNCTION validate_external_target() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.kind = 'course' AND NEW.target_id = NEW.course_id) OR
     (NEW.kind = 'section' AND EXISTS (SELECT 1 FROM sections WHERE id=NEW.target_id AND course_id=NEW.course_id AND instructor_id=NEW.instructor_id)) OR
     (NEW.kind = 'enrollment' AND EXISTS (SELECT 1 FROM enrollments WHERE id=NEW.target_id AND course_id=NEW.course_id AND instructor_id=NEW.instructor_id)) THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'reference_target_out_of_scope' USING ERRCODE = '23503';
END;
$$;
CREATE TRIGGER external_target_scope BEFORE INSERT OR UPDATE ON external_references
FOR EACH ROW EXECUTE FUNCTION validate_external_target();
