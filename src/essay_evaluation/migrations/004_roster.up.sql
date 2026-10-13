ALTER TABLE assignments ADD COLUMN roster_generation integer NOT NULL DEFAULT 0 CHECK(roster_generation >= 0);
ALTER TABLE assignment_enrollments ADD COLUMN active boolean NOT NULL DEFAULT true;
CREATE TABLE assignment_roster_versions (
 assignment_id uuid NOT NULL, course_id uuid NOT NULL, instructor_id uuid NOT NULL,
 generation integer NOT NULL CHECK(generation >= 0), enrollment_ids uuid[] NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(assignment_id,generation),
 FOREIGN KEY(assignment_id,course_id,instructor_id) REFERENCES assignments(id,course_id,instructor_id)
);
INSERT INTO assignment_roster_versions(assignment_id,course_id,instructor_id,generation,enrollment_ids)
 SELECT a.id,a.course_id,a.instructor_id,0,coalesce(array_agg(e.enrollment_id ORDER BY e.enrollment_id) FILTER(WHERE e.enrollment_id IS NOT NULL),'{}'::uuid[])
 FROM assignments a LEFT JOIN assignment_enrollments e ON e.assignment_id=a.id GROUP BY a.id;
ALTER TABLE assignment_roster_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE assignment_roster_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY instructor_scope ON assignment_roster_versions USING(instructor_id = nullif(current_setting('edu.instructor_id',true),'')::uuid) WITH CHECK(instructor_id = nullif(current_setting('edu.instructor_id',true),'')::uuid);
