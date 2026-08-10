import { Brain, FlaskConical, ListVideo, Sparkles } from "lucide-react";

const metricCards = [
  { label: "Total Clips", icon: ListVideo },
  { label: "Active A/B Tests", icon: FlaskConical },
  { label: "Avg Virality", icon: Sparkles },
  { label: "Total Insights", icon: Brain },
];

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold text-slate-100">Dashboard</h1>
      <div className="grid grid-cols-4 gap-4">
        {metricCards.map((card) => (
          <div
            key={card.label}
            className="rounded-xl border border-slate-800 bg-slate-900 p-5"
          >
            <card.icon className="mb-3 h-5 w-5 text-indigo-400" />
            <p className="text-sm text-slate-400">{card.label}</p>
            <p className="mt-1 text-3xl font-semibold text-slate-100">—</p>
          </div>
        ))}
      </div>
    </div>
  );
}