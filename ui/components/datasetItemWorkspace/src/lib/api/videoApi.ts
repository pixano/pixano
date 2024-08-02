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
  track: Tracklet[],
  imageIndex: number,
  boxes: VideoItemBBox[],
  view: string,
) => {
  //TMP
  // const no_interpol = boxes.find((box) => box.view_id == view && box.frame_index == imageIndex);
  // return no_interpol?no_interpol.coords:null;

  const currentTracklet = track.find(
    (tracklet) =>
      tracklet.start <= imageIndex && tracklet.end >= imageIndex && tracklet.view_id == view,
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
  //TMP
  // const no_interpol = object.keypoints?.find((box) => box.view_id == view && box.frame_index == imageIndex);
  // return no_interpol?no_interpol.vertices:null;

  if (!object.keypoints) return null;
  const currentTracklet = object.track.find(
    (tracklet) =>
      tracklet.start <= imageIndex && tracklet.end >= imageIndex && tracklet.view_id == view,
  );
  if (!currentTracklet) return null;
  const view_keypoints = object.keypoints?.filter((kp) => kp.view_id == view);
  const endIndex = view_keypoints?.findIndex((kp) => kp.frame_index >= imageIndex);
  if (endIndex < 0) {
    return null;
  }
  const end = view_keypoints[endIndex];
  if (imageIndex == end.frame_index) {
    return end.vertices;
  } else {
    const start = view_keypoints[endIndex - 1] || view_keypoints[0];
    if (end.frame_index == start?.frame_index) {
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
    const del_data = {};
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
) => {
  let saveData: SaveItem;
  return {
    objects: objects.map((object) => {
      if (
        object.id !== shape.shapeId ||
        object.datasetItemType !== "video" ||
        objectIdBeingEdited !== object.id
      ) {
        return object;
      }
      const currentTracklet = object.track.find(
        (t) => t.start <= currentFrame && t.end >= currentFrame && t.view_id == shape.viewId,
      );
      let new_obj;
      if (shape.type === "keypoints" && object.keypoints) {
        object.keypoints = object.keypoints.map((kp) => {
          if (kp.frame_index === currentFrame) {
            kp.vertices = shape.vertices;
            kp.is_key = true;
            return kp;
          }
          return kp;
        });
        if (currentTracklet) {
          new_obj = {
            ...object.keypoints[0],
            vertices: shape.vertices,
            frame_index: currentFrame,
            is_key: true,
            tracklet_id: currentTracklet.id,
          };
          if (!object.keypoints?.some((b) => b.frame_index === currentFrame)) {
            object.keypoints?.push(new_obj);
          }
        }
        object.keypoints?.sort((a, b) => a.frame_index - b.frame_index);
        object.displayedMKeypoints = object.displayedMKeypoints?.map((kpt) => {
          if (kpt.view_id == shape.viewId) {
            return {
              ...kpt,
              vertices: shape.vertices,
            };
          }
          return kpt;
        });
      }
      if (shape.type === "bbox" && object.boxes) {
        object.boxes = editBoxesInTracklet(object.boxes, currentFrame, shape);
        if (currentTracklet) {
          new_obj = {
            ...object.boxes[0],
            coords: shape.coords,
            frame_index: currentFrame,
            is_key: true,
            tracklet_id: currentTracklet.id,
          };
          if (!object.boxes?.some((b) => b.frame_index === currentFrame)) {
            object.boxes?.push(new_obj);
          }
        }
        object.boxes?.sort((a, b) => a.frame_index - b.frame_index);
        object.displayedMBox = object.displayedMBox?.map((box) => {
          if (box.view_id == shape.viewId) {
            return {
              ...box,
              coords: shape.coords,
            };
          }
          return box;
        });
      }
      saveData = {
        change_type: "add_or_update",
        ref_name: shape.type, //this should represent the annotation table to be refered...
        is_video: true,
        data: new_obj,
      };
      return object;
    }),
    save_data: saveData,
  };
};

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
          boxes.push({
            ...item,
            ...currentKeypoint,
          } as VideoKeypoints);
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
  const selectAnn = (
    ann: VideoItemBBox | VideoKeypoints,
    tracklet: TrackletWithItems,
    arr: VideoItemBBox[] | VideoKeypoints[],
  ) => {
    if (
      ann.view_id == tracklet.view_id &&
      ann.frame_index >= tracklet.start &&
      ann.frame_index <= tracklet.end
    ) {
      ann.tracklet_id = tracklet.id;
      arr.push(ann);
    }
  };
  trackWithItems.forEach((tracklet) => {
    object.boxes?.forEach((box) => selectAnn(box, tracklet, boxes));
    object.keypoints?.forEach((kpt) => selectAnn(kpt, tracklet, keypoints));
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
