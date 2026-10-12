import { Dashboard } from "../components/dashboard";
import { backendOrigin } from "../lib/gateway";
export const dynamic = "force-dynamic";
export default function Page() { return <Dashboard protectedConfigured={backendOrigin(process.env.EDU_BACKEND_ORIGIN, process.env.NODE_ENV === "production") !== null} />; }
