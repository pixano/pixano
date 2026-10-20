/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { getContext, setContext } from "svelte";

import type { FrameWindow, MarkBox, PxWindow, TimelineGeometry } from "$lib/timeline/types";
import type { Entity, Tracklet } from "$lib/types/dataset";

/**
 * The timeline panel's measurements, shared with its rows, ruler and marks. The panel sets
 * an object of getters, so a child reading a field stays reactive to it.
 */
export interface TimelineLayoutContext {
  /** The frame↔x mapping of every lane. */
  readonly geometry: TimelineGeometry;
  /** The part of the lanes to draw (the visible part plus margins), in lane px. */
  readonly pxWindow: PxWindow;
  /** The frames of `pxWindow`. */
  readonly frameWindow: FrameWindow;
  readonly dpr: number;
  /** The frame rate times are computed with. */
  readonly fps: number;
}

const TIMELINE_LAYOUT_CONTEXT = Symbol("timeline-layout");

export function setTimelineLayoutContext(context: TimelineLayoutContext): void {
  setContext(TIMELINE_LAYOUT_CONTEXT, context);
}

export function getTimelineLayoutContext(): TimelineLayoutContext {
  return getContext<TimelineLayoutContext>(TIMELINE_LAYOUT_CONTEXT);
}

/** A mark drawn over a lane: its centre x in lane px and the lane's top in body px. */
export interface OverlayMark {
  x: number;
  laneTop: number;
  box: MarkBox;
  color: string;
}

/** The tooltip of a hovered tick. */
export interface OverlayTooltip {
  text: string;
  /** Centre x in lane px. */
  x: number;
  /** Top of the row it describes, in body px. */
  rowTop: number;
  rowHeight: number;
}

/** What a right-click on the timeline opened the track menu on. */
export interface TimelineMenuTarget {
  /** The row's entity, a sub-entity's own when it has a row. */
  entity: Entity;
  topId: string;
  /** The frame the actions apply to: the clicked one, or the current one from a header. */
  frame: number;
  /** The row's own tracks there, by camera. */
  tracks: Tracklet[];
}
