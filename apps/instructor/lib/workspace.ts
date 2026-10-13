export type Criterion = { id: string; name: string; levels: { name: string; description: string; points: number }[] };
export type Assignment = { id: string; title: string; instructions: string; criteria: Criterion[] };
export type Course = { id: string; title: string; objectives: string[]; assignments: Assignment[] };
export type Submission = { id: string; courseId: string; assignmentId: string; studentRef: string; text: string; reflection: string; match: "matched" | "unmatched"; privacy: "pending" | "reviewed"; feedback: string; enrollmentId?: string; excluded?: boolean };
export type Workspace = { courses: Course[]; submissions: Submission[] };
// All records are invented; this fixed fixture is the only intake source in this slice.
export function syntheticWorkspace(): Workspace {
  const criteria: Criterion[] = [{ id: "claim", name: "Claim and reasoning", levels: [
    { name: "Developing", description: "A claim needs a clear reason and connection to evidence.", points: 1 },
    { name: "Proficient", description: "A focused claim connects reasons and evidence.", points: 2 }
  ] }, { id: "evidence", name: "Evidence", levels: [
    { name: "Developing", description: "Examples need interpretation.", points: 1 },
    { name: "Proficient", description: "Specific examples support the reasoning.", points: 2 }
  ] }];
  return { courses: [
    { id: "composition", title: "Composition · Section A", objectives: ["Develop a defensible claim", "Explain evidence"], assignments: [
      { id: "argument", title: "A place for public reading", instructions: "Argue how a fictional town could make reading more accessible. Support your position with specific examples.", criteria },
      { id: "revision", title: "Revision reflection", instructions: "Explain one revision and its effect on the reader.", criteria }
    ] },
    { id: "rhetoric", title: "Rhetoric · Section B", objectives: ["Analyze audience and purpose"], assignments: [
      { id: "audience", title: "Reading an invitation", instructions: "Analyze how a fictional invitation addresses its audience.", criteria }
    ] }
  ], submissions: [
    { id: "essay-1", courseId: "composition", assignmentId: "argument", studentRef: "Writer 01", enrollmentId: "enroll-1", text: "The town should open a reading room after sunset. Evening hours would give shift workers a place to read. A shared shelf could make books easier to find.", reflection: "I added the example about evening hours to explain who benefits.", match: "matched", privacy: "pending", feedback: "" },
    { id: "essay-2", courseId: "composition", assignmentId: "argument", studentRef: "Unmatched fictional record", text: "A mobile book cart could visit the town square. The cart would bring short stories to people waiting for the bus.", reflection: "I want to connect my example more clearly to the claim.", match: "unmatched", privacy: "pending", feedback: "" },
    { id: "essay-3", courseId: "rhetoric", assignmentId: "audience", studentRef: "Writer 03", enrollmentId: "enroll-3", text: "The invitation uses a welcoming question to address first-time visitors.", reflection: "I focused on the opening sentence.", match: "matched", privacy: "pending", feedback: "" }
  ] };
}
export const snippets = [
  { id: "reason", category: "Reasoning", text: "Explain how this example supports your claim." },
  { id: "reader", category: "Audience", text: "What does your reader need to understand before this point?" },
  { id: "revision", category: "Revision", text: "Name one change you will make and explain its purpose." }
];
export function visibleSubmissions(work: Workspace, courseId: string, assignmentId: string) {
  return work.submissions.filter(s => s.courseId === courseId && s.assignmentId === assignmentId);
}
export function updateSubmission(work: Workspace, courseId: string, assignmentId: string, id: string, change: Partial<Pick<Submission, "privacy" | "feedback">>): Workspace {
  return { ...work, submissions: work.submissions.map(s => s.id === id && s.courseId === courseId && s.assignmentId === assignmentId ? { ...s, ...change } : s) };
}
export function holds(s: Submission): string[] {
  return [...(s.match === "unmatched" ? ["Enrollment match required"] : []), ...(s.privacy === "pending" ? ["Contextual privacy review required"] : []), "Rubric activation pending", "Assessment route unqualified", "Instructor release unavailable"];
}
