<div align="center">
<picture>
    <img src="https://raw.githubusercontent.com/pixano/pixano/main/images/pixano_logo.png" alt="Pixano" height="100"/>
</picture>
<br/>

**Data-centric AI building blocks for computer vision applications**

***Under active development, subject to API change***

</div>

# Pixano Annotator : User Guide


## Pixano Annotator main screen : datasets browser

From the Annotator homepage, you will be greeted with a list of all the Pixano format datasets found in the directory you provided.

Each dataset show the dataset name, the number of elements it contains, and six samples images drawn from the datasets.

You can put mouse pointer over the dataset name to see the complete name (full name may have been truncated if too long) and the dataset description.

Click on any of them to open the annotation screen. It opens on the first elements of the dataset.


## Annotation screen

On the header's screen, a cross on the right allows to go back to previous screen. Or you can click on "Pixano Annotator"
The dataset name and element ID is displayed here. 

A "Save" icon allows to save your changes. It is highlighted if there is changes to save. 
If you close this screen, or change the current element with some unsaved changes, you will be warned that it would discard your unsaved changes. You can choose "OK" to discard them.

On the left is the "Tools" panel.

The image (or several in case of multiview dataset), annotations, and current inputs and are diplayed in the center.

On the right, a panel with two tabs, "LABELS" and "DATASET" show annotations with some control, and list of elements, respectively.

### Tools

On the left are displayed the available tools:
- the "Pan" tool. It allows to move image(s).
- the "Point" tool. It allows to draw input points to annotate. A panel open to choose '+' (green) or '-' (red) when you put pointer over this tool.
- the "Rectangle" tool. It allows to draw an input bounding box to annotate.

*(coming soon: new tools such as "Paint", ...)*

### Image views

The selected image is displayed, or several images arranged in a grid, one by view, in case of a multi-view dataset.

With the "Pan" tool, or you with middle-click, can grab and move the image (each image independantly in case of multi view), and zoom in and out with the mouse wheel over the image.

Double-click on an image to move it to top in case of multi-view dataset.

Annotations, in form of segmentations mask, are displayed.
Each object category is given a color.

On the top of the image, when you have an input Tool selected, a panel is displayed that allow to choose a category.

### LABELS tab

"LABELS" tab display the list of annotation, grouped by view (if revelent), and by categories
Each group can be expanded or closed by clicking on it, showed or hidden by clicking on the "eye" icon, as well as each element inside a category group.
The element is represented by it's ID. On hover, you can see a generated label.

(*coming soon: custom meta data per element*)

The "trash" icon allows to delete an annotation.

### DATASET tab

"DATASET" tab allows to navigate through the dataset.
Each element of the dataset is displayed, the image (or one view by image with multiview dataset) and the element's ID.
This list will be automatically appended by scrolling down.

Click on any element to change current displayed element. If you have unsaved changes, you will be asked if you want to discard theses changes ("OK") or stay on the current element ("Cancel").

*(coming soon: new annotations types such as keypoints, ...)*

## Annotate

Currently the inputs are "Points" ('+' and '-'), and "Rectangle". Depending on the model used, it will allow to make prediction.

Points and Rectangle inputs can be used together.

Pixano annotator make a new prediction (displayed in green) for every new input. 

The category selection panel displayed whith an input tool allows to enter a category name, or chose one in the drop-down list. All existing categories in this element are listed, plus predefined categories if provided. Manually entered categories are also kept.
The "check" button validate the current prediction with the current category name. Or you can hit "Enter" key to validate.

"Echap" key discards all inputs and current prediction.

### Points input

With the "Point" input tool, click anywhere on a image to put an input point. As long as your pointer is on the point, it will be highlighted. You can grab it and move it then. New prediction will be continuously computed (whenever you stop moving, or move slowly enough, or release the point). 
Hit the "Suppr" key over an highlighted point to delete it. It makes a new prediction with remaining inputs if any.

With this tool selected, the category selection panel also allows to select between '+' and '-' point. The currently selected tool is highlighted.

### Rectangle input

With the "Rectangle" input tool, click and drag to draw a rectangle box as input. It's displayed as a white dotted rectangle on screen.
There can be only one input rectangle at a time, so drawing a new one will discard the previous one.

