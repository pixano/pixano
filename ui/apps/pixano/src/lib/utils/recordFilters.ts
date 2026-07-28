/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Client-side helpers for the explorer's record filters.
 *
 * A filter is serialized to the `col:op:value` grammar the backend compiler
 * accepts (see `src/pixano/api/query.py`). List-valued operators (`in`/`nin`,
 * `between`) join their values with commas, escaping literal commas as `\,`.
 */

export interface RecordFilter {
  col: string;
  op: string;
  /** For list operators (`in`/`nin`/`between`) this holds multiple values. */
  values: string[];
}

/** Operators whose value is a comma-separated list. */
export const LIST_OPERATORS = new Set(["in", "nin", "between"]);

/** Human-readable labels for each operator, per column type where it matters. */
export const OPERATOR_LABELS: Record<string, string> = {
  eq: "is",
  ne: "is not",
  lt: "<",
  lte: "≤",
  gt: ">",
  gte: "≥",
  in: "is any of",
  nin: "is none of",
  contains: "contains",
  between: "between",
};

export function isListOperator(op: string): boolean {
  return LIST_OPERATORS.has(op);
}

function escapeListValue(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/,/g, "\\,");
}

function splitListValue(raw: string): string[] {
  const items: string[] = [];
  let current = "";
  let escaped = false;
  for (const char of raw) {
    if (escaped) {
      current += char;
      escaped = false;
    } else if (char === "\\") {
      escaped = true;
    } else if (char === ",") {
      items.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  if (escaped) current += "\\";
  items.push(current);
  return items;
}

/** Serialize one filter into a `col:op:value` token. */
export function serializeFilter(filter: RecordFilter): string {
  const value = isListOperator(filter.op)
    ? filter.values.map(escapeListValue).join(",")
    : (filter.values[0] ?? "");
  return `${filter.col}:${filter.op}:${value}`;
}

/** Serialize a list of filters into repeated `filter=` query values. */
export function serializeFilters(filters: RecordFilter[]): string[] {
  return filters.map(serializeFilter);
}

/**
 * Parse a `col:op:value` token. The value may itself contain `:` (only the
 * first two colons are structural), matching the backend's `_split_filter`.
 * Returns `null` for a token that isn't of the expected shape.
 */
export function parseFilter(token: string): RecordFilter | null {
  const first = token.indexOf(":");
  const second = token.indexOf(":", first + 1);
  if (first === -1 || second === -1) return null;
  const col = token.slice(0, first);
  const op = token.slice(first + 1, second);
  const rawValue = token.slice(second + 1);
  if (!col || !op) return null;
  const values = isListOperator(op) ? splitListValue(rawValue) : [rawValue];
  return { col, op, values };
}

export function parseFilters(tokens: string[]): RecordFilter[] {
  return tokens.map(parseFilter).filter((f): f is RecordFilter => f !== null);
}

/**
 * Detect a legacy raw-SQL filter string (from the deprecated free-text where
 * box) so callers can route it to the `where=` param instead of `filter=`.
 * A `col:op:value` token never contains SQL operators or spaces around `=`.
 */
export function looksLikeRawSql(text: string): boolean {
  const trimmed = text.trim();
  if (!trimmed) return false;
  // Structured tokens have exactly the `a:b:c` shape with no SQL syntax.
  if (/^[A-Za-z_][A-Za-z0-9_]*:[a-z]+:.*$/.test(trimmed)) return false;
  return /[=<>]|\bAND\b|\bOR\b|\bLIKE\b|\bIN\b|'/i.test(trimmed);
}
