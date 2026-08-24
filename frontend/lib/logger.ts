const isDev = process.env.NODE_ENV === "development";

export function debugLog(...args: unknown[]): void {
  if (isDev) console.log("[debug]", ...args);
}
