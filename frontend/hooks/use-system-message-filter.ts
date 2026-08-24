"use client";

import { useCallback, useMemo, useState } from "react";

import { ChatMessage } from "@/lib/api";

const STORAGE_KEY = "mindsforge:show-system-messages";

function readInitialValue(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export function useSystemMessageFilter(messages: ChatMessage[]): {
  showSystem: boolean;
  toggle: () => void;
  systemCount: number;
  filtered: ChatMessage[];
} {
  const [showSystem, setShowSystem] = useState(readInitialValue);

  const toggle = useCallback(() => {
    setShowSystem((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem(STORAGE_KEY, String(next));
      } catch {
        // localStorage unavailable — state still toggles
      }
      return next;
    });
  }, []);

  const systemCount = useMemo(
    () => messages.filter((m) => m.role === "system").length,
    [messages],
  );

  const filtered = useMemo(
    () =>
      showSystem
        ? messages
        : messages.filter((m) => m.role !== "system"),
    [messages, showSystem],
  );

  return { showSystem, toggle, systemCount, filtered };
}
