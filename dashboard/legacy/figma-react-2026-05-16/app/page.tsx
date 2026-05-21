import { ExperimentDashboard } from "@/components/experiment-dashboard";
import { dashboardData } from "@/lib/dashboard-data";

export default function Page() {
  return <ExperimentDashboard data={dashboardData} />;
}
