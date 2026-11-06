`pixano-worker` tracks objects through videos: the `tracking` job follows an object a person
annotated on a frame — its box or its mask — to the video's end, with a tracking model the
inference serves, and proposes its mask on each later frame, pending review, with a tracklet
spanning them. Submitted from the Jobs panel, it follows every object a person annotated on a
frame of a video. A track from a later frame corrects a drift: a box drawn there prompts it, and
what an earlier track proposed before that frame stays.
