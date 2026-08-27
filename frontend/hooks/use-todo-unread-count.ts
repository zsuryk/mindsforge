"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchTodoUnreadCount } from "@/lib/api";

const POLL_INTERVAL_MS = 30_000;

export function useTodoUnreadCount(): {
  count: number;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
} {
  const [count, setCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const load = useCallback(async () => {
    try {
      const c = await fetchTodoUnreadCount();
      if (mountedRef.current) {
        setCount(c);
        setError(null);
      }
    } catch {
      if (mountedRef.current) {
        setError("Failed to load unread count");
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    load();

    const id = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      mountedRef.current = false;
      clearInterval(id);
    };
  }, [load]);

  return { count, isLoading, error, refetch: load };
}
