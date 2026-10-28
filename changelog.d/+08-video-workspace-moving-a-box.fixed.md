Video workspace: moving a box after clicking its pencil in the inspector no
longer freezes frame navigation. An interpolated box or keypoints shape keeps
the same id instead of getting a new one each time it is shown, and "Add a
point" puts the new keyframe on the current frame. During a tracking session,
where any box edit becomes a keyframe of the track being drawn, the box pencils
are disabled.
