/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { flushSync } from "svelte";
import * as THREE from "three";
import { afterEach, describe, expect, it } from "vitest";

import { BoxEditor } from "../boxEditor.svelte.js";

// The 3D box editor's keyboard: Escape closes the box being edited, and the
// edit with it — unless the key was pressed in a form field, where it belongs
// to the field (a select closes its list with it).

const GIZMOS_SHOWN = { rings: true, resizeArrows: true, translateArrows: true };

let teardown: (() => void) | null = null;

afterEach(() => {
  teardown?.();
  teardown = null;
  document.body.innerHTML = "";
});

/** A real editor, its effects running, holding a box for the person to confirm. */
function editorHoldingABox() {
  let canceled = 0;
  let editor!: BoxEditor;
  teardown = $effect.root(() => {
    editor = new BoxEditor(
      { current: new THREE.PerspectiveCamera() },
      () => null,
      () => [],
      () => true,
      () => 0,
      () => [0, 0, 0],
      () => 1,
      () => GIZMOS_SHOWN,
      () => {},
      () => (canceled += 1),
    );
  });
  flushSync();
  editor.drawPhase = "confirming";
  editor.previewVisible = true;
  flushSync();
  return { editor, canceledCount: () => canceled };
}

function pressEscape(target: HTMLElement): void {
  target.focus();
  target.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
}

describe("BoxEditor keyboard", () => {
  it("keeps the box when Escape is pressed in a select", () => {
    const { editor, canceledCount } = editorHoldingABox();
    const select = document.createElement("select");
    document.body.appendChild(select);

    pressEscape(select);

    expect(editor.drawPhase).toBe("confirming");
    expect(canceledCount()).toBe(0);
  });

  it("closes the box when Escape is pressed anywhere else", () => {
    const { editor, canceledCount } = editorHoldingABox();

    pressEscape(document.body);

    expect(editor.drawPhase).toBe("idle");
    expect(canceledCount()).toBe(1);
  });
});
