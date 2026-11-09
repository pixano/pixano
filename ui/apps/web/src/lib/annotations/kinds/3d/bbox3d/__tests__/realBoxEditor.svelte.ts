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

/** A point of the scene, in three.js space. */
export type ScenePoint = readonly [number, number, number];

/** A press the editor heard: the pointer is held down until `release`. */
export interface HeldPointer {
  /** Drag the pointer, still held, to where the camera sees another point. */
  moveTo(point: ScenePoint): void;
  /** Let go where the pointer now is. */
  release(): void;
}

/**
 * A real box editor, its effects running, wired to the session as
 * `BBox3DTool` wires it: the stored boxes handed over through `editorBoxOf`,
 * its gizmos shown as the session says, its reports — a box ready, a draw
 * canceled, a drag begun — into the session, and its reset as the session's.
 * A box is opened as a person opens it: a click on the canvas, the camera
 * looking straight at it.
 *
 * @param session The session the editor reports to.
 * @param collection Where the stored boxes are read, as the tool reads them.
 * @returns The editor; `open` clicks a stored box; `grab` presses where the
 *   camera sees a point; `grabRing` presses a ring of the box opened;
 *   `teardown` stops the editor.
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
      () => session.reportDragStarted(),
    );
  });
  flushSync();
  session.setResetEditor(() => editor.reset());

  /** The left button's event over where the camera sees `point`. */
  const pointerOver = (point: ScenePoint): PointerEventInit => {
    const onScreen = new THREE.Vector3(...point).project(camera);
    return {
      button: 0,
      clientX: ((onScreen.x + 1) / 2) * CANVAS_PIXELS,
      clientY: ((1 - onScreen.y) / 2) * CANVAS_PIXELS,
      bubbles: true,
    };
  };

  /**
   * Press, as a mouse does, where the camera sees `point`: on a gizmo of the
   * box opened, or on the box, the editor starts that gizmo's drag.
   *
   * @returns The pointer, held down.
   */
  const grab = (point: ScenePoint): HeldPointer => {
    // The gizmos' geometry follows the box the editor opened.
    flushSync();
    let at = pointerOver(point);
    canvas.dispatchEvent(new PointerEvent("pointerdown", at));
    return {
      moveTo(next) {
        at = pointerOver(next);
        canvas.dispatchEvent(new PointerEvent("pointermove", at));
      },
      release: () => canvas.dispatchEvent(new PointerEvent("pointerup", at)),
    };
  };

  return {
    editor,
    teardown,
    grab,
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
    /**
     * Press, as a mouse does, the rotation ring facing the camera of the box
     * `open` opened: the editor starts turning the box.
     *
     * @returns `turn` drags the pointer a quarter turn round the ring, which
     *   turns the box; `release` lets go where the pointer is.
     */
    grabRing() {
      flushSync();
      const [x, y, z] = editor.previewCenter;
      // Halfway between the two rings seen edge-on, which cross the one facing
      // the camera on its horizontal and vertical diameters.
      const offset = editor.gizmoRingRadius * Math.SQRT1_2;
      const held = grab([x + offset, y + offset, z]);
      if (editor.drawPhase !== "rotating") throw new Error("the editor did not take the ring");
      return {
        turn: () => held.moveTo([x - offset, y + offset, z]),
        release: () => held.release(),
      };
    },
  };
}
