import type {
  DatasetInfo,
  DatasetItem,
  ImageDatasetItem,
  ItemView,
  Tracklet,
  VideoDatasetItem,
} from "@pixano/core/src";
import { datasetPreview, imgThumbnail } from "../../assets/base64image";
import fleurs from "../../../assets/fleurs.jpg";

// IMPORT ALL IMAGES
const gallery: string[] = Object.values(
  import.meta.glob("../../../assets/videos/mock/*.{png,jpg,jpeg,PNG,JPEG}", {
    eager: true,
    as: "url",
  }),
);

const fleursUrl = fleurs as string;

const mockImage: ItemView = {
  id: "image",
  type: "image",
  uri: fleursUrl.slice(1),
  thumbnail: imgThumbnail,
  frame_number: undefined,
  total_frames: undefined,
  features: {
    width: {
      name: "width",
      dtype: "int",
      value: 770,
    },
    height: {
      name: "height",
      dtype: "int",
      value: 513,
    },
  },
};

export const mockedImageDatasetItem: ImageDatasetItem = {
  type: "image",
  id: "fleurs.jpg",
  split: "demo",
  features: {
    label: {
      name: "label",
      dtype: "str",
      value: "printemps",
    },
    category_name: {
      name: "category_name",
      dtype: "str",
      value: "foo",
    },
  },
  views: {
    image: mockImage,
  },
  objects: {
    EZ4s6R0E_y: {
      datasetItemType: "image",
      id: "EZ4s6R0E_y",
      item_id: "fleurs.jpg",
      view_id: "image",
      source_id: "Ground Truth",
      review_state: undefined,
      bbox: {
        coords: [
          0.7411248087882996, 0.031893156468868256, 0.21801991760730743, 0.27492383122444153,
        ],
        format: "xywh",
        is_normalized: true,
        confidence: 1,
        displayControl: {
          hidden: false,
        },
      },
      mask: undefined,
      features: {
        category_name: {
          name: "category_name",
          dtype: "str",
          value: "Flower",
        },
        category: {
          name: "category",
          dtype: "str",
          value: "nature",
        },
        category_id: {
          name: "category_id",
          dtype: "int",
          value: 2,
        },
      },
      highlighted: "all",
      displayControl: {
        hidden: false,
      },
    },
    QfNTSmYHmg: {
      datasetItemType: "image",
      id: "QfNTSmYHmg",
      item_id: "fleurs.jpg",
      view_id: "image",
      source_id: "Ground Truth",
      review_state: undefined,
      bbox: {
        coords: [0.3974025845527649, 0.2007797211408615, 0.2805194854736328, 0.35672515630722046],
        format: "xywh",
        is_normalized: true,
        confidence: 0,
        displayControl: {
          hidden: false,
        },
      },
      mask: {
        size: [513, 770],
        counts: [
          157152, 6, 506, 10, 502, 15, 496, 21, 491, 25, 486, 31, 481, 36, 475, 41, 471, 46, 466,
          51, 460, 56, 456, 61, 450, 67, 445, 71, 440, 77, 435, 82, 430, 86, 425, 92, 420, 97, 414,
          102, 410, 107, 404, 113, 399, 117, 394, 123, 389, 128, 384, 132, 379, 138, 374, 143, 368,
          148, 364, 153, 358, 155, 357, 156, 356, 157, 354, 159, 353, 160, 351, 162, 350, 163, 348,
          165, 347, 166, 346, 167, 344, 169, 343, 169, 342, 171, 341, 172, 339, 174, 338, 175, 337,
          176, 335, 178, 334, 179, 332, 181, 331, 182, 331, 182, 331, 181, 332, 181, 332, 181, 332,
          181, 332, 181, 332, 181, 332, 181, 332, 181, 332, 181, 332, 181, 332, 181, 332, 180, 333,
          180, 333, 180, 333, 180, 333, 180, 333, 180, 333, 180, 333, 180, 333, 180, 333, 180, 333,
          180, 333, 179, 334, 179, 334, 179, 334, 179, 334, 179, 334, 179, 334, 179, 334, 179, 334,
          179, 334, 179, 334, 179, 334, 178, 335, 178, 335, 178, 335, 178, 335, 178, 335, 178, 335,
          178, 335, 178, 335, 178, 335, 178, 335, 178, 335, 177, 336, 177, 336, 177, 336, 177, 336,
          177, 336, 177, 336, 177, 336, 177, 336, 177, 336, 177, 336, 177, 336, 176, 337, 176, 337,
          176, 337, 176, 337, 176, 337, 176, 337, 176, 337, 176, 337, 176, 337, 176, 337, 176, 337,
          175, 338, 175, 338, 175, 338, 175, 338, 175, 338, 175, 338, 175, 338, 175, 338, 175, 338,
          175, 338, 174, 339, 174, 339, 174, 339, 174, 339, 174, 339, 174, 339, 174, 339, 174, 339,
          174, 339, 174, 339, 174, 339, 173, 340, 173, 340, 173, 340, 173, 340, 173, 340, 173, 340,
          173, 340, 173, 340, 173, 340, 173, 340, 173, 340, 172, 341, 172, 341, 172, 341, 172, 341,
          172, 341, 172, 341, 172, 341, 172, 341, 172, 341, 172, 341, 172, 341, 171, 342, 171, 342,
          171, 342, 171, 342, 171, 342, 171, 342, 171, 342, 171, 342, 171, 342, 171, 342, 171, 342,
          170, 343, 170, 343, 170, 343, 170, 343, 170, 343, 170, 343, 170, 343, 170, 343, 170, 343,
          170, 343, 170, 343, 169, 344, 169, 344, 169, 344, 169, 344, 169, 344, 169, 344, 169, 350,
          163, 356, 157, 362, 151, 369, 144, 375, 137, 382, 131, 388, 125, 394, 119, 400, 113, 406,
          107, 413, 100, 419, 94, 425, 88, 431, 82, 437, 76, 443, 69, 451, 62, 457, 56, 463, 50,
          469, 44, 475, 38, 481, 32, 487, 26, 494, 19, 500, 13, 506, 7, 127467,
        ],
        displayControl: {
          hidden: false,
        },
      },
      features: {
        category_name: {
          name: "category_name",
          dtype: "str",
          value: "Flower",
        },
        category: {
          name: "category",
          dtype: "str",
          value: "nature",
        },
        category_id: {
          name: "category_id",
          dtype: "int",
          value: 2,
        },
      },
      highlighted: "all",
      displayControl: {
        hidden: false,
      },
    },
    tJA83zBeSh: {
      datasetItemType: "image",
      id: "tJA83zBeSh",
      item_id: "fleurs.jpg",
      view_id: "image",
      source_id: "Ground Truth",
      review_state: undefined,
      bbox: {
        coords: [0.3233766257762909, 0.5808966755867004, 0.24415583908557892, 0.4035087823867798],
        format: "xywh",
        is_normalized: true,
        confidence: 0,
        displayControl: {
          hidden: false,
        },
      },
      mask: {
        size: [513, 770],
        counts: [
          128120, 29, 483, 57, 454, 61, 451, 64, 448, 67, 444, 70, 442, 73, 438, 77, 435, 80, 431,
          84, 428, 86, 426, 89, 422, 93, 419, 96, 415, 100, 412, 102, 408, 107, 404, 111, 399, 116,
          395, 119, 392, 123, 387, 127, 384, 130, 380, 133, 378, 136, 376, 138, 374, 140, 372, 141,
          371, 143, 369, 145, 367, 147, 366, 147, 365, 149, 363, 151, 361, 153, 359, 154, 358, 156,
          356, 158, 354, 160, 352, 161, 352, 162, 350, 164, 348, 166, 346, 167, 345, 169, 343, 171,
          340, 174, 338, 175, 337, 177, 335, 179, 333, 181, 330, 183, 329, 185, 327, 187, 325, 189,
          323, 190, 321, 193, 319, 194, 318, 195, 317, 196, 316, 197, 316, 197, 316, 197, 316, 198,
          315, 198, 314, 199, 314, 199, 314, 199, 314, 199, 314, 199, 314, 199, 313, 201, 312, 201,
          312, 201, 312, 201, 312, 201, 311, 202, 311, 202, 311, 203, 310, 203, 310, 203, 310, 203,
          309, 204, 309, 204, 309, 204, 309, 204, 309, 205, 307, 206, 307, 206, 307, 206, 307, 206,
          307, 206, 307, 206, 307, 207, 306, 207, 306, 207, 306, 207, 306, 207, 306, 207, 306, 207,
          306, 207, 306, 207, 306, 207, 306, 206, 307, 206, 307, 206, 307, 205, 308, 205, 308, 204,
          309, 204, 309, 204, 309, 203, 310, 203, 310, 202, 311, 202, 311, 202, 311, 201, 312, 201,
          312, 200, 313, 200, 313, 200, 313, 199, 314, 199, 314, 198, 315, 198, 315, 197, 316, 197,
          316, 197, 316, 196, 317, 196, 317, 195, 318, 195, 318, 195, 318, 194, 319, 194, 320, 192,
          321, 191, 323, 189, 325, 188, 325, 187, 327, 185, 328, 184, 330, 182, 332, 180, 333, 179,
          335, 177, 337, 175, 338, 174, 340, 173, 352, 160, 366, 146, 368, 144, 370, 142, 372, 140,
          375, 137, 377, 135, 379, 133, 381, 132, 382, 130, 385, 127, 387, 125, 389, 123, 391, 121,
          393, 119, 396, 116, 398, 114, 400, 111, 403, 109, 406, 105, 409, 103, 411, 100, 414, 98,
          416, 95, 420, 92, 422, 89, 426, 86, 429, 82, 433, 79, 436, 75, 440, 72, 443, 68, 447, 65,
          450, 61, 454, 58, 457, 54, 461, 51, 464, 47, 468, 44, 170911,
        ],
        displayControl: {
          hidden: false,
        },
      },
      features: {
        category_name: {
          name: "category_name",
          dtype: "str",
          value: "Flower",
        },
        category: {
          name: "category",
          dtype: "str",
          value: "nature",
        },
        category_id: {
          name: "category_id",
          dtype: "int",
          value: 2,
        },
      },
      highlighted: "all",
      displayControl: {
        hidden: false,
      },
    },
  },
  embeddings: {},
};

export const mockedCurrentDataset: DatasetInfo = {
  id: "QSctnfM7Ek68M7w6tyNhHf",
  name: "demo_agriculture",
  description: "LIST Days - agriculture",
  estimated_size: "681.31 KB",
  num_elements: 25,
  splits: ["demo"],
  tables: {
    main: [
      {
        name: "db",
        fields: {
          id: "str",
          views: "[str]",
          split: "str",
          label: "str",
          category_name: "str",
        },
        source: "Pre-annotation",
        type: undefined,
      },
    ],
    media: [
      {
        name: "image",
        fields: {
          id: "str",
          image: "image",
        },
        source: undefined,
        type: undefined,
      },
    ],
    embeddings: [
      {
        name: "emb_230602_141614_SAM_ViT_H",
        fields: {
          id: "str",
          image: "bytes",
        },
        source: "SAM_ViT_H",
        type: "segment",
      },
      {
        name: "emb_231110_110736_CLIP",
        fields: {
          id: "str",
          image: "vector(512)",
        },
        source: "CLIP",
        type: "search",
      },
      {
        name: "emb_231208_153758_SAM_ViT_B",
        fields: {
          id: "str",
          image: "bytes",
        },
        source: "SAM_ViT_B",
        type: "segment",
      },
    ],
    objects: [
      {
        name: "obj_231208_163253_YOLOv5s",
        fields: {
          id: "str",
          item_id: "str",
          view_id: "str",
          bbox: "bbox",
          mask: "compressedrle",
          category_id: "int",
          category_name: "str",
          review_state: "str",
        },
        source: "Pre-annotation",
        type: undefined,
      },
      {
        name: "obj_231208_163619_FasterRCNN_R50",
        fields: {
          id: "str",
          item_id: "str",
          view_id: "str",
          bbox: "bbox",
          mask: "compressedrle",
          category_id: "int",
          category_name: "str",
          review_state: "str",
        },
        source: "Pre-annotation",
        type: undefined,
      },
      {
        name: "obj_231208_163854_FasterRCNN_R50",
        fields: {
          id: "str",
          item_id: "str",
          view_id: "str",
          bbox: "bbox",
          mask: "compressedrle",
          category_id: "int",
          category_name: "str",
        },
        source: "FasterRCNN_R50",
        type: undefined,
      },
      {
        name: "obj_annotator",
        fields: {
          id: "str",
          item_id: "str",
          view_id: "str",
          bbox: "bbox",
          mask: "compressedrle",
          category_id: "int",
          category_name: "str",
        },
        source: "Pixano Annotator",
        type: undefined,
      },
      {
        name: "objects",
        fields: {
          id: "str",
          item_id: "str",
          view_id: "str",
          bbox: "bbox",
          mask: "compressedrle",
          category_name: "str",
          category: "str",
          review_state: "str",
          category_id: "int",
        },
        source: "Ground Truth",
        type: undefined,
      },
    ],
  },
  categories: [],
  features_values: {
    scene: {
      label: ["arbre", "oranges", "poire", "None", "abeille", "printemps"],
      category_name: ["foo", "None"],
    },
    objects: {
      category_id: [],
      category_name: [
        "toilet",
        "chair",
        "oranges",
        "donut",
        "bar",
        "apple",
        "dining table",
        "pizza",
        "refrigerator",
        "None",
        "potted plant",
        "orange",
        "bird",
        "cake",
        "sheep",
        "salade",
        "broccoli",
        "olive",
        "sandwich",
        "oooo",
        "banano",
        "carrot",
        "bowl",
        "banana",
        "carrotes",
        "foo",
        "choubidou",
        "bottle",
      ],
      category: ["vzfe", "front", "None", "seed", "foo", "bar"],
    },
  },
  preview: datasetPreview,
  stats: [],
  page: {
    items: [
      {
        id: "fleurs.jpg",
        type: "image",
        split: "demo",
        features: {
          label: {
            name: "label",
            dtype: "str",
            value: "printemps",
          },
          category_name: {
            name: "category_name",
            dtype: "str",
            value: "foo",
          },
        },
        views: {
          image: {
            id: "image",
            type: "image",
            uri: "data/demo_agriculture_broken/media/image/demo/fleurs.jpg",
            thumbnail: imgThumbnail,
            frame_number: undefined,
            total_frames: undefined,
            features: {},
          },
        },
        objects: {},
        embeddings: {},
      },
    ],
    total: 25,
  },
  isErrored: false,
};

export const mockHandleSaveItem = (item: DatasetItem) => {
  console.log({ item });
  return Promise.resolve();
};

const displayedBox = {
  coords: [0.5362540535588254, 0.1909159114200253, 0.09993766916635072, 0.18671048750633337],
  format: "xywh",
  is_normalized: true,
  confidence: 1,
  frameIndex: 1,
};

const track: Tracklet[] = [
  {
    start: 0,
    end: 73,
    keyBoxes: [
      {
        coords: [0.5362540535588254, 0.1909159114200253, 0.09993766916635072, 0.18671048750633337],
        format: "xywh",
        is_normalized: true,
        confidence: 1,
        frameIndex: 0,
      },
      {
        coords: [0.5914342337390056, 0.2693339921343171, 0.09993766916635072, 0.18671048750633337],
        format: "xywh",
        is_normalized: true,
        confidence: 1,
        frameIndex: 73,
      },
    ],
  },
];

export const mockedVideoDatasetItem: VideoDatasetItem = {
  id: "fleurs.jpg",
  type: "video",
  split: "demo",
  features: {
    label: {
      name: "label",
      dtype: "str",
      value: "printemps",
    },
    category_name: {
      name: "category_name",
      dtype: "str",
      value: "foo",
    },
  },
  views: {
    image: gallery.map((image) => ({
      ...mockImage,
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
      uri: image,
    })),
  },
  objects: {
    EZ4s6R0E_y: {
      id: "EZ4s6R0E_y",
      datasetItemType: "video",
      track,
      item_id: "fleurs.jpg",
      view_id: "image",
      source_id: "Ground Truth",
      review_state: undefined,
      displayedBox,
      features: {
        category_name: {
          name: "category_name",
          dtype: "str",
          value: "Flower",
        },
        category: {
          name: "category",
          dtype: "str",
          value: "nature",
        },
        category_id: {
          name: "category_id",
          dtype: "int",
          value: 2,
        },
      },
      highlighted: "all",
      displayControl: {
        hidden: false,
      },
    },
  },
  embeddings: {},
};
