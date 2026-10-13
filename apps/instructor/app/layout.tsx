import type { ReactNode } from "react";
import "./style.css";
export const metadata = { title: "edu · Instructor workspace", description: "Rubric-grounded writing review" };
export default function Layout({ children }: { children: ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
