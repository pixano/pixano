The inference integration depends on `pixano-inference >= 0.7.1, < 0.8.0`, which
ships the client and the wire schemas itself; `pixano-inference-client` is no
longer used. `/inference/models/list` carries each model's `interface` (how it is
called: prompts, prompt-free, classes, thresholds, outputs) as the server publishes it. Video tracking results are grouped by frame:
`/inference/video_mask_generation` and its job status return
`data.frames[].objects[]` (`track_id`, `box`, `score`, `class_name`, `mask`)
instead of the parallel `objects_ids` / `frame_indexes` / `masks` lists, so the
boxes, scores and classes of a tracking-by-detection model come through. A
tracking request no longer needs `objects_ids`; `classes` and `box_threshold`
select what a prompt-free model follows. A job result Pixano cannot read is a
502 instead of an empty result.
