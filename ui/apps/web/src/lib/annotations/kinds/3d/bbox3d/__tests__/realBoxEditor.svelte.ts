/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { flushSync } from "svelte";
import * as THREE from "three";
import type { OrbitControls as ThreeOrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import { editorBoxOf } from "../bbox3dEditorBoxes.js";
import type { BBox3DSession, PendingConfirm } from "../bbox3dSession.svelte.js";
import { BoxEditor } from "../boxEditor.svelte.js";
import type { AnnotationStore } from "$lib/annotations/annotationCollection.svelte.js";

/** The side, in px, of the canvas the editor listens on. */
const CANVAS_PIXELS = 100;
/** How far from the box the camera stands to look at it. */
const CAMERA_DISTANCE = 20;

/**
 * A real box editor, its effects running, wired to the session as
 * `BBox3DTool` wires it: the stored boxes handed over through `editorBoxOf`,
 * its gizmos shown as the session says, its reports — a box ready, a draw
 * canceled — into the session, and its reset as the session's.
 * A box is opened as a person opens it: a click on the canvas, the camera
 * looking straight at it.
 *
 * @param session The session the editor reports to.
 * @param collection Where the stored boxes are read, as the tool reads them.
 * @returns The editor; `open` clicks a stored box; `teardown` stops the editor.
 */
export function realBoxEditor(session: BBox3DSession, collection: Pick<AnnotationStore, "byKind">) {
  const canvas = document.createElement("div");
  canvas.getBoundingClientRect = () =>
    ({ left: 0, top: 0, width: CANVAS_PIXELS, height: CANVAS_PIXELS }) as DOMRect;
  document.body.appendChild(canvas);
  const camera = new THREE.PerspectiveCamera();
  const boxes = () => collection.byKind("bbox3d").map(editorBoxOf);
  let editor!: BoxEditor;
  const teardown = $effect.root(() => {
    editor = new BoxEditor(
      { current: camera },
      () => ({ domElement: canvas }) as unknown as ThreeOrbitControls,
      boxes,
      () => true,
      () => 0,
      () => [0, 0, 0],
      () => 1,
      () => session.gizmoVisibility,
      (coords, rotation, editingId) => session.reportReady(coords, rotation, editingId),
      () => session.reportCanceled(),
    );
  });
  flushSync();
  session.setResetEditor(() => editor.reset());

  return {
    editor,
    teardown,
    /**
     * Click a stored box: the editor opens it and reports it to the session.
     *
     * @returns What the editor staged, as the session holds it.
     */
    open(id: string): PendingConfirm {
      const box = boxes().find((b) => b.id === id);
      if (!box) throw new Error(`no box ${id} for the editor`);
      const [x, y, z] = box.position;
      camera.position.set(x, y, z + CAMERA_DISTANCE);
      camera.lookAt(x, y, z);
      camera.updateMatrixWorld();
      const middle = CANVAS_PIXELS / 2;
      canvas.dispatchEvent(
        new PointerEvent("pointerdown", {
          button: 0,
          clientX: middle,
          clientY: middle,
          bubbles: true,
        }),
      );
      if (session.confirm?.editingId !== id) throw new Error(`the editor did not open ${id}`);
      return session.confirm;
    },
  };
}
