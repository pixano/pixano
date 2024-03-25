import type {
  EditShape,
  ItemObject,
  KeyVideoFrame,
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
  let endIndex = currentTracklet.keyFrames.findIndex((frame) => frame.frameIndex > imageIndex);
  endIndex = endIndex < 0 ? currentTracklet.keyFrames.length - 1 : endIndex;
  const start = currentTracklet.keyFrames[endIndex - 1] || currentTracklet.keyFrames[0];
  const end = currentTracklet.keyFrames[endIndex];
  if (start.bbox && end.bbox) {
    const [startX, startY, startWidth, startHeight] = start.bbox.coords;
    const [endX, endY, endWidth, endHeight] = end.bbox.coords;
    const xInterpolation = (endX - startX) / (end.frameIndex - start?.frameIndex);
    const yInterpolation = (endY - startY) / (end.frameIndex - start?.frameIndex);
    const widthInterpolation = (endWidth - startWidth) / (end.frameIndex - start?.frameIndex);
    const heightInterpolation = (endHeight - startHeight) / (end.frameIndex - start?.frameIndex);
    const x = startX + xInterpolation * (imageIndex - start.frameIndex);
    const y = startY + yInterpolation * (imageIndex - start.frameIndex);
    const width = startWidth + widthInterpolation * (imageIndex - start.frameIndex);
    const height = startHeight + heightInterpolation * (imageIndex - start.frameIndex);
    return [x, y, width, height];
  }
  return null;
};

export const deleteKeyBoxFromTracklet = (
  objects: ItemObject[],
  frame: KeyVideoFrame,
  objectId: ItemObject["id"],
) =>
  objects.map((object) => {
    if (objectId === object.id && object.datasetItemType === "video") {
      object.track = object.track
        .map((tracklet) => {
          if (tracklet.start <= frame.frameIndex && tracklet.end >= frame.frameIndex) {
            tracklet.keyFrames = tracklet.keyFrames.filter(
              (keyFrame) => keyFrame.frameIndex !== keyFrame.frameIndex,
            );
            tracklet.start = tracklet.keyFrames[0]?.frameIndex;
            tracklet.end = tracklet.keyFrames[tracklet.keyFrames.length - 1]?.frameIndex;
          }
          return tracklet;
        })
        .filter((tracklet) => tracklet.keyFrames.length > 1);
    }
    return object;
  });

export const editKeyBoxInTracklet = (
  objects: ItemObject[],
  keyFrameBeingEdited: KeyVideoFrame,
  shape: EditShape,
) =>
  objects.map((object) => {
    if (
      shape.type === "rectangle" &&
      object.id === shape.shapeId &&
      object.datasetItemType === "video"
    ) {
      object.track = object.track.map((tracklet) => {
        if (
          tracklet.start <= keyFrameBeingEdited.frameIndex &&
          tracklet.end >= keyFrameBeingEdited.frameIndex
        ) {
          tracklet.keyFrames = tracklet.keyFrames.map((keyFrame) => {
            if (keyFrame.frameIndex === keyFrameBeingEdited.frameIndex) {
              // keyFrame.coords = shape.coords; TODO_MASK
              // object.displayedBox.coords = shape.coords;
              return keyFrame;
            }
            return keyFrame;
          });
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
  keyFrame: KeyVideoFrame,
) => {
  let nextTrackletStart = track.find((tracklet) => tracklet.start > frameIndex)?.start;
  nextTrackletStart = nextTrackletStart ? nextTrackletStart - 1 : lastFrameIndex;
  return {
    start: frameIndex,
    end: nextTrackletStart,
    keyFrames: [
      {
        ...keyFrame,
        frameIndex,
      },
      {
        ...keyFrame,
        frameIndex: nextTrackletStart,
      },
    ],
  } as Tracklet;
};

const addKeyBoxToTracklet = (track: Tracklet[], tracklet: Tracklet, keyFrame: KeyVideoFrame) =>
  track.map((trackItem) => {
    if (trackItem.start === tracklet.start && trackItem.end === tracklet.end) {
      trackItem.keyFrames.push(keyFrame);
      trackItem.keyFrames.sort((a, b) => a.frameIndex - b.frameIndex);
      trackItem.start = trackItem.keyFrames[0].frameIndex;
      trackItem.end = trackItem.keyFrames[trackItem.keyFrames.length - 1].frameIndex;
    }
    return trackItem;
  });

export const addKeyBox = (
  objects: ItemObject[],
  keyFrame: KeyVideoFrame,
  objectId: string,
  frameIndex: number,
  lastFrameIndex: number,
) => {
  return objects.map((object) => {
    if (objectId !== object.id) return object;
    if (object.datasetItemType !== "video") return object;
    const currentTracklet = object.track.find(
      (tracklet) => tracklet.start <= frameIndex && tracklet.end >= frameIndex,
    );
    if (!currentTracklet) {
      const newTracklet = createNewTracklet(object.track, frameIndex, lastFrameIndex, keyFrame);
      object.track.push(newTracklet);
    } else {
      object.track = addKeyBoxToTracklet(object.track, currentTracklet, keyFrame);
    }
    object.track.sort((a, b) => a.start - b.start);
    return object;
  });
};

export const findNeighbors = (
  track: Tracklet[],
  currentTracklet: Tracklet,
  frameIndex: VideoItemBBox["frameIndex"],
  lastFrameIndex: number,
): [number, number] => {
  const currentIntervalIndex = track.findIndex(
    (int) => int.start === currentTracklet.start && int.end === currentTracklet.end,
  );
  if (currentIntervalIndex < 0) return [0, 0];
  const prevTracklet = track[currentIntervalIndex - 1];
  let prevNeighbor = currentTracklet.keyFrames.find(
    (box) => box.frameIndex < frameIndex,
  )?.frameIndex;
  if (!prevNeighbor && prevTracklet) {
    prevNeighbor = prevTracklet.keyFrames[prevTracklet.keyFrames.length - 1]?.frameIndex;
  }
  prevNeighbor = prevNeighbor || 0;

  let nextNeighbor = currentTracklet.keyFrames.find(
    (box) => box.frameIndex > frameIndex,
  )?.frameIndex;
  const nextTracklet = track[currentIntervalIndex + 1];
  if (!nextNeighbor && nextTracklet) {
    nextNeighbor = nextTracklet.keyFrames[0]?.frameIndex;
  }
  nextNeighbor = nextNeighbor || lastFrameIndex + 1;

  return [prevNeighbor, nextNeighbor];
};

const filterKeyFrames = (
  keyFrames: KeyVideoFrame[],
  newFrame: KeyVideoFrame,
  shouldBeFiltered: (index: KeyVideoFrame["frameIndex"]) => boolean,
) =>
  keyFrames.reduce(
    (acc, frame, i) => {
      if (i === 0) {
        acc.push(newFrame);
      }
      if (shouldBeFiltered(frame.frameIndex)) {
        acc.push(frame);
      }
      return acc.sort((a, b) => a.frameIndex - b.frameIndex);
    },
    [] as Tracklet["keyFrames"],
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
    keyFrames: filterKeyFrames(
      tracklet.keyFrames,
      { ...object.displayedFrame, frameIndex: rightClickFrameIndex },
      (index) => index < rightClickFrameIndex,
    ),
  };
  const endTracklet: Tracklet = {
    start: rightClickFrameIndex + 1,
    end: tracklet.end,
    keyFrames: filterKeyFrames(
      tracklet.keyFrames,
      { ...object.displayedFrame, frameIndex: rightClickFrameIndex + 1 },
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
