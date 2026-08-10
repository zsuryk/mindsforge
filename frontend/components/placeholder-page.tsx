export function PlaceholderPage({ title, note }: { title: string; note: string }) {
  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-100">{title}</h1>
      <p className="mt-2 text-sm text-slate-400">{note}</p>
    </div>
  );
}