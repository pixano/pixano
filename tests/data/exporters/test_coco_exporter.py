# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

import json
import tempfile
import unittest
from pathlib import Path

from pixano.data import COCOExporter, COCOImporter


class COCOExporterTestCase(unittest.TestCase):
    """COCOExporter test case"""

    def test_export_dataset(self):
        """Test COCOExporter export_dataset method"""

        with tempfile.TemporaryDirectory() as temp_dir:
            # Set import and export directory
            import_dir = Path(temp_dir) / "coco"
            export_dir = Path(temp_dir) / "coco_exported"

            # Create COCO dataset
            input_dirs = {
                "image": Path("tests/assets/coco_dataset/image"),
                "objects": Path("tests/assets/coco_dataset"),
            }
            importer = COCOImporter(
                name="COCO",
                description="COCO dataset",
                input_dirs=input_dirs,
                splits=["val"],
            )
            importer.import_dataset(import_dir)

            # Export dataset
            exporter = COCOExporter(input_dir=import_dir)
            exporter.export_dataset(export_dir)

            # Annotations files
            imported_ann_fp = Path("tests/assets/coco_dataset") / "instances_val.json"
            exported_ann_fp = (
                export_dir / "annotations [Ground Truth]" / "instances_val.json"
            )

            # Check that exported annotation JSON file exists
            self.assertTrue(exported_ann_fp.exists())

            with open(imported_ann_fp, encoding="utf-8") as imported_ann_file:
                with open(exported_ann_fp, encoding="utf-8") as exported_ann_file:
                    imported_ann = json.load(imported_ann_file)
                    exported_ann = json.load(exported_ann_file)

                    # Compare info headers
                    self.assertEqual(
                        imported_ann["info"]["description"],
                        exported_ann["info"]["description"],
                    )
                    self.assertEqual(
                        imported_ann["info"]["contributor"],
                        exported_ann["info"]["contributor"],
                    )

                    # Compare image fields
                    self.assertEqual(
                        len(imported_ann["images"]),
                        len(exported_ann["images"]),
                    )
                    for i in range(len(imported_ann["images"])):
                        self.assertEqual(
                            imported_ann["images"][i]["id"],
                            exported_ann["images"][i]["id"],
                        )
                        self.assertEqual(
                            imported_ann["images"][i]["file_name"],
                            exported_ann["images"][i]["file_name"],
                        )
                        self.assertEqual(
                            imported_ann["images"][i]["height"],
                            exported_ann["images"][i]["height"],
                        )
                        self.assertEqual(
                            imported_ann["images"][i]["width"],
                            exported_ann["images"][i]["width"],
                        )

                    # Compare annnotation fields
                    self.assertEqual(
                        len(imported_ann["annotations"]),
                        len(exported_ann["annotations"]),
                    )
                    for i in range(len(imported_ann["annotations"])):
                        self.assertEqual(
                            imported_ann["annotations"][i]["id"],
                            exported_ann["annotations"][i]["id"],
                        )
                        self.assertEqual(
                            imported_ann["annotations"][i]["image_id"],
                            exported_ann["annotations"][i]["image_id"],
                        )

                        self.assertEqual(
                            imported_ann["annotations"][i]["segmentation"],
                            exported_ann["annotations"][i]["segmentation"],
                        )
                        self.assertEqual(
                            [
                                round(coord)
                                for coord in imported_ann["annotations"][i]["bbox"]
                            ],
                            [
                                round(coord)
                                for coord in exported_ann["annotations"][i]["bbox"]
                            ],
                        )
                        self.assertEqual(
                            imported_ann["annotations"][i]["category_id"],
                            exported_ann["annotations"][i]["category_id"],
                        )
                        self.assertEqual(
                            imported_ann["annotations"][i]["category_name"],
                            exported_ann["annotations"][i]["category_name"],
                        )

                    # Compare category fields
                    self.assertEqual(
                        len(imported_ann["categories"]),
                        len(exported_ann["categories"]),
                    )
                    for i in range(len(imported_ann["images"])):
                        self.assertEqual(
                            imported_ann["categories"][i]["id"],
                            exported_ann["categories"][i]["id"],
                        )
                        self.assertEqual(
                            imported_ann["categories"][i]["name"],
                            exported_ann["categories"][i]["name"],
                        )
                        self.assertEqual(
                            imported_ann["categories"][i]["supercategory"],
                            exported_ann["categories"][i]["supercategory"],
                        )
