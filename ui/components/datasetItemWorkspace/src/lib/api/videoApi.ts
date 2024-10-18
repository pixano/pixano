/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BBox, Tracklet } from "@pixano/core";
import type {
  KeypointsTemplate,
  ItemObject,
  TrackletItem,
  TrackletWithItems,
  VideoItemBBox,
  VideoItemKeypoints,
  VideoObject,
  SaveItem,
} from "@pixano/core";
import { nanoid } from "nanoid";

import { addOrUpdateSaveItem } from "./objectsApi";
import { saveData } from "../../lib/stores/datasetItemWorkspaceStores";

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
  const index = Math.round((left / max) * length) - 1;
  return index < 0 ? 0 : index;
};

export const boxLinearInterpolation = (
  boxes: BBox[], //bboxes of the tracklet
  imageIndex: number,
): BBox | undefined => {
  //Note: this suppose boxes are sorted by frame_index (it should)
  const endIndex = boxes.findIndex((box) => box.frame_index >= imageIndex);
  if (endIndex < 0) {
    return undefined;
  }
  const endBox = boxes[endIndex];
  if (imageIndex == endBox.frame_index) {
    return endBox;
  }

  const startBox = boxes[endIndex - 1] || boxes[0];
  const [startX, startY, startWidth, startHeight] = startBox.data.coords;
  const [endX, endY, endWidth, endHeight] = endBox.data.coords;

  const xInterpolation = (endX - startX) / (endBox.frame_index - startBox.frame_index);
  const yInterpolation = (endY - startY) / (endBox.frame_index - startBox.frame_index);
  const widthInterpolation = (endWidth - startWidth) / (endBox.frame_index - startBox.frame_index);
  const heightInterpolation =
    (endHeight - startHeight) / (endBox.frame_index - startBox.frame_index);
  const x = startX + xInterpolation * (imageIndex - startBox.frame_index);
  const y = startY + yInterpolation * (imageIndex - startBox.frame_index);
  const width = startWidth + widthInterpolation * (imageIndex - startBox.frame_index);
  const height = startHeight + heightInterpolation * (imageIndex - startBox.frame_index);
  // make a new BBox with interpolated coords
  const interpolatedBox = structuredClone(startBox);
  interpolatedBox.id = nanoid(5); //not needed but it still ensure unique id
  interpolatedBox.frame_index = imageIndex;
  // for convenience, we store refs to start & end boxes
  interpolatedBox.startRef = startBox;
  interpolatedBox.endRef = endBox;
  //TODO ? we should change view_ref.id too ... (requires $views or declined)
  interpolatedBox.data.coords = [x, y, width, height];
  return interpolatedBox;
};

export const keypointsLinearInterpolation = (
  keypoints: KeypointsTemplate[], //keypoints of the tracklet
  imageIndex: number,
): KeypointsTemplate | undefined => {
  //Note: this suppose keypoints are sorted by frame_index (it should)
  const endIndex = keypoints.findIndex((kpt) => kpt.frame_index >= imageIndex);
  if (endIndex < 0) {
    return undefined;
  }
  const endKpt = keypoints[endIndex];
  if (imageIndex == endKpt.frame_index) {
    return endKpt;
  }
  const startKpt = keypoints[endIndex - 1] || keypoints[0];
  if (endKpt.frame_index == startKpt?.frame_index) {
    return startKpt;
  } else {
    const vertices = startKpt.vertices.map((vertex, i) => {
      const xInterpolation =
        (endKpt.vertices[i].x - vertex.x) / (endKpt.frame_index - startKpt?.frame_index);
      const yInterpolation =
        (endKpt.vertices[i].y - vertex.y) / (endKpt.frame_index - startKpt?.frame_index);
      const x = vertex.x + xInterpolation * (imageIndex - startKpt.frame_index);
      const y = vertex.y + yInterpolation * (imageIndex - startKpt.frame_index);
      return { ...vertex, x, y };
    });
    // make a new BBox with interpolated coords
    const interpolatedKpt = structuredClone(startKpt);
    interpolatedKpt.id = nanoid(5); //not needed but it still ensure unique id
    interpolatedKpt.frame_index = imageIndex;
    // for convenience, we store refs to start & end kpts
    interpolatedKpt.startRef = startKpt;
    interpolatedKpt.endRef = endKpt;
    //TODO ? we should change view_ref.id too ... (requires $views or declined)
    interpolatedKpt.vertices = vertices;
    return interpolatedKpt;
  }
};

export const deleteKeyBoxFromTracklet = (
  objects: ItemObject[],
  trackletItem: TrackletItem,
  objectId: ItemObject["id"],
) =>
  objects.map((object) => {
    const del_data: Record<string, string[]> = {};
    if (objectId === object.id && object.datasetItemType === "video") {
      const view_id = getViewIdFromTrackletItem(trackletItem, object.track);
      object.boxes = object.boxes?.filter((box) => {
        if (box.frame_index !== trackletItem.frame_index || box.view_id !== view_id) {
          return true;
        } else {
          del_data["bbox"] = [box.id];
          return false;
        }
      });
      object.keypoints = object.keypoints?.filter((keypoint) => {
        if (keypoint.frame_index !== trackletItem.frame_index || keypoint.view_id !== view_id) {
          return true;
        } else {
          del_data["keypoints"] = [keypoint.id];
          return false;
        }
      });
      object.track = object.track
        .map((tracklet) => {
          let changed_tracklet = false;
          if (tracklet.view_id !== view_id) return tracklet;
          if (tracklet.start === trackletItem.frame_index) {
            const nextBoxFrameIndex = object.boxes?.find(
              (box) => box.frame_index > trackletItem.frame_index && box.view_id == view_id,
            )?.frame_index;
            const nextKeypointFrameIndex = object.keypoints?.find(
              (keypoint) =>
                keypoint.frame_index > trackletItem.frame_index && keypoint.view_id == view_id,
            )?.frame_index;
            tracklet.start = Math.min(
              nextBoxFrameIndex || tracklet.end,
              nextKeypointFrameIndex || tracklet.end,
              tracklet.end,
            );
            changed_tracklet = true;
          }
          if (tracklet.end === trackletItem.frame_index) {
            const prevBoxFrameIndex = object.boxes
              ?.reverse()
              .find(
                (box) => box.frame_index < trackletItem.frame_index && box.view_id == view_id,
              )?.frame_index;
            const prevKeypointFrameIndex = object.keypoints
              ?.reverse()
              .find(
                (keypoint) =>
                  keypoint.frame_index < trackletItem.frame_index && keypoint.view_id == view_id,
              )?.frame_index;
            tracklet.end = Math.max(
              prevBoxFrameIndex || tracklet.start,
              prevKeypointFrameIndex || tracklet.start,
              tracklet.start,
            );
            changed_tracklet = true;
          }
          if (changed_tracklet) {
            const save_item: SaveItem = {
              change_type: "add_or_update",
              ref_name: "tracklet",
              is_video: true,
              data: { ...tracklet, entity_ref: { id: objectId, name: "top_entity" } },
            };
            saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
          }
          return tracklet;
        })
        .filter((tracklet) => tracklet.end !== tracklet.start); //TODO if remove, may also remove track (if no other tracklet on view...)
      const save_item: SaveItem = {
        change_type: "delete",
        ref_name: "",
        is_video: true,
        data: del_data,
      };
      saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
    }
    return object;
  });

const createNewTracklet = (
  track: Tracklet[],
  frameIndex: number,
  lastFrameIndex: number,
  item: TrackletItem,
  view_id: string,
) => {
  let nextIntervalStart = track.find((t) => t.view_id == view_id && t.start > frameIndex)?.start;
  nextIntervalStart = nextIntervalStart ? nextIntervalStart - 1 : lastFrameIndex;
  return {
    start: frameIndex,
    end: nextIntervalStart,
    id: item.tracklet_id,
    view_id: view_id,
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
  view_id: string,
) => {
  const item: TrackletItem = {
    frame_index: frameIndex,
    is_key: true,
    tracklet_id: "", //field required by tslint
  };
  const tracklet = track.find(
    (tracklet) =>
      tracklet.view_id === view_id && tracklet.start <= frameIndex && frameIndex <= tracklet.end,
  );
  if (!tracklet) {
    item.tracklet_id = nanoid(5);
    const newTracklet = createNewTracklet(track, frameIndex, lastFrameIndex, item, view_id);
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
  if (object.displayedMBox) {
    for (const displayedBox of object.displayedMBox) {
      allItems.forEach((item) => {
        let currentBox = null;
        if (item.frame_index == rightClickFrameIndex) {
          currentBox = {
            ...displayedBox,
            frame_index: item.frame_index,
            tracklet_id: rightClickFrameIndex, //item.tracklet_id,
            is_key: true,
          };
          const save_item_left: SaveItem = {
            change_type: "add_or_update",
            ref_name: "bbox",
            is_video: true,
            data: { ...displayedBox, entity_ref: { id: object.id, name: "top_entity" } },
          };
          saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_left));
        } else {
          currentBox = object.boxes?.find(
            (b) => b.view_id == displayedBox.view_id && b.frame_index === item.frame_index,
          );
        }
        if (currentBox) {
          boxes.push({
            ...item,
            ...currentBox,
          } as VideoItemBBox);
        }
      });
    }
  }
  const keypoints: VideoObject["keypoints"] = [];
  if (object.displayedMKeypoints) {
    for (const displayedKeypoints of object.displayedMKeypoints) {
      allItems.forEach((item) => {
        let currentKeypoint = null;
        if (item.frame_index == rightClickFrameIndex) {
          currentKeypoint = {
            ...displayedKeypoints,
            frame_index: item.frame_index,
            tracklet_id: rightClickFrameIndex, //item.tracklet_id,
            is_key: true,
          };
          const save_item_left: SaveItem = {
            change_type: "add_or_update",
            ref_name: "keypoints",
            is_video: true,
            data: { ...displayedKeypoints, entity_ref: { id: object.id, name: "top_entity" } },
          };
          saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_left));
        } else {
          currentKeypoint = object.keypoints?.find(
            (kpt) =>
              kpt.view_id == displayedKeypoints.view_id && kpt.frame_index === item.frame_index,
          );
        }
        if (currentKeypoint) {
          keypoints.push({
            ...item,
            ...currentKeypoint,
          } as VideoItemKeypoints);
        }
      });
    }
  }
  return { boxes, keypoints };
};

export const mapSplittedTrackToObject = (
  trackWithItems: TrackletWithItems[],
  object: VideoObject,
) => {
  const boxes: VideoObject["boxes"] = [];
  const keypoints: VideoObject["keypoints"] = [];
  trackWithItems.forEach((tracklet) => {
    object.boxes?.forEach((box) => {
      if (
        box.view_id == tracklet.view_id &&
        box.frame_index >= tracklet.start &&
        box.frame_index <= tracklet.end
      ) {
        box.tracklet_id = tracklet.id;
        boxes.push(box);
      }
    });
    object.keypoints?.forEach((kpt) => {
      if (
        kpt.view_id == tracklet.view_id &&
        kpt.frame_index >= tracklet.start &&
        kpt.frame_index <= tracklet.end
      ) {
        kpt.tracklet_id = tracklet.id;
        keypoints.push(kpt);
      }
    });
  });
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

export const splitTrackletInTwo = (
  previousTrack: TrackletWithItems[],
  tracklet: TrackletWithItems,
  rightClickFrameIndex: number,
  prev: number,
  next: number,
  entity_id: string,
) => {
  const trackletIndex = previousTrack.findIndex((trklet) => trklet.id === tracklet.id);
  const endId = nanoid(10);

  const leftTracklet: TrackletWithItems = {
    ...tracklet,
    end: prev,
    items: tracklet.items.filter((item) => item.frame_index <= prev),
  };
  const rightTracklet: TrackletWithItems = {
    ...tracklet,
    id: endId,
    start: next,
    items: tracklet.items
      .filter((item) => item.frame_index >= next)
      .map((item) => {
        item.tracklet_id = endId;
        return item;
      }),
  };

  const getTracklet = (tracklet: TrackletWithItems): Tracklet => {
    const { items: drop, ...tracklet_without_items } = tracklet;
    drop; // access drop only to prevent ts-lint warning (! ts-expect-error doesn't work here !)
    return tracklet_without_items;
  };
  const save_item_left: SaveItem = {
    change_type: "add_or_update",
    ref_name: "tracklet",
    is_video: true,
    data: { ...getTracklet(leftTracklet), entity_ref: { id: entity_id, name: "top_entity" } },
  };
  saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_left));
  const save_item_right: SaveItem = {
    change_type: "add_or_update",
    ref_name: "tracklet",
    is_video: true,
    data: { ...getTracklet(rightTracklet), entity_ref: { id: entity_id, name: "top_entity" } },
  };
  saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item_right));
  return [
    ...previousTrack.slice(0, trackletIndex),
    leftTracklet,
    rightTracklet,
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

export const getViewIdFromTrackletItem = (
  trackletItem: TrackletItem,
  tracklets: Tracklet[],
): string => {
  const tracklet = tracklets.find((tracklet) => tracklet.id === trackletItem.tracklet_id);
  if (tracklet) {
    return tracklet.view_id;
  }
  return "";
};

export const getNewTrackletValues = (
  isStart: boolean,
  newFrameIndex: number,
  tracklet: TrackletWithItems,
): TrackletWithItems => {
  const startingBox: TrackletItem = {
    ...tracklet.items?.[0],
    frame_index: isStart ? newFrameIndex : tracklet.start,
  };
  const endingBox: TrackletItem = {
    ...tracklet.items?.[tracklet.items.length - 1],
    frame_index: isStart ? tracklet.end : newFrameIndex,
  };
  const newTracklet: TrackletWithItems = {
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
  to_del_tracklet: TrackletWithItems,
) =>
  objects
    .map((obj) => {
      if (obj.id === objectId && obj.datasetItemType === "video") {
        const del_data: Record<string, string[]> = {
          tracklet: [to_del_tracklet.id],
          bbox: [],
          keypoints: [],
        };
        obj.track = obj.track.filter((tracklet) => tracklet.id !== to_del_tracklet.id);
        obj.boxes = obj.boxes?.filter((box) => {
          if (box.tracklet_id !== to_del_tracklet.id) {
            return true;
          } else {
            del_data["bbox"].push(box.id);
            return false;
          }
        });
        obj.keypoints = obj.keypoints?.filter((kp) => {
          if (kp.tracklet_id !== to_del_tracklet.id) {
            return true;
          } else {
            del_data["keypoints"].push(kp.id);
            return false;
          }
        });
        const save_item: SaveItem = {
          change_type: "delete",
          ref_name: "",
          is_video: true,
          data: del_data,
        };
        saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
      }
      return obj;
    })
    .filter((obj) => obj.datasetItemType === "video" && obj.track.length > 0);
