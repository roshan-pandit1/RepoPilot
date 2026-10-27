import { Dashboard } from "@/components/dashboard";
import { demoEnabled } from "@/lib/server-api";
export const dynamic = "force-dynamic";
export default function Page() { return <Dashboard demo={demoEnabled()} />; }
