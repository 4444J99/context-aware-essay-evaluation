CREATE TABLE assignments (
 id uuid PRIMARY KEY, instructor_id uuid NOT NULL REFERENCES instructors(id), course_id uuid NOT NULL,
 section_id uuid NOT NULL, label text NOT NULL CHECK(length(label) BETWEEN 1 AND 120),
 UNIQUE(id,course_id,instructor_id),
 FOREIGN KEY(section_id,course_id,instructor_id) REFERENCES sections(id,course_id,instructor_id)
);
CREATE TABLE assignment_enrollments (
 assignment_id uuid NOT NULL, enrollment_id uuid NOT NULL, course_id uuid NOT NULL, instructor_id uuid NOT NULL,
 PRIMARY KEY(assignment_id,enrollment_id), UNIQUE(assignment_id,enrollment_id,course_id,instructor_id),
 FOREIGN KEY(assignment_id,course_id,instructor_id) REFERENCES assignments(id,course_id,instructor_id),
 FOREIGN KEY(enrollment_id,course_id,instructor_id) REFERENCES enrollments(id,course_id,instructor_id)
);
ALTER TABLE intake_submissions ADD COLUMN assignment_id uuid, ADD COLUMN enrollment_id uuid,
 ADD COLUMN excluded boolean NOT NULL DEFAULT false,
 ADD CONSTRAINT mapping_pair CHECK((assignment_id IS NULL) = (enrollment_id IS NULL)),
 ADD CONSTRAINT mapping_scope FOREIGN KEY(assignment_id,enrollment_id,course_id,instructor_id)
 REFERENCES assignment_enrollments(assignment_id,enrollment_id,course_id,instructor_id);
CREATE UNIQUE INDEX intake_active_mapping ON intake_submissions(assignment_id,enrollment_id) WHERE NOT excluded AND assignment_id IS NOT NULL;
ALTER TABLE intake_events DROP CONSTRAINT intake_events_action_check;
ALTER TABLE intake_events ADD CONSTRAINT intake_events_action_check CHECK(action IN ('created','privacy_review','mapping','exclude','restore'));
ALTER TABLE assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE assignments FORCE ROW LEVEL SECURITY;
CREATE POLICY instructor_scope ON assignments USING(instructor_id = nullif(current_setting('edu.instructor_id',true),'')::uuid) WITH CHECK(instructor_id = nullif(current_setting('edu.instructor_id',true),'')::uuid);
ALTER TABLE assignment_enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE assignment_enrollments FORCE ROW LEVEL SECURITY;
CREATE POLICY instructor_scope ON assignment_enrollments USING(instructor_id = nullif(current_setting('edu.instructor_id',true),'')::uuid) WITH CHECK(instructor_id = nullif(current_setting('edu.instructor_id',true),'')::uuid);
