import type {
  EditRectangleShape,
  EditShape,
  ItemObject,
  Tracklet,
  VideoItemBBox,
  VideoObject,
} from "@pixano/core";

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

export const linearInterpolation = (track: Tracklet[], imageIndex: number) => {
  const currentTracklet = track.find(
    (tracklet) => tracklet.start <= imageIndex && tracklet.end >= imageIndex,
  );
  if (!currentTracklet) return null;
  let endIndex = currentTracklet.boxes.findIndex((box) => box.frame_index > imageIndex);
  endIndex = endIndex < 0 ? currentTracklet.boxes.length - 1 : endIndex;
  const start = currentTracklet.boxes[endIndex - 1] || currentTracklet.boxes[0];
  const end = currentTracklet.boxes[endIndex];
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

export const deleteKeyBoxFromTracklet = (
  objects: ItemObject[],
  box: VideoItemBBox,
  objectId: ItemObject["id"],
) =>
  objects.map((object) => {
    if (objectId === object.id && object.datasetItemType === "video") {
      object.track = object.track
        .map((tracklet) => {
          if (tracklet.start <= box.frame_index && tracklet.end >= box.frame_index) {
            tracklet.boxes = tracklet.boxes.filter(
              (keyBox) => keyBox.frame_index !== box.frame_index,
            );
            tracklet.start = tracklet.boxes[0].frame_index;
            tracklet.end = tracklet.boxes[tracklet.boxes.length - 1].frame_index;
          }
          return tracklet;
        })
        .filter((tracklet) => tracklet.boxes.length > 1);
    }
    return object;
  });

const editBoxesInTracklet = (
  boxes: VideoItemBBox[],
  currentFrame: number,
  shape: EditRectangleShape,
) =>
  boxes.map((box) => {
    if (box.frame_index === currentFrame) {
      box.coords = shape.coords;
      box.is_key = true;
    }
    return box;
  });

const addBoxToTrackletBoxes = (tracklet: Tracklet, currentFrame: number, box: VideoItemBBox) => {
  if (!tracklet.boxes.some((b) => b.frame_index === currentFrame)) {
    tracklet.boxes.push(box);
    tracklet.boxes.sort((a, b) => a.frame_index - b.frame_index);
    tracklet.start = tracklet.boxes[0].frame_index;
    tracklet.end = tracklet.boxes[tracklet.boxes.length - 1].frame_index;
  }
  return tracklet;
};

export const editKeyBoxInTracklet = (
  objects: ItemObject[],
  shape: EditShape,
  currentFrame: number,
  objectIdBeingEdited: string | null,
) =>
  objects.map((object) => {
    if (
      shape.type === "rectangle" &&
      object.id === shape.shapeId &&
      object.datasetItemType === "video" &&
      objectIdBeingEdited === object.id
    ) {
      object.track = object.track.map((tracklet) => {
        if (tracklet.start <= currentFrame && tracklet.end >= currentFrame) {
          tracklet.boxes = editBoxesInTracklet(tracklet.boxes, currentFrame, shape);
          tracklet = addBoxToTrackletBoxes(tracklet, currentFrame, {
            ...tracklet.boxes[0],
            coords: shape.coords,
            frame_index: currentFrame,
            is_key: true,
          });
          object.displayedBox.coords = shape.coords;
        }
        return tracklet;
      });
    }
    return object;
  });

const createNewTracklet = (
  track: Tracklet[],
  frameIndex: number,
  lastFrameIndex: number,
  box: VideoItemBBox,
) => {
  let nextIntervalStart = track.find((t) => t.start > frameIndex)?.start;
  nextIntervalStart = nextIntervalStart ? nextIntervalStart - 1 : lastFrameIndex;
  return {
    start: frameIndex,
    end: nextIntervalStart,
    boxes: [
      {
        ...box,
        frame_index: frameIndex,
        is_key: true,
      },
      {
        ...box,
        frame_index: nextIntervalStart,
        is_key: true,
      },
    ],
  } as Tracklet;
};

const addKeyBoxToTracklet = (track: Tracklet[], currentTracklet: Tracklet, box: VideoItemBBox) =>
  track.map((tracklet) => {
    if (tracklet.start === currentTracklet.start && tracklet.end === currentTracklet.end) {
      const currentBox = tracklet.boxes.find((b) => b.frame_index === box.frame_index);
      if (currentBox) {
        tracklet.boxes = tracklet.boxes.map((b) => {
          if (b.frame_index === box.frame_index) {
            return box;
          }
          return b;
        });
      } else {
        tracklet.boxes.push(box);
        tracklet.boxes.sort((a, b) => a.frame_index - b.frame_index);
        tracklet.start = tracklet.boxes[0].frame_index;
        tracklet.end = tracklet.boxes[tracklet.boxes.length - 1].frame_index;
      }
    }
    return tracklet;
  });

export const addKeyBox = (
  objects: ItemObject[],
  keyBox: VideoItemBBox,
  objectId: string,
  frameIndex: number,
  lastFrameIndex: number,
) => {
  return objects.map((object) => {
    if (objectId !== object.id) return object;
    if (object.datasetItemType !== "video") return object;
    const tracklet = object.track.find((t) => t.start <= frameIndex && t.end >= frameIndex);
    if (!tracklet) {
      const newTracklet = createNewTracklet(object.track, frameIndex, lastFrameIndex, keyBox);
      object.track.push(newTracklet);
    } else {
      object.track = addKeyBoxToTracklet(object.track, tracklet, keyBox);
    }
    object.track.sort((a, b) => a.start - b.start);
    return object;
  });
};

export const findNeighbors = (
  track: Tracklet[],
  currentTracklet: Tracklet,
  frameIndex: VideoItemBBox["frame_index"],
  lastFrameIndex: number,
): [number, number] => {
  const currentIntervalIndex = track.findIndex(
    (int) => int.start === currentTracklet.start && int.end === currentTracklet.end,
  );
  if (currentIntervalIndex < 0) return [0, 0];
  const prevTracklet = track[currentIntervalIndex - 1];
  let prevNeighbor = currentTracklet.boxes.find((box) => box.frame_index < frameIndex)?.frame_index;
  if (!prevNeighbor && prevTracklet) {
    prevNeighbor = prevTracklet.boxes[prevTracklet.boxes.length - 1]?.frame_index;
  }
  prevNeighbor = prevNeighbor || 0;

  let nextNeighbor = currentTracklet.boxes.find((box) => box.frame_index > frameIndex)?.frame_index;
  const nextTracklet = track[currentIntervalIndex + 1];
  if (!nextNeighbor && nextTracklet) {
    nextNeighbor = nextTracklet.boxes[0]?.frame_index;
  }
  nextNeighbor = nextNeighbor || lastFrameIndex + 1;

  return [prevNeighbor, nextNeighbor];
};

const filterBoxes = (
  boxes: Tracklet["boxes"],
  newBox: VideoItemBBox,
  shouldBeFiltered: (index: VideoItemBBox["frame_index"]) => boolean,
) =>
  boxes.reduce(
    (acc, box, i) => {
      if (i === 0) {
        acc.push(newBox);
      }
      if (shouldBeFiltered(box.frame_index)) {
        acc.push(box);
      }
      return acc.sort((a, b) => a.frame_index - b.frame_index);
    },
    [] as Tracklet["boxes"],
  );

export const splitTrackletInTwo = (
  object: VideoObject,
  trackletIndex: number,
  rightClickFrameIndex: number,
) => {
  const tracklet = object.track[trackletIndex];
  const startTracklet: Tracklet = {
    start: tracklet.start,
    end: rightClickFrameIndex,
    boxes: filterBoxes(
      tracklet.boxes,
      { ...object.displayedBox, frame_index: rightClickFrameIndex, is_key: true },
      (index) => index < rightClickFrameIndex,
    ),
  };
  const endTracklet: Tracklet = {
    start: rightClickFrameIndex + 1,
    end: tracklet.end,
    boxes: filterBoxes(
      tracklet.boxes,
      { ...object.displayedBox, frame_index: rightClickFrameIndex + 1, is_key: true },
      (index) => index > rightClickFrameIndex + 1,
    ),
  };
  return [
    ...object.track.slice(0, trackletIndex),
    startTracklet,
    endTracklet,
    ...object.track.slice(trackletIndex + 1),
  ];
};

export const filterTrackletBoxes = (
  newFrameIndex: VideoItemBBox["frame_index"],
  draggedFrameIndex: VideoItemBBox["frame_index"],
  currentTracklet: Tracklet,
  objects: ItemObject[],
  objectId: ItemObject["id"],
) => {
  const isGoingRight = newFrameIndex > draggedFrameIndex;
  const isStart = draggedFrameIndex === currentTracklet.start;

  return objects.map((object) => {
    if (object.id === objectId && object.datasetItemType === "video") {
      object.track = object.track.map((tracklet) => {
        if (tracklet.start === currentTracklet.start && tracklet.end === currentTracklet.end) {
          tracklet.boxes = tracklet.boxes.filter((box) => {
            if (
              isGoingRight &&
              box.frame_index > draggedFrameIndex &&
              box.frame_index < newFrameIndex
            ) {
              return false;
            }
            if (
              !isGoingRight &&
              box.frame_index > newFrameIndex &&
              box.frame_index < draggedFrameIndex
            ) {
              return false;
            }
            return true;
          });
          if (isStart && !isGoingRight) {
            tracklet.start = newFrameIndex;
            tracklet.boxes[0].is_key = true;
            tracklet.boxes[0].frame_index = newFrameIndex;
            return tracklet;
          }
          if (!isStart && isGoingRight) {
            tracklet.end = newFrameIndex;
            tracklet.boxes[tracklet.boxes.length - 1].is_key = true;
            tracklet.boxes[tracklet.boxes.length - 1].frame_index = newFrameIndex;
            return tracklet;
          }
          if (isStart && isGoingRight) {
            tracklet.start = newFrameIndex;
            tracklet.boxes[0].is_key = true;
            tracklet.boxes[0].frame_index = newFrameIndex;
            return tracklet;
          }
          if (!isStart && !isGoingRight) {
            tracklet.end = newFrameIndex;
            tracklet.boxes[tracklet.boxes.length - 1].is_key = true;
            tracklet.boxes[tracklet.boxes.length - 1].frame_index = newFrameIndex;
            return tracklet;
          }
          return tracklet;
        }
        return tracklet;
      });
    }
    return object;
  });
};
