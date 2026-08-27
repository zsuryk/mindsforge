"use client";

import { Bell } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useTodoUnreadCount } from "@/hooks/use-todo-unread-count";

export default function TodoPage() {
  const { count } = useTodoUnreadCount();

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <header>
        <Badge variant="outline" className="uppercase tracking-[0.18em] text-xs">
          Studio
        </Badge>
        <h1 className="mt-4 font-display text-3xl font-semibold tracking-tight text-foreground">
          Todo
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {count > 0
            ? `You have ${count} unread item${count === 1 ? "" : "s"}.`
            : "All caught up — no unread items."}
        </p>
      </header>

      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border/40 py-16">
        <Bell className="h-10 w-10 text-subtle" />
        <p className="mt-4 text-sm text-muted-foreground">
          Todo feed coming soon.
        </p>
      </div>
    </div>
  );
}
