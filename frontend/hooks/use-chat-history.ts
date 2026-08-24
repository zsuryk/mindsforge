"use client";

import { useEffect, useState } from "react";

import { ChatMessage, fetchChatHistory } from "@/lib/api";

export function useChatHistory(): {
  messages: ChatMessage[];
  error: string | null;
} {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchChatHistory()
      .then((result) => {
        if (!cancelled) setMessages(result.messages);
      })
      .catch(() => {
        if (!cancelled) setError("Failed to load chat history");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { messages, error };
}
