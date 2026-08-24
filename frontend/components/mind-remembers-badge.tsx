"use client";

import { Brain } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { collectConversationBrandRules } from "@/lib/insights";

type Message = { role: string; text: string };

export default function MindRemembersBadge({ messages }: { messages: Message[] }) {
  const rules = collectConversationBrandRules(messages ?? []);

  if (rules.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Badge variant="outline" className="border-violet-500/30 bg-violet-500/10 text-violet-300">
        <Brain className="mr-1 h-3 w-3" />
        Mind remembers
      </Badge>
      {rules.map((rule, index) => (
        <Badge
          key={index}
          variant="outline"
          className="border-border/60 bg-background/60 text-xs text-muted-foreground"
          title={rule.text}
        >
          {rule.text.length > 40 ? `${rule.text.slice(0, 40)}…` : rule.text}
        </Badge>
      ))}
    </div>
  );
}
