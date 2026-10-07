"""Exécuter le notebook avec le Python courant, sans noyau global à installer."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    # Python 3.13 on Windows: ZMQ needs add_reader support. Avoid the fallback
    # selector thread, which can fail during interpreter shutdown in a sandbox.
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'notebooks/01_exploration.ipynb')
    args = parser.parse_args()
    source = ROOT / 'notebooks/01_exploration.ipynb'
    notebook = nbformat.read(source, as_version=4)
    nbformat.validate(notebook)
    # Temporary local kernel explicitly points at .venv when this script is run there.
    with tempfile.TemporaryDirectory(prefix='m259-jupyter-') as folder:
        temporary = Path(folder)
        kernel_dir = temporary / 'kernels/m259-analysis'
        kernel_dir.mkdir(parents=True)
        (kernel_dir / 'kernel.json').write_text(json.dumps({
            'argv': [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}'],
            'display_name': 'M259 analyse', 'language': 'python',
        }), encoding='utf-8')
        variables = {
            'JUPYTER_PATH': str(temporary),
            'JUPYTER_RUNTIME_DIR': str(temporary / 'runtime'),
            'JUPYTER_CONFIG_DIR': str(temporary / 'config'),
            'IPYTHONDIR': str(temporary / 'ipython'),
            'MPLCONFIGDIR': str(temporary / 'matplotlib'),
        }
        previous = {key: os.environ.get(key) for key in variables}
        os.environ.update(variables)
        try:
            NotebookClient(notebook, timeout=180, kernel_name='m259-analysis',
                           resources={'metadata': {'path': str(ROOT)}},
                           record_timing=False).execute()
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    # Keep notebook portable for VS Code; transient kernel is not installed globally.
    notebook.metadata.kernelspec = {
        'display_name': 'Python 3 (.venv)', 'language': 'python', 'name': 'python3',
    }
    nbformat.validate(notebook)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(notebook, args.output)
    executed = sum(c.cell_type == 'code' for c in notebook.cells)
    figures = sum('image/png' in out.get('data', {}) for cell in notebook.cells
                  if cell.cell_type == 'code' for out in cell.outputs)
    print(f'Notebook exécuté : {executed} cellules de code, {figures} graphiques, aucune erreur.')


if __name__ == '__main__':
    main()
