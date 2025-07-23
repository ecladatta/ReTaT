# Triplet Task 2

- [Overview](#overview)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Usage](#usage)
  - [Command-line Arguments](#command-line-arguments)
- [Output Format](#output-format)

## Overview

This repository provides scripts for TRIPLET Task 2. The main script processes annotation datasets exported from the [ECLADATTA Annotation Tool](https://annotation-tool.ecladatta.eurecom.fr/) and generates outputs formatted for the challenge.

## Getting Started

### Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/) for dependency management.

### Installation

1. Clone this repository:

   ```bash
   git clone https://gitlab.eurecom.fr/tehrhart/triplet-task2.git
   cd triplet-task2
   ```

2. Install dependencies using Poetry:

   ```bash
   poetry install
   ```

## Usage

To process a dataset, run:

```bash
poetry run python -m triplet_task2.main <input>
```

Replace `<input>` with the path to your source `.json` file.

This will create an output directory based on the input filename, containing the processed annotations and documents. See the [Output](#output) section for details on the generated files.

### Command-line Arguments

| Argument                | Description                                              |
| ----------------------- | -------------------------------------------------------- |
| `<input>`               | Path to the source `.json` file (required)               |
| `-o, --outdir <OUTDIR>` | Destination directory (default: based on input filename) |
| `-v, --verbose`         | Increase verbosity (`-v`, `-vv`)                         |
| `-h, --help`            | Show help message and exit                               |

## Output Format

Each output folder contains:

- `annotations.csv`: A CSV file with the columns:

  - `document_id`: The unique identifier of the source document for the annotation.
  - `subject`: The subject entity of the annotated triplet.
  - `predicate`: The predicate (relation) of the annotated triplet.
  - `object`: The object entity of the annotated triplet.

  Each row represents a single annotation (triplet) extracted from the input dataset.

- `documents.json`: A JSON array where each element is an object representing a document with the following fields:

  - `id`: The document's unique identifier.
  - `title`: The document's title.
  - `texts`: A list of text segments extracted from the document.
  - `tables`: A list of tables extracted from the document.

  This file contains all documents referenced by the annotations, including their extracted texts and tables.
