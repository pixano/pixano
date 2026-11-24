The `tracking` job of `pixano-worker` can propose boxes: its `output` parameter asks for the
object's mask on each frame (the default, what it proposed until now), the box around that mask,
or both, pending review. A frame on which a person drew or accepted the object's box gets no box
from the model, and tracking again from a later frame replaces only what came after it, of what
the job was asked for.
