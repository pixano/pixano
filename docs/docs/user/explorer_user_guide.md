<div align="center">
<picture>
    <img src="https://raw.githubusercontent.com/pixano/pixano/main/images/pixano_logo.png" alt="Pixano" height="100"/>
</picture>
<br/>

**Data-centric AI building blocks for computer vision applications**

***Under active development, subject to API change***

</div>

# Pixano Explorer : User Guide


## Pixano Explorer main screen : datasets browser

From the Explorer homepage, you will be greeted with a list of all the Pixano format datasets found in the directory you provided.

Each dataset show the dataset name, the number of elements it contains, and six samples images drawn from the datasets.

You can put mouse pointer over the dataset name to see the complete name (full name may have been truncated if too long) and the dataset description.

Click on any of them to open the dataset explore screen.


## Dataset explore screen

On this screen's header, you will see the dataset name.
You can click on "Pixano Explorer" or "Back to library" to go back to datasets browser screen.

On the left side, available statistics on this dataset are displayed.
Put your mouse over the graph to get some detailled information, depending of displayed graph.
Some of the graphs may be scrollable if required.

*(coming soon: filtering from statistics graphs)*

On the right side, are displayed the elements in a scrollable panel, by pages of up to 100 elements.
"PREV" and "NEXT" buttons, at the bottom, allows to navigate in theses elements pages.

Each element display at least it's ID, an image thumbnail, and the split from which it comes.
There can be several image thumbnails if you have a multiview dataset, and other element level meta data if they're been made available in the dataset, such as image width and height, etc.

*(coming soon: filtering by meta data)*

Click on any of the element to open the detailed element screen


## Detailed Element screen

On the top right of the screen, a red cross allows to go back to previous screen. Or you can hit the "Echap" key.

The selected image is displayed, or several images arranged in a grid, one by view, in case of a multi-view dataset.
You can grab and move the image (each image independantly in case of multi view), and zoom in and out with the mouse wheel over the image.
Double-click on an image to move it to top in case of multi-view dataset.

Annotations, in form of segmentations mask and bounding boxes, are displayed.
Each object category is given a color.

Bounding box display category, and confidence for inferences, on the top left of the box.


on the right, a panel show some information and display controls

"DATA" section give some information on this element.
Currently, only ID is displayed

"TOOLS" section allows to filter showed elements

"Show all items" checkbox hide or show all annotations.

"Show boxes" checkbox hide or show all bounding boxes

"Mask opacity" slider allows to adjust segmentations masks opacity

"Minimum confidence" slider allows to adjust the threshold for confidence. Inference are displayed only if their confidence is greater or equal than the given threshold.

"Categories" display each category for this element, and the number of element for each category if more than one.
You can hide or show a specific category by clicking it. Hidden categories are greyed out.

*(coming soon: show/hide by ground truth / inference)*

*(coming soon: color by ground truth / inference)*

"Views" section is diplayed only with a multi-view dataset. 
It list available views, *and still under development...*

*(coming soon: show/hide specific view(s))*


*(coming soon: new annotations types such as keypoints, ...)*
