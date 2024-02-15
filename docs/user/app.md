# Using the Pixano app

## Home page

![Pixano home page](../assets/user/app_home.png)

From the app home page, you will be greeted with a list of all the Pixano format datasets found in the directory you provided.

## Dataset page

![Pixano dataset page - top](../assets/user/app_dataset_1.png)

On the dataset page, you will see a list of all the items it contains, organized in pages.

![Pixano dataset page - bottom](../assets/user/app_dataset_2.png)

When scrolling to the bottom of the page, you will see navigation buttons to move through the pages of your dataset.

## Dashboard page

![Pixano dataset dashboard](../assets/user/app_dashboard.png)

From the dataset page, you can go to the dashboard page, which contains more information about your datasets and also displays all the computed statistics available.

## Item page

When opening an item, the item media will be displayed in the center on the screen (in case of multi-view datasets, the images will be tiled).

On the left, a toolbar is available. On the right, two panels will display information on the item objects and scene.

### Scene panel

![Pixano item view - scene](../assets/user/exploration_scene.png)

The scene panel will display all the scene features, like the item label, or any other feature created when importing your dataset, as well as metadata information on all the images in the item.

You can edit the scene features and then click the save changes button to write them to the dataset.

### Object panel

![Pixano item view - objects](../assets/user/exploration_objects.png)

The objects panel will display all the item objects.

On the top, you will see the ground truth objects, which are the objects you imported with your dataset, and objects you create within the app. On the bottom, a dropdown menu will let you go through all the objects created by models like the ones available in Pixano Inference.

You have visibility toggles for objects and object group, and when hovering on an object, you will have access to an edit tool and a delete tool.

If you have used an inference model for pre-annotating the dataset, a "Pre-annotation" toggle will also appear above the ground truth section. Activating this toggle will let you go through each object and accept or reject them individually. You will also be able to edit the object features before accepting it.

![Pixano item view - object edition](../assets/user/exploration_object_edition.png)

The edit tool will allow you to edit the object features, for example its category and category ID, and also allow you to edit the object bounding box and mask on the image.

To create new objects, you have multiple tools at your disposal on the left toolbar.

### Toolbar

#### Pan tool

With the pan tool selected, you can move the image around. This is especially useful for multi-view datasets for organizing multiple images.

Moving the images is still possible while any other tools is selected by using your mouse middle click. You can also zoom in and out of an image with the mouse wheel, and double click an image to bring it in front of the others.

#### Bounding box tool

![Pixano tools - bounding box](../assets/user/annotation_bounding_box.png)

With the bounding box tool, you can create a bounding box object by click and dragging a rectangle over the image. Once you are done with your selection, you will be prompted to enter values for your object features depending on your dataset (in this case category_id and category), and to confirm the object.

Then, click save changes in the object panels to save the created object to your dataset.

#### Polygon tool

![Pixano tools - polygon](../assets/user/annotation_polygon.png)

With the polygon tool, you can create a segmentation mask manually by adding points with the granularity of your choice.

Once you save this mask, a matching bounding box will automatically be created.

#### Smart segmentation tool

With Pixano, you can segment with smart segmentation tool like SAM (Segment Anything Model). Please follow our documentation on how to precompute the embeddings required by SAM and export its ONNX model to be able to use it.

![Pixano tools - SAM points](../assets/user/annotation_sam_points.png)

With the positive and negative points, you can inform SAM on which part of the image you are trying to segment, and SAM will generate the mask for you.

![Pixano tools - SAM rectangle](../assets/user/annotation_sam_rectangle.png)

When relevant, you can also use the rectangle tool to select the thing you want SAM to segment.

When saving the mask created by SAM, like with the polygon tool, a matching bounding box will automatically be created.
