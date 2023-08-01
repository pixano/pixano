# Changelog

All notable changes to Pixano will be documented in this file.



## [Unreleased]

### Added:
- Add labels hierarchy (group by source, view, and category) in both Pixano apps
- Add label category ID on hover in side panel and label toolbar in both Pixano apps
- Scale item annotations with zoom inside Pixano apps
- Add new better defined types for Pixano annotations

### Changed:
- Replace JavaScript popup boxes by integrated windows in Pixano Apps to fix notebook integration
- Update import dataset portable option from moving files to copying them 
- Refactor all UI code and merge common code for Explorer and Annotator apps

## Fixed:
- Fix category colors
- Fix saving annotations to file from Pixano Annotator
- Fix displaying item information inside Pixano apps item view
- Clear user inputs if either inference model or embedding directory is missing in Pixano Annotator 
- Fix Pixano Annotator for multi-views datasets
- Fix imports and dependency versions for Pixano apps and UI components


## [0.3.2] - 2023-07-11

### Added:
- Add first and last page buttons in Pixano Explorer
- Add search in label toolbar in Pixano Annotator

### Changed:
- Separate image tools and annotation tools in Pixano Annotator
- Refactor Pixano Apps components
- Add links to Pixano Inference documentation in Pixano documentation
- Add link to dataset import notebook in Pixano apps

### Fixed:
- Fix version requirement for pydantic package
- Fix color schemes and dark mode in Pixano apps
- Fix uses of svg icons in Pixano apps
- Fix tooltips for buttons and truncated texts in Pixano apps
- Fix display in Pixano Explorer for datasets without annotations
- Fix default device for embedding precomputing in notebook
- Fix default images paths for dataset import in notebook
- Update CHANGELOG format



## [0.3.1] - 2023-07-07

### Fixed:
- Fix READMEs pictures and links
- Fix getting splits when processing dataset with an inference model
- Add warnings in inference notebooks for selecting CPU or GPU device



## [0.3.0] - 2023-07-07

### Added:
- Add **Pixano Annotator** for smart dataset annotation using AI models like the **Segment Anything Model (SAM)**
- Add support for **importing datasets to Pixano** (image-only, COCO format, DOTAv2, and legacy Pixano datasets)
- Add support for **exporting Pixano datasets** to COCO format 
- Add **dataset import and export notebooks** for an easier process 
- Add **thumbnail and statistics generation** to dataset import process
- Add **user guides** for the Pixano Explorer and Annotator apps

### Changed:
- Merge inference generation and embedding precomputing into a **single inference model class**
- Add custom type for embeddings for better support of **precomputed embedding datasets**
- Improve custom type for images
- Improve ease of use of Pixano Explorer and Annotator apps in notebooks
- Improve Pixano Explorer dataset page query speed
- Update Pixano Explorer for consistency with the new Pixano Annotator
- Refactor and reformat both backend and frontend code
- Improve READMEs and documentation

### Fixed:
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



[Unreleased]: https://github.com/pixano/pixano/compare/v0.3.1...HEAD
[0.3.2]: https://github.com/pixano/pixano/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/pixano/pixano/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/pixano/pixano/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/pixano/pixano/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/pixano/pixano/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/pixano/pixano/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/pixano/pixano/releases/tag/v0.1.0

