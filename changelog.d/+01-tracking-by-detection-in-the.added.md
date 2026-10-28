**Tracking by detection in the video workspace.** A toolbar action runs a
prompt-free tracking model served by pixano-inference (YOLO + ByteTrack) over
the video — optionally from the current frame, restricted to classes, above a
detection threshold — previews every proposed track on the canvas and the
timeline, and lets you keep or discard tracks before accepting: one object per
track (its class in the dataset's label field when it has one), one tracklet
per run, one box every N frames with the model's score as confidence. A run
covers at most 600 frames.
