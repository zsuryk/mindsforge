"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Bell } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { TodoCard } from "@/components/todo-card";
import {
  fetchTodos,
  updateTodo,
  type TodoItem,
  type TodoItemType,
} from "@/lib/api";
import { useTodoUnreadCount } from "@/hooks/use-todo-unread-count";

const POLL_INTERVAL_MS = 30_000;

type FilterType = "all" | "unread" | TodoItemType;

function filterToParams(filter: FilterType) {
  if (filter === "unread") return { unread: true as const };
  if (filter === "all") return {};
  return { type: filter };
}

export default function TodoPage() {
  const [items, setItems] = useState<TodoItem[]>([]);
  const [filter, setFilter] = useState<FilterType>("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { count: unreadCount, refetch: refetchUnread } = useTodoUnreadCount();
  const mountedRef = useRef(true);

  const load = useCallback(async () => {
    try {
      const data = await fetchTodos(filterToParams(filter));
      if (mountedRef.current) {
        setItems(data.items);
        setError(null);
      }
    } catch {
      if (mountedRef.current) {
        setError("Failed to load todo items");
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [filter]);

  useEffect(() => {
    mountedRef.current = true;
    setIsLoading(true);
    load();

    const id = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      mountedRef.current = false;
      clearInterval(id);
    };
  }, [load]);

  const handleMarkRead = useCallback(
    async (id: string) => {
      setItems((prev) =>
        prev.map((item) =>
          item.id === id ? { ...item, is_read: true } : item,
        ),
      );
      try {
        await updateTodo(id, { is_read: true });
        refetchUnread();
      } catch {
        // revert on failure
        setItems((prev) =>
          prev.map((item) =>
            item.id === id ? { ...item, is_read: false } : item,
          ),
        );
      }
    },
    [refetchUnread],
  );

  const handleArchive = useCallback(
    async (id: string) => {
      setItems((prev) => prev.filter((item) => item.id !== id));
      try {
        await updateTodo(id, { is_archived: true });
        refetchUnread();
      } catch {
        // revert on failure
        load();
      }
    },
    [load, refetchUnread],
  );

  const totalCount = items.length;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <Badge
          variant="outline"
          className="uppercase tracking-[0.18em] text-xs"
        >
          Studio
        </Badge>
        <div className="mt-4 flex items-baseline gap-3">
          <h1 className="font-display text-3xl font-semibold tracking-tight text-foreground">
            Todo
          </h1>
          {totalCount > 0 && (
            <span className="text-sm text-muted-foreground">
              {totalCount} item{totalCount === 1 ? "" : "s"}
              {unreadCount > 0 && ` · ${unreadCount} unread`}
            </span>
          )}
        </div>
      </header>

      <div className="flex items-center gap-3">
        <Select
          value={filter}
          onChange={(e) => setFilter(e.target.value as FilterType)}
          aria-label="Filter todo items"
          className="w-48"
        >
          <option value="all">All</option>
          <option value="unread">Unread</option>
          <option value="weekly_digest">Weekly Digest</option>
          <option value="clip_suggestion">Clip Suggestion</option>
          <option value="experiment_result">Experiment Result</option>
          <option value="trend_alert">Trend Alert</option>
        </Select>
        <Button variant="ghost" size="sm" onClick={() => load()}>
          Refresh
        </Button>
      </div>

      {error && (
        <Card className="border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          {error}
        </Card>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="h-28 animate-pulse bg-muted/40" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border/40 py-16">
          <Bell className="h-10 w-10 text-subtle" />
          <p className="mt-4 text-center text-sm text-muted-foreground">
            No todo items yet — your Mind will notify you here when there&apos;s
            something important.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <TodoCard
              key={item.id}
              item={item}
              onMarkRead={handleMarkRead}
              onArchive={handleArchive}
            />
          ))}
        </div>
      )}
    </div>
  );
}
