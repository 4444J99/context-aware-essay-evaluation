"use client";
import { useState } from "react";
import { snippets } from "../lib/workspace";
// Retains the predecessor's category/content browsing concept, without storage or model hooks.
export function SnippetBank({ onInsert }: { onInsert: (text: string) => void }) {
  const [query, setQuery] = useState("");
  const matches = snippets.filter(s => `${s.category} ${s.text}`.toLowerCase().includes(query.toLowerCase()));
  return <section aria-labelledby="snippet-title"><h3 id="snippet-title">Feedback snippets</h3><label>Search snippets<input value={query} onChange={e => setQuery(e.target.value)} /></label><ul className="snippets">{matches.map(s => <li key={s.id}><small>{s.category}</small><p>{s.text}</p><button onClick={() => onInsert(s.text)}>Insert {s.category.toLowerCase()} snippet</button></li>)}</ul>{matches.length === 0 && <p>No matching snippets.</p>}</section>;
}
