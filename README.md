# Triplet Task 2

- [Triplet Task 2](#triplet-task-2)
  - [Overview](#overview)
  - [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
  - [Usage](#usage)
    - [Command-line Arguments](#command-line-arguments)
  - [Output Format](#output-format)
  - [Evaluation](#evaluation)
    - [Evaluation Command-line Arguments](#evaluation-command-line-arguments)
    - [Evaluation Output](#evaluation-output)
  - [Workflow for TRIPLET Challenge](#workflow-for-triplet-challenge)

## Overview

This repository provides scripts for TRIPLET Task 2. The main script processes annotation datasets exported from the [ECLADATTA Annotation Tool](https://annotation-tool.ecladatta.eurecom.fr/) and generates outputs formatted for the challenge.

## Getting Started

### Prerequisites

- Python 3.7+
- [uv](https://docs.astral.sh/uv/) for dependency management.

### Installation

1. Clone this repository:

   ```bash
   git clone https://gitlab.eurecom.fr/tehrhart/triplet-task2.git
   cd triplet-task2
   ```

## Usage

To process a dataset, run:

```bash
uv run python -m triplet_task2.main <input>
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

## Evaluation

To evaluate predicted triplets against gold standard annotations, run:

```bash
uv run python -m triplet_task2.evaluate <predicted> <gold> [options]
```

Replace `<predicted>` and `<gold>` with the paths to the respective `annotations.csv` files.

### Evaluation Command-line Arguments

| Argument                       | Description                                                                  |
| ------------------------------ | ---------------------------------------------------------------------------- |
| `<predicted>`                  | Path to predicted annotations CSV file (required)                            |
| `<gold>`                       | Path to gold standard annotations CSV file (required)                        |
| `--relations <REL> [<REL>...]` | List of valid relations (default: predefined business relations)             |
| `-o, --output <OUTPUT>`        | Output file for evaluation results in JSON format (default: print to stdout) |
| `-v, --verbose`                | Increase verbosity (`-v`, `-vv`)                                             |
| `-h, --help`                   | Show help message and exit                                                   |

### Evaluation Output

The evaluation script outputs a JSON object with metrics for different matching strategies:

```json
{
  "Exact matching": {
    "precision": 0,
    "recall": 0.0,
    "f1": 0
  },
  "Partial matching (head+tail)": {
    "precision": 0,
    "recall": 0.0,
    "f1": 0
  },
  "Partial matching (relation + 1 entity)": {
    "precision": 0,
    "recall": 0.0,
    "f1": 0
  }
}
```

- **Exact matching**: All three elements (subject, predicate, object) must match.
- **Partial matching (head+tail)**: Both subject and object match, regardless of predicate.
- **Partial matching (relation + 1 entity)**: Relation and at least one entity (subject or object) match.

Each metric includes `precision`, `recall`, and `f1` score.

## Workflow for TRIPLET Challenge

1. Download the properties files for each dataset:
   - `female_celebrity_properties.csv`: https://nextcloud.eurecom.fr/s/binNocXa4CRAHKj
   - `telco_properties.csv`: https://nextcloud.eurecom.fr/s/2n6THinAHS5AXSW
   - `business_properties.csv`: https://nextcloud.eurecom.fr/s/Y6BnfB8a4PPKZLa

2. Run the `prepare_triplet_task2.sh` script to generate the required ZIP files for submission:

   ```bash
   ./prepare_triplet_task2.sh female_celebrity_properties.csv telco_properties.csv business_properties.csv
   ```

3. This will create three ZIP files:
   - `task2-train.zip`: Training dataset package.
   - `task2-test.zip`: Test dataset package.
   - `task2-groundtruth.zip`: Ground truth annotations for evaluation.
