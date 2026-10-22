/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { trackMenuAvailability, trackMenuHeading, type MenuTrack } from "../timelineMenu";

/** A track whose keyframes all hold a box, unless `editableFrames` says otherwise. */
function menuTrack(
  id: string,
  view: string,
  start: number,
  end: number,
  keyframes: number[],
  editableFrames: number[] = keyframes,
): MenuTrack {
  return {
    id,
    view,
    start,
    end,
    keyframes: Int32Array.from(keyframes),
    editableFrames: Int32Array.from(editableFrames),
  };
}

const at = (track: MenuTrack, frame: number) => trackMenuAvailability(track, [track], frame);

describe("trackMenuAvailability: keyframe actions", () => {
  const boxes = menuTrack("t1", "cam1", 0, 20, [0, 10, 20]);
  const nothing = { canEdit: false, canRemove: false, canAdd: false, canSplit: false };

  it("edits, removes and splits on a middle keyframe", () => {
    expect(at(boxes, 10)).toEqual({
      trackletId: "t1",
      view: "cam1",
      frame: 10,
      isKeyframe: true,
      canEdit: true,
      canRemove: true,
      canAdd: false,
      canSplit: true,
      glueBefore: null,
      glueAfter: null,
    });
  });

  it("adds and splits between two boxes", () => {
    expect(at(boxes, 5)).toMatchObject({
      frame: 5,
      isKeyframe: false,
      canEdit: false,
      canRemove: false,
      canAdd: true,
      canSplit: true,
    });
  });

  it("splits after the first frame, never after the last", () => {
    expect(at(boxes, 0)).toMatchObject({ isKeyframe: true, canEdit: true, canSplit: true });
    expect(at(boxes, 20)).toMatchObject({
      isKeyframe: true,
      canEdit: true,
      canRemove: true,
      canAdd: false,
      canSplit: false,
    });
  });

  it("keeps a track's last two keyframes", () => {
    const pair = menuTrack("t2", "cam1", 0, 20, [0, 20]);
    expect(at(pair, 0)).toMatchObject({ isKeyframe: true, canEdit: true, canRemove: false });
    expect(at(pair, 20)).toMatchObject({ isKeyframe: true, canRemove: false });
    expect(at(pair, 10)).toMatchObject({ isKeyframe: false, canRemove: false, canAdd: true });
  });

  it("neither edits nor adds on a mask-only track", () => {
    const masks = menuTrack("m", "cam1", 0, 20, [0, 10, 20], []);
    expect(at(masks, 10)).toMatchObject({
      isKeyframe: true,
      canEdit: false,
      canRemove: true,
      canSplit: true,
    });
    expect(at(masks, 5)).toMatchObject({ isKeyframe: false, canAdd: false, canSplit: true });
  });

  it("adds only with a box or keypoints on both sides of the frame", () => {
    // Frame 20 holds a mask only.
    const mixed = menuTrack("x", "cam1", 0, 20, [0, 10, 20], [0, 10]);
    expect(at(mixed, 5).canAdd).toBe(true);
    expect(at(mixed, 15).canAdd).toBe(false);
    expect(at(mixed, 20)).toMatchObject({ isKeyframe: true, canEdit: false, canRemove: true });
  });

  it("adds nothing past the last keyframe of a range wider than its keyframes", () => {
    const wide = menuTrack("w", "cam1", 0, 19, [0, 12]);
    expect(at(wide, 15)).toMatchObject({ isKeyframe: false, canAdd: false, canSplit: true });
    expect(at(wide, 19)).toMatchObject({ isKeyframe: false, canAdd: false, canSplit: false });
  });

  it("offers nothing outside the track", () => {
    for (const frame of [-1, 21, 40]) {
      expect(at(boxes, frame)).toMatchObject({ frame, isKeyframe: false, ...nothing });
    }
  });

  it("only edits a single-frame track", () => {
    const single = menuTrack("s", "cam1", 7, 7, [7]);
    expect(at(single, 7)).toMatchObject({ isKeyframe: true, ...nothing, canEdit: true });
  });

  it("follows the rules on every frame around a track", () => {
    // Boxes on 3 and 10, masks only on 6 and 17.
    const track = menuTrack("r", "cam1", 3, 17, [3, 6, 10, 17], [3, 10]);
    const failures: string[] = [];
    for (let frame = 0; frame <= 20; frame += 1) {
      const isKeyframe = [3, 6, 10, 17].includes(frame);
      const expected = {
        isKeyframe,
        canEdit: frame === 3 || frame === 10,
        canRemove: isKeyframe,
        canAdd: !isKeyframe && frame > 3 && frame < 10,
        canSplit: frame >= 3 && frame < 17,
      };
      const can = at(track, frame);
      const actual = {
        isKeyframe: can.isKeyframe,
        canEdit: can.canEdit,
        canRemove: can.canRemove,
        canAdd: can.canAdd,
        canSplit: can.canSplit,
      };
      if (JSON.stringify(actual) !== JSON.stringify(expected)) {
        failures.push(`#${frame}: ${JSON.stringify(actual)}`);
      }
    }
    expect(failures).toEqual([]);
  });

  it("reads plain arrays too", () => {
    const plain: MenuTrack = {
      id: "p",
      view: "cam1",
      start: 0,
      end: 20,
      keyframes: [0, 10, 20],
      editableFrames: [0, 20],
    };
    expect(at(plain, 10)).toMatchObject({ isKeyframe: true, canEdit: false, canRemove: true });
    expect(at(plain, 15)).toMatchObject({ isKeyframe: false, canAdd: true });
  });
});

describe("trackMenuAvailability: glue", () => {
  const first = menuTrack("first", "cam1", 0, 10, [0, 10]);
  const middle = menuTrack("middle", "cam1", 20, 30, [20, 30]);
  const last = menuTrack("last", "cam1", 40, 50, [40, 50]);
  const otherView = menuTrack("cam2", "cam2", 12, 18, [12, 18]);
  const own = [first, middle, last, otherView];
  const glue = (track: MenuTrack, tracks: MenuTrack[] = own) => {
    const { glueBefore, glueAfter } = trackMenuAvailability(track, tracks, track.start);
    return { glueBefore, glueAfter };
  };

  it("glues to the nearest own tracks of the same view", () => {
    expect(glue(middle)).toEqual({ glueBefore: "first", glueAfter: "last" });
  });

  it("finds no track before the first one or after the last one", () => {
    expect(glue(first)).toEqual({ glueBefore: null, glueAfter: "middle" });
    expect(glue(last)).toEqual({ glueBefore: "middle", glueAfter: null });
  });

  it("ignores the other views", () => {
    expect(glue(otherView)).toEqual({ glueBefore: null, glueAfter: null });
  });

  it("glues the two halves of a split", () => {
    const left = menuTrack("left", "cam1", 0, 10, [0, 10]);
    const right = menuTrack("right", "cam1", 11, 20, [11, 20]);
    expect(glue(left, [left, right])).toEqual({ glueBefore: null, glueAfter: "right" });
    expect(glue(right, [left, right])).toEqual({ glueBefore: "left", glueAfter: null });
  });

  it("does not depend on the order of the list", () => {
    expect(glue(middle, [last, otherView, first, middle])).toEqual({
      glueBefore: "first",
      glueAfter: "last",
    });
    const far = menuTrack("far", "cam1", 60, 70, [60, 70]);
    expect(glue(middle, [far, last, first]).glueAfter).toBe("last");
  });

  it("glues to no track that shares a frame with this one", () => {
    const touchingBefore = menuTrack("touchingBefore", "cam1", 5, 20, [5, 20]);
    const touchingAfter = menuTrack("touchingAfter", "cam1", 30, 35, [30, 35]);

    expect(glue(middle, [touchingBefore, middle, touchingAfter])).toEqual({
      glueBefore: null,
      glueAfter: null,
    });
    expect(glue(middle, [first, touchingBefore, touchingAfter, last])).toEqual({
      glueBefore: "first",
      glueAfter: "last",
    });
  });

  it("skips the tracks that overlap", () => {
    const overlap = menuTrack("overlap", "cam1", 5, 25, [5, 25]);
    expect(glue(middle, [...own, overlap])).toEqual({ glueBefore: "first", glueAfter: "last" });
    expect(glue(overlap, [...own, overlap])).toEqual({ glueBefore: null, glueAfter: "last" });
  });

  it("keeps the first listed of two equally near tracks", () => {
    const twin = menuTrack("twin", "cam1", 2, 10, [2, 10]);
    expect(glue(middle, [first, twin, middle]).glueBefore).toBe("first");
    expect(glue(middle, [twin, first, middle]).glueBefore).toBe("twin");
  });

  it("does not need the track itself in the list", () => {
    expect(glue(middle, [first, last])).toEqual({ glueBefore: "first", glueAfter: "last" });
    expect(glue(middle, [])).toEqual({ glueBefore: null, glueAfter: null });
  });
});

describe("trackMenuHeading", () => {
  it("names the view and the frame range", () => {
    expect(trackMenuHeading(menuTrack("t", "left", 0, 58, [0, 58]))).toBe("left · #0–#58");
    expect(trackMenuHeading({ view: "cam 2", start: 81, end: 186 })).toBe("cam 2 · #81–#186");
  });
});
