/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { cardLayout } from "../cardLayout";
import type { RecordPreview } from "$lib/types/dataset";

const image = (name: string, resource = "images"): RecordPreview => ({
  name,
  kind: "image",
  resource,
  url: `/x/${name}/preview?size=256`,
});

const text = (name: string, excerpt = "lorem ipsum"): RecordPreview => ({
  name,
  kind: "text",
  resource: "texts",
  url: "",
  excerpt,
});

describe("cardLayout", () => {
  it("single image → full bleed", () => {
    const layout = cardLayout([image("image")]);
    expect(layout.kind).toBe("single");
    expect(layout.media).toHaveLength(1);
    expect(layout.extraCount).toBe(0);
  });

  it("two views (multi-camera) → duo mosaic", () => {
    const layout = cardLayout([image("rgb"), image("thermal")]);
    expect(layout.kind).toBe("duo");
    expect(layout.media.map((m) => m.name)).toEqual(["rgb", "thermal"]);
  });

  it("three or more views → primary + '+N views'", () => {
    const layout = cardLayout([image("cam_a"), image("cam_b"), image("cam_c")]);
    expect(layout.kind).toBe("many");
    expect(layout.media).toHaveLength(1);
    expect(layout.extraCount).toBe(2);
  });

  it("image + text (MEL) → split card", () => {
    const layout = cardLayout([image("image"), text("text", "some doc")]);
    expect(layout.kind).toBe("imageText");
    expect(layout.media).toHaveLength(1);
    expect(layout.text?.excerpt).toBe("some doc");
  });

  it("text only → excerpt tile", () => {
    const layout = cardLayout([text("text")]);
    expect(layout.kind).toBe("textOnly");
    expect(layout.media).toHaveLength(0);
    expect(layout.text?.name).toBe("text");
  });

  it("no previews → typographic placeholder", () => {
    expect(cardLayout([]).kind).toBe("none");
  });

  it("video frame preview keeps its sframes resource for the film badge", () => {
    const layout = cardLayout([image("frames", "sframes")]);
    expect(layout.kind).toBe("single");
    expect(layout.media[0].resource).toBe("sframes");
  });
});
