/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export type SearchableEntity = {
  id: string;
  table_info: {
    name: string;
    base_schema: string;
    group?: string;
  };
  data: Record<string, unknown> & { parent_id?: unknown };
};

export type SearchFieldOperator = ":" | "=" | "!=" | ">" | ">=" | "<" | "<=";
export type SearchScalar = string | number | boolean | bigint;
export type SearchFieldValueMap = Map<string, SearchScalar[]>;

export type SearchFieldPredicate = {
  raw: string;
  field: string;
  operator: SearchFieldOperator;
  value: string;
  negated: boolean;
};

export type ParsedSearchQuery = {
  rawTokens: string[];
  textTokens: string[];
  negatedTextTokens: string[];
  predicates: SearchFieldPredicate[];
};

export type TopEntitySearchIndex = {
  corpusByTopEntityId: Map<string, string>;
  fieldValuesByTopEntityId: Map<string, SearchFieldValueMap>;
};

const DIACRITICS_REGEX = /\p{Diacritic}/gu;
const WHITESPACE_REGEX = /\s+/g;
const MAX_NESTED_ITEMS = 20;
const FIELD_PREDICATE_REGEX = /^([a-zA-Z0-9_.-]+)(!=|>=|<=|:|=|>|<)(.+)$/;

export const DEFAULT_IGNORED_ENTITY_DATA_KEYS: ReadonlySet<string> = new Set([
  "item_id",
  "parent_id",
]);

export function normalizeSearchText(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value)
    .normalize("NFKD")
    .replace(DIACRITICS_REGEX, "")
    .toLowerCase()
    .replace(WHITESPACE_REGEX, " ")
    .trim();
}

export function tokenizeSearchQuery(query: string): string[] {
  const normalized = normalizeSearchText(query);
  if (normalized.length === 0) return [];
  return Array.from(new Set(normalized.split(" ").filter(Boolean)));
}

export function normalizeSearchFieldName(fieldName: string): string {
  return normalizeSearchText(fieldName).replace(WHITESPACE_REGEX, "");
}

function isScalarSearchValue(value: unknown): value is string | number | boolean | bigint {
  return (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean" ||
    typeof value === "bigint"
  );
}

function collectValueTerms(value: unknown, terms: string[], depth: number): void {
  if (isScalarSearchValue(value)) {
    terms.push(String(value));
    return;
  }

  if (value instanceof Date) {
    terms.push(value.toISOString());
    return;
  }

  if (depth >= 1 || value === null || value === undefined) {
    return;
  }

  if (Array.isArray(value)) {
    for (const nested of value.slice(0, MAX_NESTED_ITEMS)) {
      collectValueTerms(nested, terms, depth + 1);
    }
    return;
  }

  if (typeof value === "object") {
    let index = 0;
    for (const [nestedKey, nestedValue] of Object.entries(value)) {
      if (index >= MAX_NESTED_ITEMS) break;
      terms.push(nestedKey);
      collectValueTerms(nestedValue, terms, depth + 1);
      index += 1;
    }
  }
}

export function buildEntitySearchText(
  entity: SearchableEntity,
  ignoredDataKeys: ReadonlySet<string> = DEFAULT_IGNORED_ENTITY_DATA_KEYS,
): string {
  const terms: string[] = [entity.id, entity.table_info.base_schema, entity.table_info.name];
  if (entity.table_info.group) {
    terms.push(entity.table_info.group);
  }

  for (const [dataKey, dataValue] of Object.entries(entity.data)) {
    if (ignoredDataKeys.has(dataKey)) continue;
    terms.push(dataKey);
    collectValueTerms(dataValue, terms, 0);
  }

  return normalizeSearchText(terms.join(" "));
}

export function matchesSearchTokens(corpus: string, tokens: readonly string[]): boolean {
  if (tokens.length === 0) return true;
  return tokens.every((token) => corpus.includes(token));
}

function splitQueryIntoRawTokens(query: string): string[] {
  const tokens: string[] = [];
  let currentToken = "";
  let inQuotes = false;

  for (const char of query) {
    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }

    if (!inQuotes && /\s/.test(char)) {
      if (currentToken.length > 0) {
        tokens.push(currentToken);
        currentToken = "";
      }
      continue;
    }

    currentToken += char;
  }

  if (currentToken.length > 0) {
    tokens.push(currentToken);
  }

  return tokens;
}

function dedupeStrings(values: string[]): string[] {
  return Array.from(new Set(values));
}

function parseSearchToken(token: string): {
  textToken?: string;
  negatedTextToken?: string;
  predicate?: SearchFieldPredicate;
} {
  if (!token) return {};

  const negated = token.startsWith("-") && token.length > 1;
  const effectiveToken = negated ? token.slice(1) : token;

  const predicateMatch = effectiveToken.match(FIELD_PREDICATE_REGEX);
  if (predicateMatch) {
    const [, rawField, rawOperator, rawValue] = predicateMatch;
    const field = normalizeSearchFieldName(rawField);
    const value = normalizeSearchText(rawValue);

    if (field && value) {
      return {
        predicate: {
          raw: token,
          field,
          operator: rawOperator as SearchFieldOperator,
          value,
          negated,
        },
      };
    }
  }

  const normalizedToken = normalizeSearchText(effectiveToken);
  if (normalizedToken.length === 0) return {};

  return negated ? { negatedTextToken: normalizedToken } : { textToken: normalizedToken };
}

export function parseSearchQuery(query: string): ParsedSearchQuery {
  const rawTokens = splitQueryIntoRawTokens(query)
    .map((token) => token.trim())
    .filter(Boolean);
  const textTokens: string[] = [];
  const negatedTextTokens: string[] = [];
  const predicates: SearchFieldPredicate[] = [];

  for (const rawToken of rawTokens) {
    const parsed = parseSearchToken(rawToken);
    if (parsed.textToken) textTokens.push(parsed.textToken);
    if (parsed.negatedTextToken) negatedTextTokens.push(parsed.negatedTextToken);
    if (parsed.predicate) predicates.push(parsed.predicate);
  }

  return {
    rawTokens,
    textTokens: dedupeStrings(textTokens),
    negatedTextTokens: dedupeStrings(negatedTextTokens),
    predicates,
  };
}

export function isSearchQueryEmpty(parsedQuery: ParsedSearchQuery): boolean {
  return (
    parsedQuery.textTokens.length === 0 &&
    parsedQuery.negatedTextTokens.length === 0 &&
    parsedQuery.predicates.length === 0
  );
}

export function buildSearchQueryChips(parsedQuery: ParsedSearchQuery, maxChips = 7): string[] {
  const chips: string[] = [];
  for (const predicate of parsedQuery.predicates) {
    const label = `${predicate.field}${predicate.operator}${predicate.value}`;
    chips.push(predicate.negated ? `NOT ${label}` : label);
  }
  for (const token of parsedQuery.textTokens) {
    chips.push(`"${token}"`);
  }
  for (const token of parsedQuery.negatedTextTokens) {
    chips.push(`NOT "${token}"`);
  }

  if (chips.length <= maxChips) return chips;
  const visible = chips.slice(0, maxChips);
  visible.push(`+${chips.length - maxChips} more`);
  return visible;
}

function appendFieldValue(
  fieldValues: SearchFieldValueMap,
  fieldName: string,
  value: SearchScalar,
): void {
  const normalizedFieldName = normalizeSearchFieldName(fieldName);
  if (normalizedFieldName.length === 0) return;
  const existing = fieldValues.get(normalizedFieldName);
  if (existing) {
    existing.push(value);
    return;
  }
  fieldValues.set(normalizedFieldName, [value]);
}

function collectFieldValues(
  fieldValues: SearchFieldValueMap,
  fieldName: string,
  value: unknown,
  depth: number,
): void {
  if (isScalarSearchValue(value)) {
    appendFieldValue(fieldValues, fieldName, value);
    return;
  }

  if (value instanceof Date) {
    appendFieldValue(fieldValues, fieldName, value.toISOString());
    return;
  }

  if (value === null || value === undefined || depth >= 1) return;

  if (Array.isArray(value)) {
    for (const nestedValue of value.slice(0, MAX_NESTED_ITEMS)) {
      collectFieldValues(fieldValues, fieldName, nestedValue, depth + 1);
    }
    return;
  }

  if (typeof value === "object") {
    let index = 0;
    for (const [nestedKey, nestedValue] of Object.entries(value)) {
      if (index >= MAX_NESTED_ITEMS) break;
      const normalizedNestedKey = normalizeSearchFieldName(nestedKey);
      if (normalizedNestedKey.length > 0) {
        collectFieldValues(
          fieldValues,
          `${fieldName}.${normalizedNestedKey}`,
          nestedValue,
          depth + 1,
        );
      }
      index += 1;
    }
  }
}

function buildEntityFieldValueMap(
  entity: SearchableEntity,
  ignoredDataKeys: ReadonlySet<string> = DEFAULT_IGNORED_ENTITY_DATA_KEYS,
): SearchFieldValueMap {
  const fieldValues: SearchFieldValueMap = new Map();

  appendFieldValue(fieldValues, "id", entity.id);
  appendFieldValue(fieldValues, "table", entity.table_info.name);
  appendFieldValue(fieldValues, "schema", entity.table_info.base_schema);
  appendFieldValue(fieldValues, "base_schema", entity.table_info.base_schema);
  if (entity.table_info.group) {
    appendFieldValue(fieldValues, "group", entity.table_info.group);
  }

  for (const [dataKey, dataValue] of Object.entries(entity.data)) {
    if (ignoredDataKeys.has(dataKey)) continue;
    collectFieldValues(fieldValues, dataKey, dataValue, 0);
  }

  return fieldValues;
}

function mergeFieldValueMaps(target: SearchFieldValueMap, source: SearchFieldValueMap): void {
  for (const [fieldName, values] of source) {
    const existing = target.get(fieldName);
    if (existing) {
      existing.push(...values);
    } else {
      target.set(fieldName, [...values]);
    }
  }
}

function toSearchComparableString(value: SearchScalar): string {
  return normalizeSearchText(value);
}

function asComparableNumber(value: SearchScalar | string): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function matchesFieldPredicateValue(
  candidate: SearchScalar,
  predicate: SearchFieldPredicate,
): boolean {
  if (predicate.operator === ":" || predicate.operator === "=" || predicate.operator === "!=") {
    const candidateText = toSearchComparableString(candidate);
    if (predicate.operator === ":") {
      return candidateText.includes(predicate.value);
    }
    const isEqual = candidateText === predicate.value;
    return predicate.operator === "=" ? isEqual : !isEqual;
  }

  const candidateNumber = asComparableNumber(candidate);
  const predicateNumber = asComparableNumber(predicate.value);
  if (candidateNumber === null || predicateNumber === null) return false;

  switch (predicate.operator) {
    case ">":
      return candidateNumber > predicateNumber;
    case ">=":
      return candidateNumber >= predicateNumber;
    case "<":
      return candidateNumber < predicateNumber;
    case "<=":
      return candidateNumber <= predicateNumber;
    default:
      return false;
  }
}

function matchesFieldPredicate(
  fieldValues: SearchFieldValueMap,
  predicate: SearchFieldPredicate,
): boolean {
  const values = fieldValues.get(predicate.field);
  if (!values || values.length === 0) return false;

  if (predicate.operator === "!=") {
    return values.every((candidate) => matchesFieldPredicateValue(candidate, predicate));
  }

  return values.some((candidate) => matchesFieldPredicateValue(candidate, predicate));
}

export function matchesParsedSearchQuery(
  corpus: string,
  fieldValues: SearchFieldValueMap,
  parsedQuery: ParsedSearchQuery,
): boolean {
  if (!matchesSearchTokens(corpus, parsedQuery.textTokens)) {
    return false;
  }

  if (parsedQuery.negatedTextTokens.some((token) => corpus.includes(token))) {
    return false;
  }

  for (const predicate of parsedQuery.predicates) {
    const isPredicateMatch = matchesFieldPredicate(fieldValues, predicate);
    if (predicate.negated ? isPredicateMatch : !isPredicateMatch) {
      return false;
    }
  }

  return true;
}

function getParentId(entity: SearchableEntity): string {
  return typeof entity.data.parent_id === "string" ? entity.data.parent_id : "";
}

function resolveTopEntityId(
  entityId: string,
  entitiesById: ReadonlyMap<string, SearchableEntity>,
  memo: Map<string, string>,
  ancestors: Set<string>,
): string {
  const memoized = memo.get(entityId);
  if (memoized) return memoized;

  const entity = entitiesById.get(entityId);
  if (!entity) {
    memo.set(entityId, entityId);
    return entityId;
  }

  const parentId = getParentId(entity);
  if (parentId === "" || !entitiesById.has(parentId) || ancestors.has(parentId)) {
    memo.set(entityId, entity.id);
    return entity.id;
  }

  ancestors.add(entity.id);
  const topEntityId = resolveTopEntityId(parentId, entitiesById, memo, ancestors);
  ancestors.delete(entity.id);
  memo.set(entity.id, topEntityId);
  return topEntityId;
}

export function buildTopEntityIdByEntityId(
  entities: readonly SearchableEntity[],
): Map<string, string> {
  const entitiesById = new Map(entities.map((entity) => [entity.id, entity]));
  const topEntityIdByEntityId = new Map<string, string>();

  for (const entity of entities) {
    const topEntityId = resolveTopEntityId(
      entity.id,
      entitiesById,
      topEntityIdByEntityId,
      new Set<string>(),
    );
    topEntityIdByEntityId.set(entity.id, topEntityId);
  }

  return topEntityIdByEntityId;
}

export function buildTopEntitySearchCorpus(
  entities: readonly SearchableEntity[],
  topEntityIdByEntityId: ReadonlyMap<string, string>,
  ignoredDataKeys: ReadonlySet<string> = DEFAULT_IGNORED_ENTITY_DATA_KEYS,
): Map<string, string> {
  const termsByTopEntityId = new Map<string, string[]>();

  for (const entity of entities) {
    const topEntityId = topEntityIdByEntityId.get(entity.id);
    if (!topEntityId) continue;

    const entitySearchText = buildEntitySearchText(entity, ignoredDataKeys);
    if (entitySearchText.length === 0) continue;

    const terms = termsByTopEntityId.get(topEntityId);
    if (terms) {
      terms.push(entitySearchText);
    } else {
      termsByTopEntityId.set(topEntityId, [entitySearchText]);
    }
  }

  const corpusByTopEntityId = new Map<string, string>();
  for (const [topEntityId, terms] of termsByTopEntityId) {
    corpusByTopEntityId.set(topEntityId, terms.join(" "));
  }
  return corpusByTopEntityId;
}

export function buildTopEntitySearchIndex(
  entities: readonly SearchableEntity[],
  topEntityIdByEntityId: ReadonlyMap<string, string>,
  ignoredDataKeys: ReadonlySet<string> = DEFAULT_IGNORED_ENTITY_DATA_KEYS,
): TopEntitySearchIndex {
  const corpusTermsByTopEntityId = new Map<string, string[]>();
  const fieldValuesByTopEntityId = new Map<string, SearchFieldValueMap>();

  for (const entity of entities) {
    const topEntityId = topEntityIdByEntityId.get(entity.id);
    if (!topEntityId) continue;

    const entitySearchText = buildEntitySearchText(entity, ignoredDataKeys);
    if (entitySearchText.length > 0) {
      const existingTerms = corpusTermsByTopEntityId.get(topEntityId);
      if (existingTerms) {
        existingTerms.push(entitySearchText);
      } else {
        corpusTermsByTopEntityId.set(topEntityId, [entitySearchText]);
      }
    }

    const entityFieldValues = buildEntityFieldValueMap(entity, ignoredDataKeys);
    const topFieldValues = fieldValuesByTopEntityId.get(topEntityId);
    if (topFieldValues) {
      mergeFieldValueMaps(topFieldValues, entityFieldValues);
    } else {
      fieldValuesByTopEntityId.set(topEntityId, entityFieldValues);
    }
  }

  const corpusByTopEntityId = new Map<string, string>();
  for (const [topEntityId, terms] of corpusTermsByTopEntityId) {
    corpusByTopEntityId.set(topEntityId, terms.join(" "));
  }

  return {
    corpusByTopEntityId,
    fieldValuesByTopEntityId,
  };
}
