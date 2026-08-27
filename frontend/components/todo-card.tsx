"use client";

import { useEffect, useRef, useState } from "react";
import {
  Archive,
  BarChart3,
  FileText,
  Lightbulb,
  TrendingUp,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { TodoItem, TodoItemType } from "@/lib/api";
import { cn } from "@/lib/utils";

const MARK_READ_DELAY_MS = 2_000;

const TYPE_CONFIG: Record<
  TodoItemType,
  { icon: typeof FileText; label: string; color: string }
> = {
  weekly_digest: {
    icon: FileText,
    label: "Weekly Digest",
    color: "text-blue-500 bg-blue-500/10",
  },
  clip_suggestion: {
    icon: Lightbulb,
    label: "Clip Suggestion",
    color: "text-amber-500 bg-amber-500/10",
  },
  experiment_result: {
    icon: BarChart3,
    label: "Experiment Result",
    color: "text-emerald-500 bg-emerald-500/10",
  },
  trend_alert: {
    icon: TrendingUp,
    label: "Trend Alert",
    color: "text-purple-500 bg-purple-500/10",
  },
};

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

interface TodoCardProps {
  item: TodoItem;
  onMarkRead: (id: string) => void;
  onArchive: (id: string) => void;
}

export function TodoCard({ item, onMarkRead, onArchive }: TodoCardProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (item.is_read) return;

    timerRef.current = setTimeout(() => {
      onMarkRead(item.id);
    }, MARK_READ_DELAY_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [item.id, item.is_read, onMarkRead]);

  const config = TYPE_CONFIG[item.type];
  const Icon = config.icon;

  return (
    <Card
      className={cn(
        "relative p-4 transition-colors",
        !item.is_read && "border-l-2 border-l-primary",
      )}
      data-testid="todo-card"
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
            config.color,
          )}
        >
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold leading-snug text-foreground">
                  {item.title}
                </h3>
                {!item.is_read && (
                  <span className="h-2 w-2 shrink-0 rounded-full bg-primary" />
                )}
              </div>
              <Badge variant="outline" className="mt-1 text-[10px]">
                {config.label}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <span className="shrink-0 text-xs text-muted-foreground">
                {relativeTime(item.created_at)}
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                onClick={() => setConfirmOpen(true)}
                aria-label="Archive item"
              >
                <Archive className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
          <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-muted-foreground">
            {item.body}
          </p>
          {item.action_url && item.action_label && (
            <div className="mt-3">
              <Button
                asChild
                size="sm"
                variant="outline"
                className="h-7 text-xs"
              >
                <a href={item.action_url}>{item.action_label}</a>
              </Button>
            </div>
          )}
        </div>
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Archive item?</DialogTitle>
            <DialogDescription>
              This will remove the item from your feed. You won&apos;t be able to
              unarchive it.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setConfirmOpen(false);
                onArchive(item.id);
              }}
            >
              Archive
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
