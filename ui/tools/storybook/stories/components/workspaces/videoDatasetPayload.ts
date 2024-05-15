export const videoDatasetItemPayload = {
  id: "id.jpg", // string
  datasetId: "datasetId", // string - could be inferred
  type: "video", // "video" | "image" | "3D"
  split: "demo", // not used
  features: {
    featureName: {
      name: "featureName", // string
      dtype: "str", // "str | "int" | "float"
      value: "printemps", // string
    },
    /// ...
  },
  views: {
    viewName: [
      {
        uri: ["path/to/asset"], // string
        features: {
          width: {
            name: "width",
            dtype: "int",
            value: 600,
          },
          height: {
            name: "height",
            dtype: "int",
            value: 338,
          },
        },
        id: "image",
        type: "image", // not used
        thumbnail: "path/to/thumbnail", // string
        frame_number: 1, // number - not used
        total_frames: 10, // number - not used
      },
    ],
  },
  objects: {
    objectId: {
      id: "objectId", // string
      datasetItemType: "video", // "video" | "image" | "3D" - maybe this could be inferred
      item_id: "item_id", // string
      view_id: "view_id", // string
      source_id: "source_id", // string
      review_state: undefined,
      features: {},
      track: [
        {
          start: 0, // number
          end: 10, // number
          keyBoxes: [
            {
              coords: [0, 0, 100, 100], // [number, number, number, number]
              format: "xywh",
              is_normalized: true, // boolean
              confidence: 1, // number
              frameIndex: 0, // number
            },
          ],
        },
      ],
      // SHOULD BE ADDED AT RUNTIME
      //  datasetItemType if not present
      //  displayedBox
      //  displayControl
      //  highlighted
    },
  },
};
