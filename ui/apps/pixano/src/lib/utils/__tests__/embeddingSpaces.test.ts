/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  canBecomeDefault,
  embeddingsView,
  healthLabel,
  isBroken,
  isHeld,
  isSearchable,
  isSearchableStatus,
  modelToCompute,
  orderedSpaces,
  selectedSpace,
  spaceChoices,
  spaceLabel,
  type ServedModel,
} from "../embeddingSpaces";
import type { EmbeddingSpaceStatusResponse, SearchCapabilitiesResponse } from "$lib/api/restTypes";

function space(changes: Partial<EmbeddingSpaceStatusResponse>): EmbeddingSpaceStatusResponse {
  return {
    id: "clip-3f2a9c1d",
    model_id: "clip",
    checkpoint: "MobileCLIP2-S2",
    dim: 512,
    default: false,
    status: "ready",
    embedded_rows: 60,
    ...changes,
  };
}

const CLIP = space({ default: true });
const SIGLIP = space({ id: "siglip-0b7e44a2", model_id: "siglip", checkpoint: "", dim: 768 });
const CLIP_LARGE = space({ id: "clip-9d01e5c2", checkpoint: "ViT-L-14", dim: 768 });

function search(changes: Partial<SearchCapabilitiesResponse>): SearchCapabilitiesResponse {
  return { modes: ["text", "semantic"], models: ["clip"], total_media: 80, ...changes };
}

function served(changes: Partial<ServedModel>): ServedModel {
  return { name: "clip", model_path: "MobileCLIP2-S2", provider_name: "local", ...changes };
}

describe("isSearchable and isBroken", () => {
  it("read every medium embedded, or some, and repair the rest", () => {
    expect(["ready", "partial"].map(isSearchableStatus)).toEqual([true, true]);
    for (const status of ["missing_table", "empty", "dim_mismatch", "corrupt"]) {
      expect([isSearchable(space({ status })), isBroken(status)]).toEqual([false, true]);
    }
    expect([isSearchableStatus("absent"), isBroken("absent")]).toEqual([false, false]);
  });
});

describe("orderedSpaces", () => {
  it("puts the default model first, the others as the server lists them", () => {
    const listed = [SIGLIP, CLIP_LARGE, CLIP];

    expect(orderedSpaces(search({ spaces: listed })).map((s) => s.id)).toEqual([
      CLIP.id,
      SIGLIP.id,
      CLIP_LARGE.id,
    ]);
  });

  it("is empty for a dataset without embeddings, or a schema that lists none", () => {
    expect(orderedSpaces(search({ spaces: [] }))).toEqual([]);
    expect(orderedSpaces(undefined)).toEqual([]);
  });
});

describe("isHeld", () => {
  it("knows a model by its id or its name, and the default by no name", () => {
    expect(
      [CLIP_LARGE.id, "siglip", ""].map((named) => isHeld([CLIP, SIGLIP, CLIP_LARGE], named)),
    ).toEqual([true, true, true]);
    expect(isHeld([CLIP], "dinov2")).toBe(false);
  });
});

describe("selectedSpace", () => {
  const spaces = [CLIP, SIGLIP, CLIP_LARGE];

  it("is the default model when the URL names none", () => {
    expect(selectedSpace(spaces, "")?.id).toBe(CLIP.id);
  });

  it("is the model the URL names by its id", () => {
    expect(selectedSpace(spaces, CLIP_LARGE.id)?.id).toBe(CLIP_LARGE.id);
  });

  it("reads a name as the server does: the default model of that name first", () => {
    expect(selectedSpace([SIGLIP, CLIP_LARGE, CLIP], "clip")?.id).toBe(CLIP.id);
    expect(selectedSpace(spaces, "siglip")?.id).toBe(SIGLIP.id);
  });

  it("reads a name none of whose models is the default as its first model", () => {
    const siglipDefault = { ...SIGLIP, default: true };
    const clipAgain = { ...CLIP, default: false };

    expect(selectedSpace([siglipDefault, CLIP_LARGE, clipAgain], "clip")?.id).toBe(CLIP_LARGE.id);
  });

  it("never takes an empty URL for a model without a name", () => {
    const nameless = space({ id: "nameless", model_id: "" });

    expect(selectedSpace([CLIP, nameless], "")?.id).toBe(CLIP.id);
  });

  it("is none while the dataset holds no embeddings", () => {
    expect(selectedSpace([], "clip")).toBeUndefined();
  });
});

describe("spaceLabel and healthLabel", () => {
  it("tells two checkpoints of one name apart, and a model without one by its name", () => {
    expect(spaceLabel(CLIP)).toBe("clip · MobileCLIP2-S2");
    expect(spaceLabel(SIGLIP)).toBe("siglip");
  });

  it("adds the dimension where two models would read the same", () => {
    const untold = space({ id: "clip-0", checkpoint: "" });
    const untoldLarge = space({ id: "clip-1", checkpoint: "", dim: 768 });

    expect([untold, untoldLarge].map((s) => spaceLabel(s, [untold, untoldLarge, CLIP]))).toEqual([
      "clip · 512d",
      "clip · 768d",
    ]);
  });

  it("words a health for a person", () => {
    expect(["ready", "partial", "dim_mismatch", "absent"].map(healthLabel)).toEqual([
      "Ready",
      "Partial",
      "Broken",
      "Not computed",
    ]);
  });
});

describe("canBecomeDefault", () => {
  it("is a model a search can read, other than the default, while the description can change", () => {
    expect(canBecomeDefault(SIGLIP, true)).toBe(true);
    expect(canBecomeDefault(CLIP, true)).toBe(false);
    expect(canBecomeDefault({ ...SIGLIP, status: "corrupt" }, true)).toBe(false);
    expect(canBecomeDefault(SIGLIP, false)).toBe(false);
  });
});

describe("spaceChoices", () => {
  it("offers every model a search can read", () => {
    const broken = space({ id: "broken", model_id: "dinov2", status: "corrupt" });

    expect(spaceChoices([CLIP, SIGLIP, broken], CLIP).map((s) => s.id)).toEqual([
      CLIP.id,
      SIGLIP.id,
    ]);
  });

  it("offers nothing when there is no other model to choose", () => {
    const broken = space({ id: "broken", model_id: "dinov2", status: "corrupt" });

    expect(spaceChoices([CLIP], CLIP)).toEqual([]);
    expect(spaceChoices([CLIP, broken], CLIP)).toEqual([]);
  });

  it("keeps a broken default among the choices, so that one can go back to it and repair it", () => {
    const broken = { ...CLIP, status: "missing_table" };

    expect(spaceChoices([broken, SIGLIP], broken).map((s) => s.id)).toEqual([broken.id, SIGLIP.id]);
    expect(spaceChoices([broken, SIGLIP], SIGLIP).map((s) => s.id)).toEqual([broken.id, SIGLIP.id]);
  });

  it("keeps the model searched among the choices, broken or not", () => {
    const brokenSiglip = { ...SIGLIP, status: "dim_mismatch" };

    expect(spaceChoices([CLIP, brokenSiglip], brokenSiglip).map((s) => s.id)).toEqual([
      CLIP.id,
      SIGLIP.id,
    ]);
  });
});

describe("embeddingsView", () => {
  it("shows the model searched, counted out of every medium of the dataset", () => {
    const partial = { ...SIGLIP, status: "partial", detail: "20 media missing" };

    const view = embeddingsView(
      search({ status: "ready", embedded_rows: 80 }),
      [CLIP, partial],
      partial,
    );

    expect(view).toMatchObject({
      status: "partial",
      detail: "20 media missing",
      embeddedMedia: 60,
      totalMedia: 80,
      searchReady: true,
      degraded: false,
      searchedId: SIGLIP.id,
      searchedLabel: "siglip",
      descriptionReadable: true,
    });
    expect(
      view.rows.map((row) => [row.id, row.isDefault, row.isSearched, row.canBecomeDefault]),
    ).toEqual([
      [CLIP.id, true, false, false],
      [SIGLIP.id, false, true, true],
    ]);
    expect(view.choices.map((choice) => choice.id)).toEqual([CLIP.id, SIGLIP.id]);
  });

  it("shows a broken model's detail on its row, and the search bar degraded", () => {
    const broken = { ...CLIP, status: "missing_table", detail: "its table is gone" };

    const view = embeddingsView(search({}), [broken, SIGLIP], broken);

    expect([view.searchReady, view.degraded]).toEqual([false, true]);
    expect(view.rows[0]).toMatchObject({
      health: "Broken",
      broken: true,
      detail: "its table is gone",
    });
  });

  it("lets no model become the default while the description cannot change", () => {
    const view = embeddingsView(search({ fully_read: false }), [CLIP, SIGLIP], CLIP);

    expect([view.descriptionReadable, view.rows.some((row) => row.canBecomeDefault)]).toEqual([
      false,
      false,
    ]);
  });

  it("shows the dataset's own state when it holds no model", () => {
    const view = embeddingsView(search({ status: "absent", detail: null }), [], undefined);

    expect(view).toMatchObject({
      status: "absent",
      detail: "",
      embeddedMedia: 0,
      searchReady: false,
      searchedId: "",
    });
    expect([view.rows, view.choices]).toEqual([[], []]);
    expect(embeddingsView(undefined, [], undefined).status).toBe("absent");
  });
});

describe("modelToCompute", () => {
  const spaces = [CLIP, SIGLIP];

  it("computes the model searched again, on the server that serves its weights", () => {
    const servers = [
      served({ name: "siglip", model_path: null }),
      served({ provider_name: "gpu" }),
    ];

    expect(modelToCompute(CLIP, spaces, servers)).toEqual({ model: "clip", provider: "gpu" });
    expect(modelToCompute(SIGLIP, spaces, servers)).toEqual({ model: "siglip", provider: "local" });
  });

  it("computes the first model the inference serves on a dataset without embeddings", () => {
    const servers = [served({ name: "siglip", provider_name: "gpu" }), served({})];

    expect(modelToCompute(undefined, [], servers)).toEqual({ model: "siglip", provider: "gpu" });
  });

  it("refuses a model the inference does not serve", () => {
    expect(modelToCompute(CLIP, spaces, [served({ name: "siglip" })])).toEqual({
      refusal: "The inference does not serve model 'clip'.",
    });
  });

  it("refuses other weights than the model's embeddings were computed with", () => {
    expect(modelToCompute(CLIP_LARGE, [CLIP, CLIP_LARGE], [served({})])).toEqual({
      refusal:
        "The inference serves model 'clip' with 'MobileCLIP2-S2', not with the weights these " +
        "embeddings were computed with.",
    });
  });

  it("refuses for a model without its weights told the weights another model of the name records", () => {
    const untold = space({ id: "clip-0", checkpoint: "", default: true });

    expect(
      modelToCompute(untold, [untold, CLIP_LARGE], [served({ model_path: "ViT-L-14" })]),
    ).toEqual({
      refusal:
        "The inference serves model 'clip' with 'ViT-L-14', not with the weights these embeddings " +
        "were computed with.",
    });
  });

  it("refuses weights several models of the name could be, as the server does", () => {
    const untold = space({ id: "clip-0", checkpoint: "", default: true });
    const untoldLarge = space({ id: "clip-1", checkpoint: "", dim: 768 });
    const told = space({ id: "clip-2", checkpoint: "ViT-B-32" });

    expect(
      modelToCompute(told, [untold, untoldLarge, told], [served({ model_path: "ViT-H-14" })]),
    ).toEqual({
      refusal:
        "The inference does not say which of this dataset's models 'clip' its weights are: their " +
        "embeddings cannot be told apart.",
    });
  });

  it("computes a model whose weights the inference or the model does not tell", () => {
    const untold = space({ checkpoint: "", default: true });

    expect(modelToCompute(untold, [untold], [served({})])).toEqual({
      model: "clip",
      provider: "local",
    });
    expect(modelToCompute(CLIP, spaces, [served({ model_path: null })])).toEqual({
      model: "clip",
      provider: "local",
    });
  });

  it("starts again from nothing with the model searched, else the first served, whatever the weights", () => {
    const servers = [served({ name: "siglip" }), served({ model_path: "ViT-L-14" })];

    expect(modelToCompute(CLIP, spaces, servers, true)).toEqual({
      model: "clip",
      provider: "local",
    });
    expect(modelToCompute(space({ model_id: "dinov2" }), spaces, servers, true)).toEqual({
      model: "siglip",
      provider: "local",
    });
  });
});
