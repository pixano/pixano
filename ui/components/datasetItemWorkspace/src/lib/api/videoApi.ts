/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  EditRectangleShape,
  EditShape,
  ItemObject,
  Tracklet,
  TrackletItem,
  TrackletWithItems,
  VideoItemBBox,
  VideoKeypoints,
  VideoObject,
} from "@pixano/core";
import { nanoid } from "nanoid";

export const getCurrentImageTime = (imageIndex: number, videoSpeed: number) => {
  const currentTimestamp = imageIndex * videoSpeed;
  const minutes = Math.floor(currentTimestamp / 60000);
  const seconds = ((currentTimestamp % 60000) / 1000).toFixed(0);
  return `${minutes}:${Number(seconds) < 10 ? "0" : ""}${seconds}`;
};

export const getImageIndexFromMouseMove = (
  event: MouseEvent,
  node: HTMLButtonElement,
  length: number,
) => {
  const parentBounding = node.parentElement?.getBoundingClientRect();
  let left = event.clientX - (parentBounding?.left || 0);
  if (left < 0) left = 0;
  const max = node.parentElement?.offsetWidth || left;
  if (left > max) left = max;
  const index = Math.floor((left / max) * length) - 1;
  return index < 0 ? 0 : index;
};

export const boxLinearInterpolation = (
  track: Tracklet[],
  imageIndex: number,
  boxes: VideoItemBBox[],
  view: string,
) => {
  const currentTracklet = track.find(
    (tracklet) => tracklet.start <= imageIndex && tracklet.end >= imageIndex,
  );
  if (!currentTracklet) return null;
  const view_boxes = boxes.filter((box) => box.view_id == view);
  const endIndex = view_boxes.findIndex(
    (box) => box.view_id == view && box.frame_index >= imageIndex,
  );
  if (endIndex < 0) {
    return null;
  }
  const end = view_boxes[endIndex];
  if (imageIndex == end.frame_index) {
    return end.coords;
  }
  const start = view_boxes[endIndex - 1] || boxes[0];
  const [startX, startY, startWidth, startHeight] = start.coords;
  const [endX, endY, endWidth, endHeight] = end.coords;

  const xInterpolation = (endX - startX) / (end.frame_index - start?.frame_index);
  const yInterpolation = (endY - startY) / (end.frame_index - start?.frame_index);
  const widthInterpolation = (endWidth - startWidth) / (end.frame_index - start?.frame_index);
  const heightInterpolation = (endHeight - startHeight) / (end.frame_index - start?.frame_index);
  const x = startX + xInterpolation * (imageIndex - start.frame_index);
  const y = startY + yInterpolation * (imageIndex - start.frame_index);
  const width = startWidth + widthInterpolation * (imageIndex - start.frame_index);
  const height = startHeight + heightInterpolation * (imageIndex - start.frame_index);
  return [x, y, width, height];
};

export const keypointsLinearInterpolation = (
  object: VideoObject,
  imageIndex: number,
  view: string,
) => {
  if (!object.keypoints) return null;
  const currentTracklet = object.track.find(
    (tracklet) => tracklet.start <= imageIndex && tracklet.end >= imageIndex,
  );
  if (!currentTracklet) return null;
  const view_keypoints = object.keypoints.filter((kp) => kp.view_id == view);
  const endIndex = view_keypoints.findIndex((kp) => kp.frame_index >= imageIndex);
  if (endIndex < 0) {
    return null;
  }
  const end = view_keypoints[endIndex];
  if (imageIndex == end.frame_index) {
    return end.vertices;
  } else {
    const start = view_keypoints[endIndex - 1] || view_keypoints[0];
    if (end.frame_index == start?.frame_index) {
      console.log("QQ", view);
      return start.vertices;
    } else {
      return start.vertices.map((vertex, i) => {
        const xInterpolation =
          (end.vertices[i].x - vertex.x) / (end.frame_index - start?.frame_index);
        const yInterpolation =
          (end.vertices[i].y - vertex.y) / (end.frame_index - start?.frame_index);
        const x = vertex.x + xInterpolation * (imageIndex - start.frame_index);
        const y = vertex.y + yInterpolation * (imageIndex - start.frame_index);
        return { ...vertex, x, y };
      });
    }
  }
};

export const deleteKeyBoxFromTracklet = (
  objects: ItemObject[],
  trackletItem: TrackletItem,
  objectId: ItemObject["id"],
) =>
  objects.map((object) => {
    if (objectId === object.id && object.datasetItemType === "video") {
      object.boxes = object.boxes?.filter((box) => box.frame_index !== trackletItem.frame_index);
      object.keypoints = object.keypoints?.filter(
        (keypoint) => keypoint.frame_index !== trackletItem.frame_index,
      );
      object.track = object.track
        .map((tracklet) => {
          if (tracklet.start === trackletItem.frame_index) {
            const nextBoxFrameIndex = object.boxes?.find(
              (box) => box.frame_index > trackletItem.frame_index,
            )?.frame_index;
            const nextKeypointFrameIndex = object.keypoints?.find(
              (keypoint) => keypoint.frame_index > trackletItem.frame_index,
            )?.frame_index;
            tracklet.start = nextBoxFrameIndex || nextKeypointFrameIndex || tracklet.end;
          }
          if (tracklet.end === trackletItem.frame_index) {
            const prevBoxFrameIndex = object.boxes
              ?.reverse()
              .find((box) => box.frame_index < trackletItem.frame_index)?.frame_index;
            const prevKeypointFrameIndex = object.keypoints
              ?.reverse()
              .find((keypoint) => keypoint.frame_index < trackletItem.frame_index)?.frame_index;
            tracklet.end = prevBoxFrameIndex || prevKeypointFrameIndex || tracklet.start;
          }
          return tracklet;
        })
        .filter((tracklet) => tracklet.end !== tracklet.start);
    }
    return object;
  });

const editBoxesInTracklet = (
  boxes: VideoObject["boxes"],
  currentFrame: number,
  shape: EditRectangleShape,
) =>
  boxes?.map((box) => {
    if (box.frame_index === currentFrame) {
      box.coords = shape.coords;
      box.is_key = true;
      return box;
    }
    return box;
  });

export const editKeyItemInTracklet = (
  objects: ItemObject[],
  shape: EditShape,
  currentFrame: number,
  objectIdBeingEdited: string | null,
) =>
  objects.map((object) => {
    if (
      object.id !== shape.shapeId ||
      object.datasetItemType !== "video" ||
      objectIdBeingEdited !== object.id
    ) {
      return object;
    }
    const currentTracklet = object.track.find(
      (t) => t.start <= currentFrame && t.end >= currentFrame,
    );
    if (shape.type === "keypoint" && object.keypoints) {
      object.keypoints = object.keypoints.map((kp) => {
        if (kp.frame_index === currentFrame) {
          kp.vertices = shape.vertices;
          kp.is_key = true;
          return kp;
        }
        return kp;
      });
      if (currentTracklet && !object.keypoints?.some((b) => b.frame_index === currentFrame)) {
        object.keypoints?.push({
          ...object.keypoints[0],
          vertices: shape.vertices,
          frame_index: currentFrame,
          is_key: true,
          tracklet_id: currentTracklet.id,
        });
      }
      object.keypoints?.sort((a, b) => a.frame_index - b.frame_index);
      object.displayedKeypoints = object.displayedKeypoints
        ? {
            ...object.displayedKeypoints,
            vertices: shape.vertices,
          }
        : undefined;
      return object;
    }
    if (shape.type === "rectangle" && object.boxes) {
      object.boxes = editBoxesInTracklet(object.boxes, currentFrame, shape);
      if (currentTracklet && !object.boxes?.some((b) => b.frame_index === currentFrame)) {
        object.boxes?.push({
          ...object.boxes[0],
          coords: shape.coords,
          frame_index: currentFrame,
          is_key: true,
          tracklet_id: currentTracklet.id,
        });
      }
      object.boxes?.sort((a, b) => a.frame_index - b.frame_index);
      object.displayedBox = object.displayedBox
        ? {
            ...object.displayedBox,
            coords: shape.coords,
          }
        : undefined;
      return object;
    }
    return object;
  });

const createNewTracklet = (
  track: Tracklet[],
  frameIndex: number,
  lastFrameIndex: number,
  item: TrackletItem,
) => {
  let nextIntervalStart = track.find((t) => t.start > frameIndex)?.start;
  nextIntervalStart = nextIntervalStart ? nextIntervalStart - 1 : lastFrameIndex;
  return {
    start: frameIndex,
    end: nextIntervalStart,
    id: item.tracklet_id,
    items: [
      {
        ...item,
        frame_index: frameIndex,
        is_key: true,
      },
      {
        ...item,
        frame_index: nextIntervalStart,
        is_key: true,
      },
    ],
  } as TrackletWithItems;
};

export const addKeyItem = (
  frameIndex: number,
  lastFrameIndex: number,
  track: TrackletWithItems[],
) => {
  const id = nanoid(5);
  const item: TrackletItem = {
    frame_index: frameIndex,
    is_key: true,
    is_thumbnail: false,
    tracklet_id: id,
  };
  const tracklet = track.find((t) => t.start <= frameIndex && t.end >= frameIndex);
  if (!tracklet) {
    const newTracklet = createNewTracklet(track, frameIndex, lastFrameIndex, item);
    track.push(newTracklet);
  } else {
    tracklet.items.push({ ...item, tracklet_id: tracklet.id });
    tracklet.items.sort((a, b) => a.frame_index - b.frame_index);
  }
  return track.sort((a, b) => a.start - b.start);
};

export const mapTrackItemsToObject = (
  trackWithItems: TrackletWithItems[],
  object: VideoObject,
  rightClickFrameIndex: number,
) => {
  const allItems = trackWithItems.reduce(
    (acc, tracklet) => [...acc, ...tracklet.items],
    [] as TrackletItem[],
  );

  const boxes: VideoObject["boxes"] = [];
  for (const displayedBox of object.displayedMBox) {
    boxes.push(
      object.boxes
        ? allItems.map((item) => {
            const box = {
              ...displayedBox,
              frame_index: item.frame_index,
              tracklet_id: item.tracklet_id,
              is_key: true,
            } as VideoItemBBox;
            const currentBox =
              object.boxes?.find(
                (box) =>
                  box.view_id == displayedBox.view_id && box.frame_index === item.frame_index,
              ) || box;
            return {
              ...item,
              ...currentBox,
            };
          })
        : undefined,
    );
  }
  const keypoints: VideoObject["keypoints"] = [];
  for (const displayedKeypoints of object.displayedMKeypoints) {
    keypoints.push(
      object.keypoints
        ? allItems.map((item) => {
            const keypoint = {
              ...displayedKeypoints,
              frame_index: rightClickFrameIndex,
              is_key: true,
            } as VideoKeypoints;
            const currentKeypoint =
              object.keypoints?.find(
                (kpt) =>
                  kpt.view_id == displayedKeypoints.view_id && kpt.frame_index === item.frame_index,
              ) || keypoint;
            return {
              ...item,
              ...currentKeypoint,
            };
          })
        : undefined,
    );
  }

  return { boxes, keypoints };
};

export const mapSplittedTrackToObject = (
  trackWithItems: TrackletWithItems[],
  object: VideoObject,
  rightClickFrameIndex: number,
) => {
  const allItems = trackWithItems.reduce(
    (acc, tracklet) => [...acc, ...tracklet.items],
    [] as TrackletItem[],
  );

  const boxes: VideoObject["boxes"] = [];
  for (const displayedBox of object.displayedMBox) {
    boxes.push(
      object.boxes
        ? allItems.map((item) => {
            const box = {
              ...displayedBox,
              frame_index: rightClickFrameIndex,
              is_key: true,
            } as VideoItemBBox;
            const currentBox =
              object.boxes?.find(
                (box) =>
                  box.view_id == displayedBox.view_id && box.tracklet_id === item.tracklet_id,
              ) || box;
            return {
              ...item,
              ...currentBox,
            };
          })
        : undefined,
    );
  }
  const keypoints: VideoObject["keypoints"] = [];
  for (const displayedKeypoints of object.displayedMKeypoints) {
    keypoints.push(
      object.keypoints
        ? allItems.map((item) => {
            const keypoint = {
              ...displayedKeypoints,
              frame_index: rightClickFrameIndex,
              is_key: true,
            } as VideoKeypoints;
            const currentKeypoint =
              object.keypoints?.find(
                (kpt) =>
                  kpt.view_id == displayedKeypoints.view_id && kpt.tracklet_id === item.tracklet_id,
              ) || keypoint;
            return {
              ...item,
              ...currentKeypoint,
            };
          })
        : undefined,
    );
  }

  return { boxes, keypoints };
};

export const mapTrackletItems = (object: VideoObject, tracklet: TrackletWithItems) => {
  const boxes = object.boxes?.filter(
    (box) =>
      box.tracklet_id !== tracklet.id ||
      tracklet.items.some((item) => item.frame_index === box.frame_index),
  );
  const keypoints = object.keypoints?.filter(
    (kp) =>
      kp.tracklet_id !== tracklet.id ||
      tracklet.items.some((item) => item.frame_index === kp.frame_index),
  );
  return { boxes, keypoints };
};

const filterItems = (
  items: TrackletItem[],
  newItem: TrackletItem,
  shouldBeFiltered: (index: VideoItemBBox["frame_index"]) => boolean,
) =>
  items.reduce((acc, item, i) => {
    if (i === 0) {
      acc.push(newItem);
    }
    if (shouldBeFiltered(item.frame_index)) {
      acc.push(item);
    }
    return acc
      .sort((a, b) => a.frame_index - b.frame_index)
      .map((item) => ({ ...item, tracklet_id: newItem.tracklet_id }));
  }, [] as TrackletItem[]);

export const splitTrackletInTwo = (
  previousTrack: TrackletWithItems[],
  trackletIndex: number,
  rightClickFrameIndex: number,
) => {
  const tracklet = previousTrack[trackletIndex];
  const startId = nanoid(10);
  const endId = nanoid(10);
  const startTracklet: TrackletWithItems = {
    start: tracklet.start,
    end: rightClickFrameIndex,
    id: startId,
    items: filterItems(
      tracklet.items,
      { tracklet_id: startId, frame_index: rightClickFrameIndex, is_key: true },
      (index) => index < rightClickFrameIndex,
    ),
  };
  const endTracklet: TrackletWithItems = {
    start: rightClickFrameIndex + 1,
    end: tracklet.end,
    id: endId,
    items: filterItems(
      tracklet.items,
      { tracklet_id: endId, frame_index: rightClickFrameIndex + 1, is_key: true },
      (index) => index > rightClickFrameIndex + 1,
    ),
  };
  return [
    ...previousTrack.slice(0, trackletIndex),
    startTracklet,
    endTracklet,
    ...previousTrack.slice(trackletIndex + 1),
  ];
};

export const filterTrackletItems = (
  newFrameIndex: VideoItemBBox["frame_index"],
  draggedFrameIndex: VideoItemBBox["frame_index"],
  tracklet: TrackletWithItems,
) => {
  const isGoingRight = newFrameIndex > draggedFrameIndex;
  const isStart = draggedFrameIndex === tracklet.start;
  const isEnd = draggedFrameIndex === tracklet.end;

  tracklet.items = tracklet.items.filter((box) => {
    if (isGoingRight && box.frame_index > draggedFrameIndex && box.frame_index < newFrameIndex) {
      return false;
    }
    if (!isGoingRight && box.frame_index > newFrameIndex && box.frame_index < draggedFrameIndex) {
      return false;
    }
    return true;
  });
  if (isStart) {
    tracklet.start = newFrameIndex;
    tracklet.items[0].is_key = true;
    tracklet.items[0].frame_index = newFrameIndex;
    return tracklet;
  }
  if (isEnd) {
    tracklet.end = newFrameIndex;
    tracklet.items[tracklet.items.length - 1].is_key = true;
    tracklet.items[tracklet.items.length - 1].frame_index = newFrameIndex;
    return tracklet;
  }
  tracklet.items = tracklet.items.map((box) => {
    if (box.frame_index === draggedFrameIndex) {
      box.is_key = true;
      box.frame_index = newFrameIndex;
      return box;
    }
    return box;
  });
  if (newFrameIndex < tracklet.start) {
    tracklet.start = newFrameIndex;
  }
  if (newFrameIndex > tracklet.end) {
    tracklet.end = newFrameIndex;
  }
  return tracklet;
};

export const getNewTrackletValues = (
  isStart: boolean,
  newFrameIndex: number,
  tracklet: TrackletWithItems,
): TrackletWithItems => {
  const startingBox = {
    ...tracklet.items?.[0],
    frame_index: isStart ? newFrameIndex : tracklet.start,
  };
  const endingBox = {
    ...tracklet.items?.[tracklet.items.length - 1],
    frame_index: isStart ? tracklet.end : newFrameIndex,
  };
  const newTracklet = {
    ...tracklet,
    items: [startingBox, endingBox],
    start: isStart ? newFrameIndex : tracklet.start,
    end: isStart ? tracklet.end : newFrameIndex,
  };
  return newTracklet;
};

export const deleteTracklet = (
  objects: ItemObject[],
  objectId: VideoObject["id"],
  trackletIndex: number,
  trackWithItems: TrackletWithItems[],
) =>
  objects
    .map((obj) => {
      if (obj.id === objectId && obj.datasetItemType === "video") {
        obj.track.splice(trackletIndex, 1);
        obj.boxes = obj.boxes?.filter(
          (box) =>
            !(
              box.frame_index >= trackWithItems[trackletIndex].start &&
              box.frame_index <= trackWithItems[trackletIndex].end
            ),
        );
        obj.keypoints = obj.keypoints?.filter(
          (kp) =>
            !(
              kp.frame_index >= trackWithItems[trackletIndex].start &&
              kp.frame_index <= trackWithItems[trackletIndex].end
            ),
        );
      }
      return obj;
    })
    .filter((obj) => obj.datasetItemType === "video" && obj.track.length > 0);
