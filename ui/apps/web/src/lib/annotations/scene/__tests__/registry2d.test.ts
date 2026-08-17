/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import { RENDERER_FACTORIES_2D, TOOLS_2D } from "../registry2d.js";
import { TOOLS_3D } from "../registry3d.js";
import { DEFAULT_TOOL_2D } from "../tool.js";
import type { AnnotationKind } from "$lib/annotations/annotationCollection.svelte.js";
import { payloadBuilderFor } from "$lib/annotations/payloadBuilders.js";
import { SEED_LOADERS } from "$lib/annotations/seedLoaders.js";

// Importing the registry pulls in every tool and renderer, and so the real
// Konva, which needs a native `canvas` build in node. These checks only read
// registry metadata — no node is ever constructed — so an empty stub is enough.
vi.mock("konva", () => ({ default: {} }));

/**
 * Registration is the one step of adding a kind that no other test covers: each
 * registry is a plain list, so forgetting a line leaves the code compiling,
 * every unit test green, and the tool simply absent from the toolbar. These
 * checks tie the four registries together so a half-registered kind fails here.
 */

/** Kinds a tool can create, i.e. every tool except the kind-agnostic select. */
function creatableKinds(): AnnotationKind[] {
  const kinds = TOOLS_2D.flatMap((tool) => (tool.kind ? [tool.kind] : []));
  return [...new Set(kinds)];
}

function seedLoaderKinds(): Set<AnnotationKind> {
  return new Set(SEED_LOADERS.map((loader) => loader.kind));
}

function rendererKinds(): Set<AnnotationKind> {
  return new Set(RENDERER_FACTORIES_2D.map((factory) => factory.kind));
}

describe("2D registry consistency", () => {
  it("has the kind-agnostic select tool first", () => {
    expect(TOOLS_2D[0].id).toBe(DEFAULT_TOOL_2D);
    expect(TOOLS_2D[0].kind).toBeUndefined();
  });

  it("gives every tool a unique id", () => {
    const ids = TOOLS_2D.map((tool) => tool.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("can build payloads for every kind a tool creates", () => {
    // A tool without a payload builder throws only once the user has already
    // drawn something, which is far too late to notice.
    for (const kind of creatableKinds()) {
      expect(() => payloadBuilderFor(kind)).not.toThrow();
    }
  });

  it("can render every kind a tool creates", () => {
    // Otherwise the annotation is saved and then invisible on reload.
    const renderers = rendererKinds();
    for (const kind of creatableKinds()) {
      expect(renderers.has(kind)).toBe(true);
    }
  });

  it("can reload every kind a tool creates", () => {
    // Without a seed loader the annotation survives the save but not the
    // record switch that follows it.
    const loaders = seedLoaderKinds();
    for (const kind of creatableKinds()) {
      expect(loaders.has(kind)).toBe(true);
    }
  });

  it("has a payload builder behind every seed loader", () => {
    for (const loader of SEED_LOADERS) {
      expect(() => payloadBuilderFor(loader.kind)).not.toThrow();
    }
  });

  it("gives every stored kind a tool that can create it", () => {
    // The direction that actually catches a forgotten registry line: checks
    // starting from the tool list go vacuously green when the tool is the thing
    // missing. A kind wired for storage but reachable by no tool is dead weight
    // — it can be read back but never produced.
    // 2D and 3D are searched together: a kind's tool may live in either scene
    // (bbox3d renders in both but is only drawn in the point cloud).
    const toolKinds = new Set(
      [...TOOLS_2D, ...TOOLS_3D].flatMap((tool) => (tool.kind ? [tool.kind] : [])),
    );
    for (const loader of SEED_LOADERS) {
      expect(toolKinds.has(loader.kind), `no tool creates "${loader.kind}"`).toBe(true);
    }
  });

  it("routes each kind to a distinct backend resource", () => {
    const resources = SEED_LOADERS.map((loader) => payloadBuilderFor(loader.kind).resource);
    expect(new Set(resources).size).toBe(resources.length);
  });
});
