/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { EmbeddingSpaceStatusResponse, SearchCapabilitiesResponse } from "$lib/api/restTypes";
import type { InferenceModel } from "$lib/types/inference";

/** The healths of a model's embeddings a search reads: every medium embedded, or some. */
const SEARCHABLE_STATUSES = new Set(["ready", "partial"]);

/** The healths of a model's embeddings that must be computed again before a search reads them. */
const BROKEN_STATUSES = new Set(["missing_table", "empty", "dim_mismatch", "corrupt"]);

/** The fewest models a selector offers: with one, there is nothing to choose. */
const MODELS_TO_CHOOSE_FROM = 2;

/** A model the inference serves, as the explorer's own computation names it. */
export type ServedModel = Pick<InferenceModel, "name" | "model_path" | "provider_name">;

/** The model the explorer's own computation computes, on which server, or why it computes none. */
export type ModelToCompute = { model: string; provider: string } | { refusal: string };

/** A model of the dataset, as the embeddings popover lists it. */
export interface SpaceRow {
  id: string;
  label: string;
  /** Its health, in a word. */
  health: string;
  broken: boolean;
  /** What is wrong with it, empty when nothing is. */
  detail: string;
  /** The media it holds a vector of. */
  embeddedMedia: number;
  isDefault: boolean;
  /** Whether it is the model a search reads. */
  isSearched: boolean;
  /** Whether it can be made the default: a search can read it, and the description can change. */
  canBecomeDefault: boolean;
}

/** A model the selector offers. */
export interface SpaceChoice {
  id: string;
  label: string;
  /** Its health, in a word: shown for a model a search cannot read. */
  health: string;
  searchable: boolean;
  isDefault: boolean;
}

/** What the search bar shows of the dataset's embeddings: those of the model a search reads. */
export interface EmbeddingsView {
  /** Their health: "absent" when the dataset holds none. */
  status: string;
  /** What is wrong with them, empty when nothing is. */
  detail: string;
  /** The media they hold a vector of. */
  embeddedMedia: number;
  /** The media the dataset holds, which every model's embeddings are counted out of. */
  totalMedia: number;
  /** Whether a search can read them. */
  searchReady: boolean;
  /** Whether they must be computed again before a search reads them. */
  degraded: boolean;
  /** Every model of the dataset, the default one first. */
  rows: SpaceRow[];
  /** The models to choose from; empty when there is no choice. */
  choices: SpaceChoice[];
  /** The model a search reads, empty while the dataset holds none. */
  searchedId: string;
  searchedLabel: string;
  /**
   * Whether the dataset's description of its embeddings was read entirely: if not, nothing changes
   * it but computing them again from nothing, which deletes every model's embeddings first.
   */
  descriptionReadable: boolean;
}

/** Whether a search can read embeddings of this health. */
export function isSearchableStatus(status: string): boolean {
  return SEARCHABLE_STATUSES.has(status);
}

/** Whether a search can read a model's embeddings. */
export function isSearchable(space: EmbeddingSpaceStatusResponse): boolean {
  return isSearchableStatus(space.status);
}

/** Whether embeddings of this health must be computed again before a search reads them. */
export function isBroken(status: string): boolean {
  return BROKEN_STATUSES.has(status);
}

/** A dataset's embeddings models, the default one first, then the others in the order the server lists them. */
export function orderedSpaces(
  search: SearchCapabilitiesResponse | undefined,
): EmbeddingSpaceStatusResponse[] {
  const spaces = search?.spaces ?? [];
  return [...spaces.filter((space) => space.default), ...spaces.filter((space) => !space.default)];
}

/** Whether the dataset holds the model a URL names — by its id or its name —, the default when it names none. */
export function isHeld(spaces: EmbeddingSpaceStatusResponse[], named: string): boolean {
  return named === "" || spaces.some((space) => space.id === named || space.model_id === named);
}

/**
 * The model a search reads: the one the URL names — by its id, or by its name as the server reads
 * a name, the default model of that name first —, else the default one.
 */
export function selectedSpace(
  spaces: EmbeddingSpaceStatusResponse[],
  named: string,
): EmbeddingSpaceStatusResponse | undefined {
  const fallback = spaces.find((space) => space.default);
  if (named === "") return fallback;
  const ofName = spaces.filter((space) => space.model_id === named);
  return (
    spaces.find((space) => space.id === named) ??
    ofName.find((space) => space.default) ??
    ofName[0] ??
    fallback
  );
}

/**
 * A model as a person tells it from another: its name, the weights it was computed with, and its
 * vectors' dimension when another model of the dataset would read the same.
 */
export function spaceLabel(
  space: EmbeddingSpaceStatusResponse,
  spaces: EmbeddingSpaceStatusResponse[] = [],
): string {
  const named = (other: EmbeddingSpaceStatusResponse) =>
    other.checkpoint ? `${other.model_id} · ${other.checkpoint}` : other.model_id;
  const label = named(space);
  const alike = spaces.some((other) => other.id !== space.id && named(other) === label);
  return alike ? `${label} · ${space.dim}d` : label;
}

/** A model's embeddings' health, in a word. */
export function healthLabel(status: string): string {
  if (status === "ready") return "Ready";
  if (status === "partial") return "Partial";
  if (isBroken(status)) return "Broken";
  return "Not computed";
}

/**
 * Whether a model can be made the default: a search can read it — a broken default would leave
 * every search naming no model without results —, and the description can change.
 */
export function canBecomeDefault(
  space: EmbeddingSpaceStatusResponse,
  descriptionReadable: boolean,
): boolean {
  return !space.default && isSearchable(space) && descriptionReadable;
}

/**
 * The models the selector offers: those a search can read, the default and the searched one among
 * them whatever their health, so that one can always go back to them. None with fewer than two.
 */
export function spaceChoices(
  spaces: EmbeddingSpaceStatusResponse[],
  searched: EmbeddingSpaceStatusResponse | undefined,
): EmbeddingSpaceStatusResponse[] {
  const offered = spaces.filter(
    (space) => isSearchable(space) || space.default || space.id === searched?.id,
  );
  return offered.length >= MODELS_TO_CHOOSE_FROM ? offered : [];
}

/** What the search bar shows of the dataset's embeddings, the model a search reads first. */
export function embeddingsView(
  search: SearchCapabilitiesResponse | undefined,
  spaces: EmbeddingSpaceStatusResponse[],
  searched: EmbeddingSpaceStatusResponse | undefined,
): EmbeddingsView {
  const descriptionReadable = search?.fully_read ?? true;
  const status = searched?.status ?? search?.status ?? "absent";
  return {
    status,
    detail: (searched ? searched.detail : search?.detail) ?? "",
    embeddedMedia: searched?.embedded_rows ?? search?.embedded_rows ?? 0,
    totalMedia: search?.total_media ?? 0,
    searchReady: isSearchableStatus(status),
    degraded: isBroken(status),
    rows: spaces.map((space) => ({
      id: space.id,
      label: spaceLabel(space, spaces),
      health: healthLabel(space.status),
      broken: isBroken(space.status),
      detail: space.detail ?? "",
      embeddedMedia: space.embedded_rows,
      isDefault: space.default,
      isSearched: space.id === searched?.id,
      canBecomeDefault: canBecomeDefault(space, descriptionReadable),
    })),
    choices: spaceChoices(spaces, searched).map((space) => ({
      id: space.id,
      label: spaceLabel(space, spaces),
      health: healthLabel(space.status),
      searchable: isSearchable(space),
      isDefault: space.default,
    })),
    searchedId: searched?.id ?? "",
    searchedLabel: searched ? spaceLabel(searched, spaces) : "",
    descriptionReadable,
  };
}

/** The models a computation of that name and weights could write, as the server matches them. */
function matchingSpaces(
  spaces: EmbeddingSpaceStatusResponse[],
  name: string,
  checkpoint: string,
): EmbeddingSpaceStatusResponse[] {
  return spaces.filter(
    (space) =>
      space.model_id === name &&
      (!space.checkpoint || !checkpoint || space.checkpoint === checkpoint),
  );
}

/**
 * The model whose embeddings a computation writes, as the server finds it: of that name, and of
 * those weights when both it and the model tell them — that very checkpoint first —; none when
 * none matches, which makes another model, nor when several do, which the server refuses to guess.
 */
function writtenSpace(
  spaces: EmbeddingSpaceStatusResponse[],
  name: string,
  checkpoint: string,
): EmbeddingSpaceStatusResponse | undefined {
  const matching = matchingSpaces(spaces, name, checkpoint);
  const exact = matching.find((space) => space.checkpoint === checkpoint);
  return exact ?? (matching.length === 1 ? matching[0] : undefined);
}

/**
 * The model the explorer's own computation computes, and the server to compute it on.
 *
 * - No model computed yet: the first the inference serves.
 * - Starting again from nothing (`startAgain`), every model's embeddings deleted first: the
 *   searched model if the inference serves it, else the first it serves — the weights no matter.
 * - Otherwise the searched model, on a server that serves it with weights whose vectors go to its
 *   embeddings; refused when none does, since they would go to another model's.
 */
export function modelToCompute(
  searched: EmbeddingSpaceStatusResponse | undefined,
  spaces: EmbeddingSpaceStatusResponse[],
  served: ServedModel[],
  startAgain = false,
): ModelToCompute {
  const named = served.filter((model) => model.name === searched?.model_id);
  if (searched === undefined || startAgain) {
    const chosen = named[0] ?? served[0];
    return chosen
      ? { model: chosen.name, provider: chosen.provider_name }
      : { refusal: "The inference serves no embedding model." };
  }
  if (named.length === 0) {
    return { refusal: `The inference does not serve model '${searched.model_id}'.` };
  }
  const fitting = named.find(
    (model) => writtenSpace(spaces, model.name, model.model_path ?? "")?.id === searched.id,
  );
  if (fitting) return { model: fitting.name, provider: fitting.provider_name };
  const weights = named[0].model_path ?? "";
  const ambiguous =
    matchingSpaces(spaces, searched.model_id, weights).length > 1 &&
    !spaces.some((space) => space.model_id === searched.model_id && space.checkpoint === weights);
  if (ambiguous) {
    return {
      refusal:
        `The inference does not say which of this dataset's models '${searched.model_id}' its weights ` +
        "are: their embeddings cannot be told apart.",
    };
  }
  return {
    refusal:
      `The inference serves model '${searched.model_id}' with '${weights}', not with the weights ` +
      "these embeddings were computed with.",
  };
}
