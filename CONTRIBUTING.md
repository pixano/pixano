# Contributing to Pixano

Thank you for your interest in Pixano! Here you will find information on running Pixano locally and guidelines on how to publish your contributions.

## Getting started

### Issue and suggestions

If you find a bug or you think of some missing features that could be useful while using Pixano, please [open an issue](https://github.com/pixano/pixano/issues)!

### Modifications

To contribute more actively to the project, you are welcome to develop the fix or the feature you have in mind, and [create a pull request](https://github.com/pixano/pixano/pulls)!

And if you want to change the application to your liking, feel free to [fork this repository](https://github.com/pixano/pixano/fork)!

## Running Pixano locally

If you are looking to contribute to Pixano and develop new features, you will need to clone the Pixano repository and run it locally.

### Requirements

#### Backend

You will need `python == 3.10`. Then, inside the root `pixano/` directory, run this command to install all the Python dependencies:

```bash
pip install .
```

#### Frontend

You will need `node ~= 18.17` and `pnpm ~= 8.6`. Then, inside the `pixano/ui/` directory, run this command to install all the pnpm dependencies:

```bash
pnpm i
```

### Running the server and apps

First, launch the backend server using this command:

```bash
DATA_DIR=your_datasets_directory/ uvicorn pixano.apps:create_app --factory --reload
```

Then, in another terminal, launch the frontend apps using:

```bash
pnpm --parallel run dev
```

This command should provide you with `http://localhost` links you can open in your browser to access the Explorer and Annotator apps.

Both the uvicorn server and the pnpm apps will refresh automatically when you make changes to the code.

## Testing the code

We test our backend code with Python's built-in `unittest` framework. All our unit testing files are in the `tests/` folder, with a `test_` prefix, so your settings file in VS Code should look like this:

```json
  "python.testing.unittestArgs": ["-v", "-s", "./tests", "-p", "test_*.py"],
  "python.testing.pytestEnabled": false,
  "python.testing.unittestEnabled": true
```

Our frontend code is tested using Storybook, which you can launch with the following command:

```bash
pnpm -r run storybook
```

## Formatting and linting the code

### Backend

We format Python files and Jupyter notebooks with the **Black formatter**.

You can install the <a href="https://marketplace.visualstudio.com/items?itemName=ms-python.black-formatter" target="_blank">Visual Studio Extension</a> and set it to format files automatically on save.

Or you can use the Python package:

```bash
pip install black
black pixano/
black notebooks/
```

### Frontend

We format frontend files (Typescript, Javascript, Svelte, HTML, CSS, JSON, YAML, Markdown) with the **Prettier formatter**.

You can install the <a href="https://marketplace.visualstudio.com/items?itemName=esbenp.prettier-vscode" target="_blank">Visual Studio Extension</a> (and <a href="https://marketplace.visualstudio.com/items?itemName=svelte.svelte-vscode
" target="_blank">this Extension</a> for Svelte) and set them to format files automatically on save.

Or you can use the command line we have set up:

```bash
cd ui
pnpm format
```

We also lint frontend files with **eslint**.

You can use the command line we have set up:

```bash
cd ui
pnpm lint
```

## Formatting your commits

We format our commit messages with **the <a href="https://www.conventionalcommits.org/en/v1.0.0/#summary" target="_blank">Conventional Commits</a> guidelines.**

## Updating the changelog

When you want to create a pull request with the changes you have made, please update the CHANGELOG.md accordingly.

We format our changelog with **the <a href="https://keepachangelog.com/en/1.1.0/#how" target="_blank">Keep a Changelog</a> guidelines.**
