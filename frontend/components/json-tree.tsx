import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

function isObject(value: JsonValue): value is { [key: string]: JsonValue } {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isExpandable(value: JsonValue): value is JsonValue[] | { [key: string]: JsonValue } {
  return Array.isArray(value) || isObject(value);
}

function isEmpty(value: JsonValue): boolean {
  return isObject(value)
    ? Object.keys(value).length === 0
    : Array.isArray(value) && value.length === 0;
}

function entriesOf(value: JsonValue): [string | null, JsonValue][] {
  if (isObject(value)) {
    return Object.entries(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => [null, item]);
  }
  return [];
}

function PrimitiveToken({ value }: { value: JsonPrimitive }) {
  const className =
    typeof value === "string"
      ? "text-emerald-300"
      : typeof value === "number"
        ? "text-amber-300"
        : value === null
          ? "text-rose-400"
          : "text-fuchsia-300";
  const text = typeof value === "string" ? JSON.stringify(value) : String(value);
  return <span className={className}>{text}</span>;
}

function JsonNode({
  name,
  value,
  depth,
}: {
  name: string | null;
  value: JsonValue;
  depth: number;
}) {
  const [open, setOpen] = useState(depth === 0);
  const expandable = isExpandable(value);
  const indentation = "  ".repeat(depth);

  return (
    <div>
      <div className="flex items-start">
        <span className="whitespace-pre">{indentation}</span>
        {expandable ? (
          <button
            type="button"
            onClick={() => setOpen(!open)}
            aria-expanded={open}
            className="mt-0.5 mr-1 text-muted hover:text-fg"
          >
            {open ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
          </button>
        ) : (
          <span className="mr-1 w-3.5" />
        )}
        <span className="break-all font-mono text-sm leading-6">
          {name !== null && (
            <>
              <span className="text-mind">{JSON.stringify(name)}</span>
              <span className="text-muted">: </span>
            </>
          )}
          {isExpandable(value) ? (
            <>
              <span className="text-muted">{Array.isArray(value) ? "[" : "{"}</span>
              {!isEmpty(value) && <span className="text-subtle">…</span>}
              <span className="text-muted">{Array.isArray(value) ? "]" : "}"}</span>
              {!isEmpty(value) && (
                <span className="ml-2 text-xs text-subtle">
                  {Array.isArray(value)
                    ? `${value.length} item${value.length === 1 ? "" : "s"}`
                    : `${Object.keys(value).length} key${Object.keys(value).length === 1 ? "" : "s"}`}
                </span>
              )}
            </>
          ) : (
            <PrimitiveToken value={value} />
          )}
        </span>
      </div>
      {expandable && open && !isEmpty(value) && (
        <div className="ml-[1.375rem] border-l border-edge/70 pl-2">
          {entriesOf(value).map(([childName, childValue], index) => (
            <JsonNode
              key={childName ?? index}
              name={childName}
              value={childValue}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function JsonTree({ data }: { data: unknown }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-edge bg-background p-4">
      <JsonNode name={null} value={data as JsonValue} depth={0} />
    </div>
  );
}
