import { readFile } from "fs/promises"
import fs from "fs"
import { describe, test, expect } from 'vitest';
import { SAM } from "../src/Sam";
import { InteractiveImageSegmenterInput, LabeledClick } from "../src/interactive_image_segmentation";
import * as ort from "onnxruntime-node";
import * as npyjs from "../src/npy";


// Target values are generated from the sam python notebook with the following parameters
const W: number = 768;
const H: number = 576;

describe("SAM", () => {
    test("Init model", async () => {
        const modelWeights = await readFile(`${__dirname}/sam_onnx_quantized_vit_h.onnx`);
        const sam = new SAM()
        await sam.init(modelWeights);

        const expectedInputs = [
            'image_embeddings',
            'point_coords',
            'point_labels',
            'mask_input',
            'has_mask_input',
            'orig_im_size'
        ];

        for (const input of expectedInputs) {
            expect(sam.inputNames()).toContain(input);
        }

        const expectedOutputs = [
            'masks', 'iou_predictions', 'low_res_masks'
        ]

        for (const output of expectedOutputs) {
            expect(sam.outputNames()).toContain(output);
        }
    })

    test("Preprocess clicks", () => {
        const expectedPointsCoords = [
            388., 133.33333, 653.3333, 222.66667, 836., 238.66667, 0., 0.
        ]

        const expectedLabels = [1., 1., 0., -1.]

        const inputClicks = [
            { x: 291, y: 100, label: 1 },
            { x: 490, y: 167, label: 1 },
            { x: 627, y: 179, label: 0 }
        ]

        const sam = new SAM();
        const samPoints = sam.preProcessClicks(inputClicks, W, H)

        for (let i = 0; i < expectedPointsCoords.length; ++i) {
            expect(samPoints.points.data[i]).toBeCloseTo(expectedPointsCoords[i])
            expect(samPoints.labels.data[i]).toBe(expectedLabels[i])
        }
    })

    test("segmentImage from clicks", async () => {
        const modelWeights = await readFile(`${__dirname}/sam_onnx_quantized_vit_h.onnx`);
        const sam = new SAM()
        await sam.init(modelWeights);

        Object.defineProperty(Image.prototype, 'naturalHeight', { get: () => H });
        Object.defineProperty(Image.prototype, 'naturalWidth', { get: () => W });

        // load embedding
        const rawData = fs.readFileSync(`${__dirname}/image-0001.npy`);
        const embeddingArr = npyjs.parse(rawData)
        const embedding = new ort.Tensor("float32", embeddingArr.data, embeddingArr.shape);

        const expectedEmbedding = [-0.18764384, -0.2177867, -0.19377214, -0.19490339, -0.2003522,
        -0.16835165, -0.15158224, -0.1445655, -0.08978239, -0.1408087]

        for (let i = 0; i < 10; ++i) {
            expect(embedding.data[i]).toBeCloseTo(expectedEmbedding[i])
        }
        console.log(embedding.data.length)

        // input clicks from users
        // const inputClicks: Array<LabeledClick> = [
        //     { x: 287, y: 95, label: 1 },
        //     { x: 503, y: 174, label: 1 },
        //     { x: 626, y: 155, label: 0 }
        // ]
        const inputClicks = [
            { x: 284, y: 104, label: 1 },
        ]

        const samInput = {
            image: new Image(),
            embedding: embedding,
            points: inputClicks
        }

        const result = await sam.segmentImage(samInput)

        console.log(result)
        expect(result.masks?.data.length).toBe(442368)

        // 10 first value of the masks
        // const expectedMaskValues = [-10.188387, -10.282515, -10.690401, -11.192415, -11.541126,
        // -11.378819, -11.06321, -10.858041, -11.021009, -11.294418]
        const expectedMaskValues = [-16.090378, -16.248798, -16.935291, -30.698093, -30.733797,
            -30.742039]

        for (let i = 0; i < 10; ++i) {
            expect(result.masks?.data[i]).toBeCloseTo(expectedMaskValues[i], 1)
        }
    })
})