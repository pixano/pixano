# Pixano

## Setup


- Install Javascript requirements
  - node > 18
  - pnpm > 7
- Install Python requirements
```bash
pip install -r requirements.txt
```
- Install dependencies
```bash
cd ui
pnpm i
```

## Launch server

From Pixano root directory:
```
DATA_DIR=[PATH TO DATA] uvicorn pixano.apps.explorer.main:app --reload
```

## Launch frontend
- Developer mode:
```bash
pnpm --parallel run dev
```
- Storybook:

```bash
pnpm -r run storybook
```
