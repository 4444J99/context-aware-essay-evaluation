ALTER TABLE intake_events DROP CONSTRAINT intake_events_action_check;
ALTER TABLE intake_events ADD CONSTRAINT intake_events_action_check CHECK(action IN ('created','privacy_review'));
DROP INDEX intake_active_mapping;
ALTER TABLE intake_submissions DROP CONSTRAINT mapping_scope, DROP CONSTRAINT mapping_pair,
 DROP COLUMN assignment_id, DROP COLUMN enrollment_id, DROP COLUMN excluded;
DROP TABLE assignment_enrollments;
DROP TABLE assignments;
