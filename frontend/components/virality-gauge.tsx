import { PolarAngleAxis, RadialBar, RadialBarChart } from "recharts";

export function viralityColor(score: number): string {
  if (score < 40) return "#fb7185";
  if (score < 70) return "#fbbf24";
  return "#34d399";
}

export function viralityLabel(score: number): string {
  if (score < 40) return "Low engagement potential — needs a stronger hook";
  if (score < 70) return "Solid potential — try the suggested hooks";
  return "High potential — ready to launch";
}

export default function ViralityGauge({ score }: { score: number | null }) {
  const value = score ?? 0;
  const color = viralityColor(value);
  return (
    <div className="relative mx-auto h-44 w-44">
      <RadialBarChart
        width={176}
        height={176}
        cx="50%"
        cy="50%"
        innerRadius="72%"
        outerRadius="100%"
        startAngle={90}
        endAngle={-270}
        data={[{ name: "virality", value, fill: color }]}
      >
        <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
        <RadialBar
          dataKey="value"
          cornerRadius={10}
          background={{ fill: "hsl(var(--elevated))" }}
        />
      </RadialBarChart>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {score === null ? (
          <span className="text-2xl text-muted-foreground">—</span>
        ) : (
          <span className="font-display text-4xl font-semibold tracking-tight text-foreground">
            {score}
          </span>
        )}
        <span className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
          virality
        </span>
      </div>
    </div>
  );
}
