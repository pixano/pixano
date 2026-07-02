/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  AnnotationCollection,
  ViewScopedAnnotations,
  type LocalAnnotation,
  type LocalBBox,
} from "../annotationCollection.svelte.js";

function makeBBox(id: string, persisted = false): LocalBBox {
  return { id, entityId: `e-${id}`, kind: "bbox", viewId: "view-1", geometry: [0.1, 0.1, 0.2, 0.2], persisted };
}

function makeBBox3D(id: string): LocalAnnotation {
  return {
    id,
    entityId: `e-${id}`,
    kind: "bbox3d",
    viewId: "",
    geometry: { coords: [0, 0, 0, 1, 1, 1], format: "xyzwhd" },
    persisted: true,
  };
}

describe("AnnotationCollection", () => {
  it("starts from the seeded annotations", () => {
    const collection = new AnnotationCollection([makeBBox("a"), makeBBox3D("b")]);
    expect(collection.count).toBe(2);
    expect(collection.find("a")?.entityId).toBe("e-a");
  });

  it("byKind filters and types per kind", () => {
    const collection = new AnnotationCollection([makeBBox("a"), makeBBox3D("b"), makeBBox("c")]);
    expect(collection.byKind("bbox").map((a) => a.id)).toEqual(["a", "c"]);
    expect(collection.byKind("bbox3d").map((a) => a.id)).toEqual(["b"]);
    expect(collection.byKind("mask")).toEqual([]);
  });

  it("add appends and find retrieves", () => {
    const collection = new AnnotationCollection();
    collection.add(makeBBox("a"));
    expect(collection.count).toBe(1);
    expect(collection.find("a")).toBeDefined();
    expect(collection.find("missing")).toBeUndefined();
  });

  it("remove drops the annotation and clears a matching selection", () => {
    const collection = new AnnotationCollection([makeBBox("a"), makeBBox("b")]);
    collection.select("a");
    collection.remove("a");
    expect(collection.find("a")).toBeUndefined();
    expect(collection.selectedId).toBeNull();
  });

  it("remove keeps an unrelated selection", () => {
    const collection = new AnnotationCollection([makeBBox("a"), makeBBox("b")]);
    collection.select("b");
    collection.remove("a");
    expect(collection.selectedId).toBe("b");
  });

  it("selected exposes the selected annotation", () => {
    const collection = new AnnotationCollection([makeBBox("a")]);
    expect(collection.selected).toBeUndefined();
    collection.select("a");
    expect(collection.selected?.id).toBe("a");
  });

  it("setGeometry replaces the geometry in place", () => {
    const collection = new AnnotationCollection([makeBBox("a")]);
    collection.setGeometry("a", [0.5, 0.5, 0.1, 0.1]);
    expect(collection.find("a")?.geometry).toEqual([0.5, 0.5, 0.1, 0.1]);
  });

});

describe("ViewScopedAnnotations", () => {
  function makeShared() {
    const otherViewBBox: LocalBBox = { ...makeBBox("other"), viewId: "view-2" };
    const shared = new AnnotationCollection([makeBBox("a"), otherViewBBox, makeBBox3D("box3d")]);
    const view1 = new ViewScopedAnnotations(() => shared, "view-1");
    return { shared, view1 };
  }

  it("shows this view's annotations plus record-scoped kinds, hides other views", () => {
    const { view1 } = makeShared();
    expect(view1.items.map((a) => a.id)).toEqual(["a", "box3d"]);
    expect(view1.find("other")).toBeUndefined();
    expect(view1.byKind("bbox3d").map((a) => a.id)).toEqual(["box3d"]);
    expect(view1.count).toBe(2);
  });

  it("writes through to the shared collection so other widgets see them", () => {
    const { shared, view1 } = makeShared();

    view1.setGeometry("box3d", { coords: [9, 9, 9, 1, 1, 1], format: "xyzwhd" });
    expect((shared.find("box3d")?.geometry as { coords: number[] }).coords).toEqual([9, 9, 9, 1, 1, 1]);

    view1.add({ ...makeBBox("new"), viewId: "view-1" });
    expect(shared.find("new")).toBeDefined();

    view1.remove("a");
    expect(shared.find("a")).toBeUndefined();
  });

  it("reflects a selection it can show (own view or record-scoped kind)", () => {
    const { shared, view1 } = makeShared();
    view1.select("box3d");
    expect(shared.selectedId).toBe("box3d");
    expect(view1.selectedId).toBe("box3d");
    expect(view1.selected?.id).toBe("box3d");
  });

  it("reads a foreign-view selection as no selection (cross-view delete guard)", () => {
    const { shared, view1 } = makeShared();
    // Selection is shared, but "other" belongs to view-2.
    shared.select("other");
    expect(shared.selectedId).toBe("other");
    expect(view1.selectedId).toBeNull();
    expect(view1.selected).toBeUndefined();
  });

  it("follows the parent getter when the session replaces the collection", () => {
    let current = new AnnotationCollection([makeBBox("a")]);
    const view = new ViewScopedAnnotations(() => current, "view-1");
    expect(view.count).toBe(1);

    current = new AnnotationCollection();
    expect(view.count).toBe(0);
  });
});
