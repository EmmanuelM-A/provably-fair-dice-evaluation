# Provably Fair Dice Evaluation Framework

A framework for generating, evaluating, and reporting on provably fair dice mechanisms.

---

## Project Structure

```text
provably-fair-dice-evaluation/
├── src/
│   ├── config/                   # Global constants and directory paths
│   ├── core/                     # Entry-point scripts (rolls, evaluate, report, run)
│   ├── enigines/                 # Evaluation and report engine logic
│   ├── modules/                  # Test modules: randomness, security, transparency, performance
│   ├── provably_fair_mechanisms/ # Mechanism implementations (HMAC, Chainlink, drand)
│   ├── utils/                    # Shared types, data loader, common operations
│   └── logger/                   # Logging setup
├── results/
│   ├── rolls/                    # Generated roll records (CSV)
│   ├── programmable/             # Programmable evaluation results (JSON)
│   ├── non_programmable/         # Non-programmable assessment inputs (JSON)
│   └── reports/                  # Generated HTML reports
├── logs/                         # Application logs
├── requirements.txt
└── .env                          # Required for Chainlink VRF only
```

---


## Setup

**Install dependencies:**

```bash
pip install -r requirements.txt
```

**Chainlink VRF only** -- add the following to a `.env` file in the project root:

```text
VRF_RPC_URL=
VRF_CONSUMER_ADDRESS=
VRF_COORDINATOR_ADDRESS=
VRF_SENDER_ADDRESS=
VRF_SENDER_PRIVATE_KEY=
```

---

## Adding a New Mechanism

The framework is designed so that all evaluation logic is completely separate from the mechanisms themselves. Everything connects through a single base class: `ProvablyFairDiceMechanism` in `src/enigines/pfd.py`.

**1. Create a new file in `src/provably_fair_mechanisms/`** and implement two things:

- A class that extends `ProvablyFairDiceMechanism` with `generate_rolls()` and `verify()` implemented
- A module-level mapping function (e.g. `my_dice_outcome(raw_output: bytes) -> float`) that maps raw bytes to a dice outcome

**2. Register it in `src/core/get_inputs.py`** by adding it to both `get_mechanism()` and `get_mechanism_mapping_fn()` as a commented option.

The evaluation engine, all test modules, and the report engine never import any specific mechanism directly. They only ever receive a `ProvablyFairDiceMechanism` instance and call `generate_rolls()` or `verify()` on it. As long as those two methods produce `RollRecord` objects with the correct fields, the entire pipeline runs without any other changes.

---

## Switching Mechanisms

Before running, open `src/core/get_inputs.py` and uncomment the mechanism you want to use in both `get_mechanism()` and `get_mechanism_mapping_fn()`:

```python
# Uncomment one in each function:

# return StakesHMACMechanism(output_file=data_file_path)
  return BetSwirlChainlinkMechanism(output_file=data_file_path)
# return BlockRandDrandMechanism(output_file=data_file_path)

# return stake_dice_outcome
  return betswirl_dice_outcome
# return blockrand_dice_outcome
```

---

## How to Use

All commands are run from the project root with `python -m`.

### Option A: Full Pipeline (recommended)

Runs roll generation, evaluation, and report in one command.

```bash
python -m src.core.run --c 1000 --t LIGHT --d <rolls_name> --r <results_name> --np <nper_name>
```

| Argument | Description |
| -------- | ----------- |
| `--c` | Number of rolls to generate (default: 1000) |
| `--t` | Evaluation tier: `LIGHT`, `IN_DEPTH`, or `FULL_DEPTH` (default: `LIGHT`) |
| `--d` | Name for the rolls file, saved to `results/rolls/<name>.csv` |
| `--r` | Name for the evaluation results file, saved to `results/programmable/<name>.json` |
| `--np` | Name of the non-programmable assessment file to load from `results/non_programmable/<name>.json` |
| `--o` | (Optional) Name for the output HTML report. Defaults to the same name as `--r` |

**Example:**

```bash
python -m src.core.run --c 1000 --t IN_DEPTH --d stakes_hmac --r stakes_hmac_per --np stakes_hmac_nper
```

---

### Option B: Step by Step

Run each stage separately if you want more control.

**Step 1 -- Generate rolls:**

```bash
python -m src.core.rolls --c 1000 --d <rolls_name>
```

**Step 2 -- Evaluate:**

```bash
python -m src.core.evaluate --d <rolls_name> --r <results_name> --t LIGHT
```

**Step 3 -- Generate report:**

```bash
python -m src.core.report --r <results_name> --np <nper_name>
```

---

## Non-Programmable Assessment Files

The report requires a non-programmable evaluation (nper) JSON file containing manual assessments for each mechanism. Pre-filled files for all three mechanisms are already provided in `results/non_programmable/`:

| File | Mechanism |
| ---- | --------- |
| `stakes_hmac_nper.json` | HMAC-SHA256 (Stake) |
| `betswirl_chainlink_nper.json` | Chainlink VRF v2.5 (BetSwirl) |
| `blockrand_drand_nper.json` | drand quicknet (BlockRand) |

---

## Evaluation Tiers

| Tier | What runs |
| ---- | --------- |
| `LIGHT` | Chi-square, Cramer-von Mises, Runs, NIST tests 1-7, seed and nonce checks, latency |
| `IN_DEPTH` | Everything in LIGHT, plus entropy monitoring, NIST tests 8-10, throughput under load |
| `FULL_DEPTH` | Reserved for future extension |

> Note: IN_DEPTH requires at least 1,000,000 bits of raw output data. With 1000 rolls this threshold is met. Running with fewer rolls will cause the NIST in-depth tests to be skipped.

---

## Output

| Output | Location |
| ------ | -------- |
| Roll records | `results/rolls/<name>.csv` |
| Evaluation results | `results/programmable/<name>.json` |
| HTML report | `results/reports/<name>.html` |
| Logs | `logs/app.log` |
