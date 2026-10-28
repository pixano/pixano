The legacy app finds the bounds of a mask whose first pixel is painted, as a
SAM mask can be: pycocotools then starts its counts with an empty run. Such a
mask got inverted bounds, and a wrong box around it.
