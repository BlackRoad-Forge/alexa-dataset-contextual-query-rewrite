# Contextual Query Rewrite (CQR) Dataset for Spoken Dialogue

[![CI — Dataset Validation](https://github.com/blackboxprogramming/alexa-dataset-contextual-query-rewrite/actions/workflows/ci.yml/badge.svg)](https://github.com/blackboxprogramming/alexa-dataset-contextual-query-rewrite/actions/workflows/ci.yml)
[![Deploy GitHub Pages](https://github.com/blackboxprogramming/alexa-dataset-contextual-query-rewrite/actions/workflows/pages.yml/badge.svg)](https://github.com/blackboxprogramming/alexa-dataset-contextual-query-rewrite/actions/workflows/pages.yml)
[![CodeQL](https://github.com/blackboxprogramming/alexa-dataset-contextual-query-rewrite/actions/workflows/codeql.yml/badge.svg)](https://github.com/blackboxprogramming/alexa-dataset-contextual-query-rewrite/actions/workflows/codeql.yml)

![Contextual Query Rewrite](dialog2-crop.png)

## Overview

This dataset contains crowd-sourced contextual query rewrites for multi-turn, multi-domain task-oriented dialogues. It enables research in dialogue state tracking using natural language as the interface between dialogue agents.

**Dataset Splits:**

| Split    | File                           | Records | Size     |
| -------- | ------------------------------ | ------- | -------- |
| Training | `cqr_kvret_train_public.json`  | 2,131   | 10.7 MB  |
| Dev      | `cqr_kvret_dev_public.json`    | 271     | 1.3 MB   |
| Test     | `cqr_kvret_test_public.json`   | 276     | 1.3 MB   |

## Motivation

Dialogue assistants serve as a digital marketplace where any developer can build a domain-specific, task-oriented dialogue agent offering services such as booking cabs, ordering food, listening to music, or shopping. These agents may interact with each other when completing a task on behalf of the user. Accomplishing this requires understanding the context of a dialogue, communicating the conversational state to multiple agents, and updating the state as the conversation proceeds.

This dataset explores using natural language as an API for communicating across agents, eliminating the need to learn or adapt to diverse schema mappings. Instead, it leverages the syntactic and semantic regularities imposed by the language itself to track dialogue state.

## Quick Start

### Validate the dataset

```bash
python3 .github/scripts/validate_data.py
```

### Load data in Python

```python
import json

with open("cqr_kvret_train_public.json", "r") as f:
    train_data = json.load(f)

print(f"Training records: {len(train_data)}")

# Access a reformulation
for record in train_data:
    if "reformulation" in record:
        reform = record["reformulation"]
        if isinstance(reform, dict):
            print(f"Reformulated: {reform.get('reformulated_utt', 'N/A')}")
            break
```

### Verify data integrity

```bash
python3 .github/scripts/generate_checksums.py
```

## Data Format

The dataset is in JSON format. Each record may contain a `reformulation` key with the following structure:

| Key                    | Description                                               |
| ---------------------- | --------------------------------------------------------- |
| `base_utt_idx`         | Index of the original utterance selected for rewrite      |
| `flag`                 | Category of referring expressions                         |
| `gold_slots`           | Gold standard slots used in the rewrite                   |
| `mturk_reformulations` | List of crowd-sourced rewrites from MTurk                 |
| `reformulated_utt`     | Gold rewrite                                              |

Reformulations are created at the end of each dialogue (marked by `"end_dialogue": true`).

## File Checksums (SHA-256)

```
b043b02a2d55...  cqr_kvret_dev_public.json   (1,372,547 bytes)
2cd70b39ece8...  cqr_kvret_test_public.json  (1,409,098 bytes)
879ed1ff43d4...  cqr_kvret_train_public.json (11,245,101 bytes)
```

Full checksums available in `checksums.json`.

## Cloudflare Worker API

A Cloudflare Worker provides a REST API for querying the dataset. See `cloudflare-worker/` for configuration and source.

**Endpoints:**

| Method | Path               | Description                          |
| ------ | ------------------ | ------------------------------------ |
| GET    | `/`                | Health check and API info            |
| GET    | `/api/stats`       | Dataset statistics                   |
| GET    | `/api/splits`      | List available splits                |
| GET    | `/api/data/:split` | Retrieve records (`?limit=N&offset=M`) |
| GET    | `/api/search`      | Search records (`?q=query&split=train`) |
| GET    | `/api/checksums`   | File integrity checksums             |
| POST   | `/api/validate`    | Trigger dataset validation           |

## CI/CD & Infrastructure

| Component          | Status                                                                 |
| ------------------ | ---------------------------------------------------------------------- |
| Dataset Validation | Runs on every push and PR; weekly scheduled check                      |
| GitHub Pages       | Auto-deploys on push to master                                         |
| CodeQL             | Weekly security scanning + PR checks                                   |
| Dependabot         | Weekly GitHub Actions dependency updates                               |
| Automerge          | Auto-merges Dependabot patch/minor PRs after CI passes                 |
| Stale Bot          | Marks inactive issues/PRs after 60 days; closes after 14 more days     |
| Cloudflare Worker  | Auto-deploys on push to master (changes in `cloudflare-worker/`)       |

All GitHub Actions are **pinned to commit SHA hashes** for supply-chain security.

## Citation

```bibtex
@inproceedings{rastogi2019scaling,
  title={Scaling Multi-Domain Dialogue State Tracking via Query Reformulation},
  author={Rastogi, Pushpendre and Gupta, Arpit and Chen, Tongfei and Mathias, Lambert},
  booktitle={Proceedings of the 2019 Conference of the North American Chapter
             of the Association for Computational Linguistics},
  year={2019},
  publisher={Association for Computational Linguistics},
}
```

**Papers:**
- [Scaling Multi-Domain Dialogue State Tracking via Query Reformulation](https://arxiv.org/pdf/1903.05164.pdf)
- [CQR Dataset Creation Details](https://arxiv.org/pdf/1903.11783.pdf)

**Source Data:** [Stanford Dialogue Corpus](https://nlp.stanford.edu/blog/a-new-multi-turn-multi-domain-task-oriented-dialogue-dataset/)

## License

Copyright (c) 2024-2026 BlackRoad OS, Inc. All Rights Reserved. See the [LICENSE](LICENSE) file.

## Security

See [SECURITY.md](.github/SECURITY.md) for vulnerability reporting guidelines.
