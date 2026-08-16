export function PlaceholderPage({ title, note }: { title: string; note: string }) {
  return (
    <div>
      <h1 className="font-display text-2xl font-semibold text-fg">{title}</h1>
      <p className="mt-2 text-sm text-muted">{note}</p>
    </div>
  );
}