"use client";

import { Eye, EyeOff } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function SystemMessageToggle({
  showSystem,
  onToggle,
  count,
}: {
  showSystem: boolean;
  onToggle: () => void;
  count: number;
}) {
  if (count === 0) return null;
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={onToggle}
      className="gap-1.5 text-muted-foreground"
    >
      {showSystem ? (
        <EyeOff className="h-4 w-4" />
      ) : (
        <Eye className="h-4 w-4" />
      )}
      {showSystem ? "Hide" : "Show"} events
      <Badge variant="secondary" className="ml-1 px-1.5 py-0 text-xs">
        {count}
      </Badge>
    </Button>
  );
}
