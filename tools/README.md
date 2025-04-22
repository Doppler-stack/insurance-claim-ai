# 🛠 Tools

This folder contains one-off developer utilities that help maintain and inspect the project.

## Included Scripts

### `verify_schema.py`
Prints out the current structure of the `claims` table inside `database.db`.

Use this after DB resets, model updates, or to verify that migrations have taken effect.

```bash
python tools/verify_schema.py
