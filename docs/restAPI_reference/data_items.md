# Dataset Items

### Video dataset Item

```
type videoDatasetItemPayload = {
  id: string;
  datasetId: string;
  type: "video" | "image" | "3D";
  split: string; // not used in FRONTEND
  features: [
    {
        name: "string";
        dtype: "str | "int" | "float";
        value: string
    }
  ]
  },
  views: {
    viewName: [
      {
        uri: string;
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
        id: string;
        type: string; // not used
        thumbnail: string
        frame_number: number; not used
        total_frames: number; not used
      },
    ],
  },
  objects: {
    objectId: {
      id: string;
      datasetItemType: "video" | "image" | "3D";
      item_id: string;
      view_id: string;
      source_id: string;
      review_state: undefined;
      features: {},
      track: [
        {
          start: number;
          end: number;
          keyBoxes: [
            {
              coords: [number, number, number, number];
              format: string;
              is_normalized: boolean;
              confidence: number;
              frame_index: number;
              is_key: boolean;
            },
          ],
        },
      ],
      thumbnails: {
        [viewId]: {
          uri: string;
          coords: [x, y, width, height];
          imageDimensions: {
            width: number;
            height: number
          }

        }
      }
    },
  },
```

Please note that values used in frontend only should not be added to the payload:

```
displayedBox
displayControl
highlighted
```
