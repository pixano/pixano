# Release notes


## Pixano v0.3.0

### Added:
- Add **Pixano Annotator** for smart dataset annotation using AI models like the **Segment Anything Model (SAM)**
- Add **dataset conversion notebooks** and template data loader to make conversion to Pixano format **more accessible** to users
- Add **data loaders** rebuilt from the ground up with support for **COCO format datasets, image-only datasets, and DOTAv2 dataset** 
- Add **thumbnail and statistics generation** to dataset conversion process
- Add **user guides** for the Pixano Explorer and Annotator apps

### Changed:
- Merge inference generation and embedding precomputing into a **single inference model class**
- Add custom type for embeddings for better support of **precomputed embedding datasets**
- Improve custom type for images
- Improve ease of use of Pixano Explorer and Annotator apps in notebooks
- Improve Pixano Explorer dataset page query speed
- Update Pixano Explorer for consistency with the new Pixano Annotator
- Refactor and reformat both backend and frontend code
- Update READMEs and documentation

### Fixed:
- Allow Pixano Explorer and Annotator apps to be created on any available port
- Check if dataset library exists when launching an app
- Fix support for nonnumerical IDs in datasets
- Fix bounding boxes not being truly optional in ObjectAnnotation 
- Order all image transforms args to height first and width second for consistency
- Check provided user data in inference and dataset notebooks before running scripts, like splits folder or source media folders


## Pixano v0.2.1

### Added
- Add GitHub workflow for automatically publishing new releases to PyPI


## Pixano v0.2.0

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


## Pixano v0.1.1

### Fixed
- Fix Python requirements


## Pixano v0.1.0

### Added
- Create first public release