const isDev = process.env.NODE_ENV === "development";

export function debugLog(...args: unknown[]): void {
  if (isDev) console.log("[debug]", ...args);
}

export function debugWarn(...args: unknown[]): void {
  if (isDev) console.warn("[debug]", ...args);
}

export function debugError(...args: unknown[]): void {
  if (isDev) console.error("[debug]", ...args);
}
