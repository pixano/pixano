**Detection in the image workspace.** A toolbar button opens a detection panel: pick a detection
model served by pixano-inference and a class, and **Detect** proposes its objects. With a model
that takes examples, such as SAM 3, **Find more like these** looks for objects like the boxes of
that class already on the image, sends the proposals rejected earlier in the session as counter-examples, and never proposes them
again. Each
proposal is a new object with the class as its label and a box with the model's score; boxes over
existing ones are left out, and the rest arrive pending review.
