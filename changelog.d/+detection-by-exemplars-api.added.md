**Detection by exemplars in the API.** `POST /inference/detection` reads the image of a dataset
view (`dataset_id` + `view_id`) as an alternative to `image`, and accepts `exemplar_boxes` (and
`negative_exemplar_boxes`): boxes around a few instances, for a model that finds more like them,
such as SAM 3. A model that does not declare it reads exemplars is refused with a 400 rather than
silently running a detection without them, as is a model that does not detect.
