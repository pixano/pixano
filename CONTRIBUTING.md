# Contributing to Pixano

Thank you for your interest in Pixano! Here you will find information on running Pixano locally and guidelines on how to publish your contributions.


## Getting started

### Issue and suggestions

If you find a bug or you think of some missing features that could be useful while using Pixano, please [open an issue](https://github.com/pixano/pixano/issues)!

### Modifications

To contribute more actively to the project, you are welcome to develop the fix or the feature you have in mind, and [create a pull request](https://github.com/pixano/pixano/pulls)!

And if you want to change the application to your liking, feel free to [fork this repository](https://github.com/pixano/pixano/fork)!


### Formatting your code

We use these extensions for formatting the Pixano source code:
- Python: Black
- Typescript: Prettier
- Svelte: Svelte for VS Code


## Running Pixano locally

If you are looking to contribute to Pixano and develop new features, you might be interested in running Pixano locally.

### Requirements

- Backend:
  - python == 3.10

```bash
pip install .
```

- Frontend:
  - node ~= 18.17
  - pnpm ~= 8.6

```bash
cd ui
pnpm i
```

### Running the server and apps

- Backend server:
```
DATA_DIR=[PATH TO DATA] uvicorn pixano.apps.explorer.main:app --reload
```

- Frontend apps:
```bash
pnpm --parallel run dev
```

### Running the storybook

The frontend includes a storybook for testing each components.

```bash
pnpm -r run storybook
```
