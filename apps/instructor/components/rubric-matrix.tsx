import type { Criterion } from "../lib/workspace";
// Adapted presentation pattern from the user-supplied Teacher Dashboard RubricDisplay.
export function RubricMatrix({ criteria }: { criteria: Criterion[] }) {
  const levels = [...new Set(criteria.flatMap(c => c.levels.map(l => l.name)))];
  return <div className="table-scroll"><table><caption>Draft rubric · instructor activation required</caption><thead><tr><th scope="col">Criterion</th>{levels.map(l => <th scope="col" key={l}>{l}</th>)}</tr></thead><tbody>{criteria.map(c => <tr key={c.id}><th scope="row">{c.name}</th>{levels.map(l => { const level = c.levels.find(v => v.name === l); return <td key={l}>{level ? <>{level.description}<small>{level.points} points</small></> : "Not defined"}</td>; })}</tr>)}</tbody></table></div>;
}
