# Changelog

All notable changes to Pixano will be documented in this file.

## [Unreleased]

### Added

- Add Prettier and eslint packages and scripts for formatting and linting frontend code
- Add GitHub actions to format frontend and backend code
- Add GitHub action to test backend code
- Add new classes related to DatasetInfo for updated API (DatasetCategory, DatasetStat, DatasetTable)
- Add new class related to Dataset for updated API (DatasetItem)
- Add new classes related to DatasetItem for updated API (ItemEmbedding, ItemFeature, ItemObject, ItemView)
- Add from_rle method to BBox
- Add file_name, width, and height properties to Image
- Add option to load a list of DatasetCategory (category id and name pairs) in Importers
- Export the complete list of DatasetCategory (category id and name pairs) in Exporters
- Add new unit tests and refactor existing unit tests

### Changed

- **Breaking:** Send **media files as URI** instead of base 64 encodings in Pixano API. Allows for better speed and flexibility for more complex dataset, but drops support for datasets imported without copying media files (`portable=False`)
- **Refactor API** with new endpoints, new methods, new data types, and new unit tests
- Update Dataset and DatasetInfo classes for new API
- Update Exporters, Importers, and InferenceModels using updated API
- Remove the `portable=False` option from importers. Instead users can choose to either **copy or move the media files** to the dataset directory
- Update README with a small header description listing main features
- Update documentation website accent color to match with the new theme of the Pixano apps
- Update API reference generation
- Reformat GitHub actions
- Reformat and refactor frontend code with Prettier and eslint

### Fixed

- Fix type hints in CompressedRLE and RLE related utils functions
- Fix pip install commands in notebooks for Google Colab
- Fix broken link in CHANGELOG.md
- Fix internal cross-references in the API reference of the documentation website
- Fix eslint and TypeScript errors

## [0.4.1] - 2023-11-13

### Added

- Add **semantic search** on images using models like CLIP
- Add optional **custom media fields** in COCO and Image Importer in addition to the standard "image" field
- Add CONTRIBUTING.md for installation information and contribution guidelines

### Changed

- Improve descriptions and fix parameters in the notebooks
- Update dependencies requirements (Lance, FastAPI, Pydantic...)
- Move unit tests and assets to `tests/` folder

### Fixed

- Fix ONNX Runtime dependencies for using SAM and other interactive annotation models
- Fix dataset scrolling in Pixano Annotator
- Fix paths for Pixano API reference generation
- Raise an error when importing a dataset if the output is empty, generally because no files were found
- Fix Python import in `data/importers`

## [0.4.0] - 2023-10-26

### Added

- UI: Add a **dataset dashboard** in Pixano Explorer with dataset information and statistics
- UI: Add a **labels hierarchy** to group them by source, by view, and by category in item view
- UI: Add label category ID on hover in side panel and label toolbar in item view
- Add **labeling tool** for **classification** in Pixano Annotator
- Add **delete tool** for clearing current annotations in Pixano Annotator

### Changed

- **Breaking:** Replace ObjectAnnotation by new and better-defined **PixanoTypes**, and add notebook for creating a custom PixanoType
- **Breaking:** Update dataset **storage format** to **lancedb**, using .lance files instead of .parquet, and with separate tables for media, annotations, and embeddings
- **Design overhaul** of both Pixano Explorer and Annotator apps
- Refactor UI code and merge common code of Pixano Explorer and Annotator apps
- Refactor Python code and add unit tests
- Change thumbnails from 3x2 images to 4x2 images in dataset importer
- Generate API references automatically on the Pixano documentation website using mkdocs plugins

### Fixed

- UI: Fix category colors in item view
- UI: Fix item annotations to scale with zoom in item view
- UI: Fix displaying item information in item view
- UI: Fix clearing user inputs in item view if either segmentation model or embeddings are missing
- UI: Fix notebook integration by replacing JavaScript pop-ups by integrated windows
- UI: Fix displaying multi-view datasets in Pixano Annotator
- Fix saving annotations to file from Pixano Annotator
- Fix portable option in dataset import to copy files instead of moving them
- Fix imports and dependency versions for Pixano apps and UI components

## [0.3.2] - 2023-07-11

### Added

- Add first and last page buttons in Pixano Explorer
- Add search in label toolbar in Pixano Annotator

### Changed

- Separate image tools and annotation tools in Pixano Annotator
- Refactor Pixano Apps components
- Add links to Pixano Inference documentation in Pixano documentation
- Add link to dataset import notebook in Pixano apps

### Fixed

- Fix version requirement for pydantic package
- Fix color schemes and dark mode in Pixano apps
- Fix uses of svg icons in Pixano apps
- Fix tooltips for buttons and truncated texts in Pixano apps
- Fix display in Pixano Explorer for datasets without annotations
- Fix default device for embedding precomputing in notebook
- Fix default images paths for dataset import in notebook
- Update CHANGELOG format

## [0.3.1] - 2023-07-07

### Fixed

- Fix READMEs pictures and links
- Fix getting splits when processing dataset with an inference model
- Add warnings in inference notebooks for selecting CPU or GPU device

## [0.3.0] - 2023-07-07

### Added

- Add **Pixano Annotator** for smart dataset annotation using AI models like the **Segment Anything Model (SAM)**
- Add support for **importing datasets to Pixano** (image-only, COCO format, DOTAv2, and legacy Pixano datasets)
- Add support for **exporting Pixano datasets** to COCO format
- Add **dataset import and export notebooks** for an easier process
- Add **thumbnail and statistics generation** to dataset import process
- Add **user guides** for the Pixano Explorer and Annotator apps

### Changed

- Merge inference generation and embedding precomputing into a **single inference model class**
- Add custom type for embeddings for better support of **precomputed embedding datasets**
- Improve custom type for images
- Improve ease of use of Pixano Explorer and Annotator apps in notebooks
- Improve Pixano Explorer dataset page query speed
- Update Pixano Explorer for consistency with the new Pixano Annotator
- Refactor and reformat both backend and frontend code
- Improve READMEs and documentation

### Fixed

- Allow Pixano Explorer and Annotator apps to be created on any available port
- Check if dataset library exists when launching an app
- Fix support for nonnumerical IDs in datasets
- Fix annotations not being truly optional in ObjectAnnotation class and in Pixano Explorer
- Round confidence values for bounding box tooltips in Pixano Explorer
- Order all image transforms args to height first and width second for consistency
- Check provided user data in inference and dataset notebooks before running scripts, like splits folder or source media folders

## [0.2.1] - 2023-06-06

### Added

- Add GitHub workflow for automatically publishing new releases to PyPI

## [0.2.0] - 2023-05-22

### Added

- Add **embedding precomputing**
- Add **ONNX model support**
- Add **inference notebooks**
- Add **notebook display function** for Pixano Explorer

### Changed

- Improve overall Python code documentation and readability
- Improve README files and project documentation

### Fixed

- Fix License, Python version, and Python requirements in pyproject.toml file

## [0.1.1] - 2023-05-11

### Fixed

- Fix Python requirements

## [0.1.0] - 2023-05-11

### Added

- Create first public release

[Unreleased]: https://github.com/pixano/pixano/compare/main...develop
[0.4.1]: https://github.com/pixano/pixano/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/pixano/pixano/compare/v0.3.2...v0.4.0
[0.3.2]: https://github.com/pixano/pixano/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/pixano/pixano/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/pixano/pixano/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/pixano/pixano/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/pixano/pixano/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/pixano/pixano/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/pixano/pixano/releases/tag/v0.1.0
