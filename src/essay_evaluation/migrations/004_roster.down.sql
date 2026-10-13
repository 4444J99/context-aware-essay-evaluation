DROP TABLE assignment_roster_versions;
ALTER TABLE assignment_enrollments DROP COLUMN active;
ALTER TABLE assignments DROP COLUMN roster_generation;
