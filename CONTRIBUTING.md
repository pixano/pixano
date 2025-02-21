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

You need a python environment with a supported version. Then, inside the root `pixano/` directory, run this command to install all the Python dependencies:

```bash
pip install . -e
```

The `-e` argument install the repository in dev mode so that your local changes are taken into account each time you run your environment.

#### Frontend

##### Dependencies

You will need `node ~= 23.8` and `pnpm ~= 10.4.1`. Then, run this to install all the pnpm dependencies:

```bash
cd ui/
pnpm i
```

##### Running the server and apps

First, you will need to launch the backend server using this command:

```bash
LIBRARY_DIR=your_datasets_directory/ MEDIA_DIR=your_media_directiory/  uvicorn pixano.app:create_app --factory --reload
```

Then, in another terminal, you can launch the frontend apps using:

```bash
cd ui/
pnpm --parallel run dev
```

This command should provide you with a `http://localhost` link you can open in your browser to access the Pixano app.

Both the backend server and the frontend apps should refresh automatically when you make changes to the code.

## Testing the code

### Backend

We test our backend code with Python's built-in `pytest` framework.

All our unit testing files are in the `tests/` folder, with a `test_` prefix.

### Frontend

Our frontend code is tested using Storybook, which you can launch with the following command:

```bash
cd ui/
pnpm -r run storybook
```

## Formatting and linting the code

### Backend

We format and lint backend files (Python, Jupyter notebooks) with **Ruff**.

You can install the [Visual Studio Extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff) and set it to format files automatically on save with the following configuration in your VSCode `settings.json`:

```json
{
  "notebook.formatOnSave.enabled": true,
  "notebook.codeActionsOnSave": {
    "notebook.source.fixAll": "explicit",
    "notebook.source.organizeImports": "explicit"
  },
  "[python]": {
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll": "explicit",
      "source.organizeImports": "explicit"
    },
    "editor.defaultFormatter": "charliermarsh.ruff"
  }
}
```

You can also use our **pre-commit** configuration to format and lint all backend files before commiting your changes:

```bash
pip install pre-commit
pre-commit run --all-files
```

You can also install the pre-commit hook if you want it to run automatically on `git commit`:

```bash
pre-commit install
```

If this command fails and/or format some files, you need to `git add` the files that you manually fixed and/or were modified by `pre-commit` before trying to commit again.

### Frontend

We format frontend files (Typescript, Javascript, Svelte, HTML, CSS, JSON, YAML, Markdown) with the **Prettier formatter**.

You can install the <a href="https://marketplace.visualstudio.com/items?itemName=esbenp.prettier-vscode" target="_blank">Visual Studio Extension</a> (and <a href="https://marketplace.visualstudio.com/items?itemName=svelte.svelte-vscode
" target="_blank">this Extension</a> for Svelte) and set them to format files automatically on save with the following configuration in your VSCode `settings.json`:

```json
{
  "[svelte]": {
    "editor.defaultFormatter": "svelte.svelte-vscode",
    "editor.formatOnSave": true
  },
  "[javascript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[jsonc]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[json]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[markdown]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[yaml]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[github-actions-workflow]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[html]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[css]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  }
}
```

You can also use the command lines we have set up to format and lint all frontend files before commiting your changes:

```bash
cd ui/
pnpm format
pnpm lint
```
