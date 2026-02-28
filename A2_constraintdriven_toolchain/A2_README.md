# A2 – Constraint-Driven Toolchain (CONSET)

This directory contains the complete **A2 constraint-driven toolchain** used in the paper to:
1) preprocess 3GPP specifications (optional),
2) extract IEs set to cover the 5G messgae,
3) extract field pairs related context from 3GPP specifications
4) query an LLM to synthesize DSL rules (optionally) ,
5) generate DSL-guided semantic test cases,
6) produce replayable (OTA-style) payloads (for simulation usage).

> **Important note (Phase-2 AE):**
> - The **LLM-dependent steps are OPTIONAL** and **not required** for functional/reproducible assessment.
> - Reviewers can run the required steps using the **pre-generated intermediate artifacts** provided in this repository (e.g., extracted contexts, field pairs, DSL rules, and/or generated testcases).

---

## Environment Setup

The following steps have been verified on a Ubuntu 22.04 environment.

### Step 1: Start a clean Ubuntu 22.04 environment
```bash
docker run -it --name ae_e1_test ubuntu:22.04 bash
```

### Step 2: Install system dependencies
```bash
apt update && apt install -y git python3 python3-venv python3-pip python3-dev \
  gcc g++ build-essential make cmake pkg-config \
  libcairo2-dev libsystemd-dev gettext libdbus-glib-1-dev \
  libgirepository1.0-dev libdbus-1-dev libcups2-dev
```

### Step 3: Clone the repository
```bash
git clone https://github.com/qiqingh/contest_AE_final
cd contest_AE_final/A2_constraintdriven_toolchain
```

### Step 4: Set up Python virtual environment and install dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r installed_packages.txt
```

### Step 5: Verify installation
```bash
python3 -c "from pycrate_asn1dir import RRCNR; print('pycrate OK')"
```

## Toolchain Overview (T1–T6)

![CONSET Toolchain Overview](./A2_constraintdriven_toolchain/toolchain_overview.png)

The A2 pipeline is organized into six toolchains.
Recommended Phase-2 path: run T2 → T3 → T5 → T6 (no external keys required).

The A2 toolchain is split into six independent stages, each with a distinct purpose. This separation allows individual stages to be run, replaced, or reused independently — for example, skipping T1/T4 using pre-generated intermediates, or reusing T3 outputs for different LLM backends in T4.

| Toolchain | Input | Output | Required |
|:---|:---|:---|:---|
| **T1 – 3GPP Preprocessing** | 3GPP spec PDFs | LaTeX-structured 3GPP text (.txt) | Optional (Mathpix key) |
| **T2 – IE Collection** | Flattened 5G message | Representative IE sets (intra-IE and inter-IE) | Required |
| **T3 – Field-Pair Context Extraction** | IE sets (from T2) & 3GPP text (from T1) | Per-field-pair relevant 3GPP text snippets | Required |
| **T4 – LLM-Based DSL Constraint Synthesis** | Field-pair context snippets (from T3) | DSL constraint rules with supporting evidence | Optional (OpenAI key) |
| **T5 – Test Case Generation** | DSL constraint rules (from T4 or pre-generated) | Constraint-violating field modifications | Required |
| **T6 – OTA Payload Generation** | Test cases (from T5) | Byte-level exploit payloads (offset + value) | Required |

![5G Message Structure](./A2_constraintdriven_toolchain/message_structure.png)

**Note:** A 5G RRC message is composed of multiple **Information Elements (IEs)**, and each IE contains multiple **fields**. Since 5G RRC messages contain deeply nested IEs, our goal is to extract semantic constraints between fields. T2 identifies a minimum-cost set of IEs that covers the full message structure. 

To capture both types of field relationships, we split the analysis into two tracks: **intra-IE** (constraints between fields within the same IE) and **inter-IE** (constraints between fields across different IEs).

> **Note:** All subsequent toolchain commands assume you are already inside `contest_AE_final/A2_constraintdriven_toolchain/`. Use relative paths from there, e.g. `cd toolchain1_3GPP_preprocessing/code`.
> 
## T1 – 3GPP Preprocessing (OPTIONAL)

This step converts specification PDFs into parseable text/snippets.
**Requires a Mathpix API key**. If you do not have a key, you may skip T1 and use the preprocessed outputs provided in this repo.

```
cd toolchain1_3GPP_preprocessing/code
python3 mathpix_processor.py
cd -
```

### Inputs: 
3GPP spec PDFs (see contest_AE_final/A2_constraintdriven_toolchain/toolchain1_3GPP_preprocessing/pdf_specifications)

### Expected outputs:

- Parsed 3GPP specification text files saved to:
```
  toolchain1_3GPP_preprocessing/outputs/txt_specifications_mathpix
```

## T2 – IE Collection (REQUIRED for full regeneration)

This step identifies candidate IEs and selects representative sets.

###  T2 (intra-IE)

```
cd toolchain2_IE_collection/intra-IE/code
python3 00_extract_IE_id.py
python3 01_filter_IE_with_ASN.py
python3 02_greedy_set_cover_intra.py
cd -
```
> **Note:** When prompted, you may select option `1 - 1st Place (Recommended)`.

### T2 (inter-IE)

```
cd toolchain2_IE_collection/inter-IE/code
python3 00_extract_IE_id.py
python3 01_filter_IE_with_ASN.py
python3 02_greedy_set_cover_inter.py
cd -
```
> **Note:** When prompted, you may select option `1 - 1st Place (Recommended)`.


### Expected outputs:

- **Intra-IE:** final selected IE set saved to:
```
  toolchain2_IE_collection/intra-IE/outputs/intra-IE_strategy/selected_ies
```
- **Inter-IE:** final selected IE set saved to:
```
  toolchain2_IE_collection/inter-IE/outputs/inter-IE_strategy/selected_ies
```

> If you only want to validate later stages, you may use the repository's pre-generated IE lists in the above directories.


## T3 – Field-Pair Context Extraction (REQUIRED for full regeneration)

This step extracts **evidence contexts** for candidate field pairs.

### T3 (intra-IE)

```
cd toolchain3_field_pair_context_extraction/intra-IE/code
python3 00_intra-IE_context_extract.py --all-pairs --no-self
cd -
```

### T3 (inter-IE)

```
cd toolchain3_field_pair_context_extraction/inter-IE/code
python3 00_generate_aggressive_inter_ie_config.py
python3 01_inter_ie_enhanced_extractor.py
cd -
```


### Expected outputs:

- **Intra-IE:** extracted field-pair context snippets saved to:
```
  toolchain3_field_pair_context_extraction/intra-IE/outputs/context_with_sections_all_pairs
```
- **Inter-IE:** extracted field-pair context snippets saved to:
```
  toolchain3_field_pair_context_extraction/inter-IE/output/context_enhanced
```
  

## T4 – LLM-Based DSL Synthesis (OPTIONAL)

This step turns extracted evidence into DSL rules using an LLM.
**Requires an OpenAI API key**. For Phase-2 evaluation, this is **not required** because **pre-generated DSL rules** are included.

To run anyway, set your API key in your environment:

export OPENAI_API_KEY="YOUR_KEY"

### T4 (intra-IE)

```
cd toolchain4_field_pair_LLM_query/intra-IE/code
python3 00_aggregate_intra_ie_constraints.py
python3 01_generate_intra_ie_dsl.py
cd -
```

### T4 (inter-IE)

```
cd toolchain4_field_pair_LLM_query/inter-IE/code
python3 00_aggregate_inter_ie_field_pairs.py
python3 01_generate_inter_ie_dsl_concurrent.py
cd -
```

### Expected outputs:

- **Intra-IE:** DSL constraint rule files saved to:
```
  toolchain4_field_pair_LLM_query/intra-IE/outputs/intra-IE_DSL_results_gpt4o
```
- **Inter-IE:** DSL constraint rule files saved to:
```
  toolchain4_field_pair_LLM_query/inter-IE/output/inter_ie_dsl_rules_gpt4o
```

## T5 – DSL → Testcase Generation (REQUIRED)

This step converts DSL rules into structured test case specifications.

```
cd toolchain5_dsl_to_testcase/code
python3 unified_test_generator.py
cd -
```

### Inputs: 
DSL rules (either from T4 or pre-generated)

### Expected outputs:

- **Intra-IE:** generated constraint-violating field modifications saved to:
```
  toolchain5_dsl_to_testcase/output/test_cases_intra_ie
```
- **Inter-IE:** generated constraint-violating field modifications saved to:
```
  toolchain5_dsl_to_testcase/output/test_cases_inter_ie
```


## T6 – OTA-Style Testcase Payload Generation (REQUIRED for A3 replay inputs)

This step reconstructs messages, re-encodes them, computes offsets, and emits payload files.

### T6 (intra-IE)

```
cd toolchain6_generate_OTA_testcase/intra-IE/code
python3 ./run_T6.py
cd -
```

### T6 (inter-IE)

```
cd toolchain6_generate_OTA_testcase/inter-IE/code
python3 ./run_T6.py
cd -
```

### Expected outputs:

- **Intra-IE:** replayable payload files saved to:
```
  toolchain6_generate_OTA_testcase/intra-IE/output/06_payloads
```
- **Inter-IE:** replayable payload files saved to:
```
  toolchain6_generate_OTA_testcase/inter-IE/output/06_payloads
```

> **Note:** T6 decodes the original message, applies constraint-violating modifications, and re-encodes it. Intermediate outputs from each step are retained in the output directory to facilitate diagnosis after the message decode and then modify and later re-encode pipeline. Each stage's output can also be used independently for other purposes, such as custom payload construction or integration with other testing frameworks.

## Suggested Minimal Path for Phase-2 AE

If you want a straightforward Phase-2 run without any external API keys:

1. **Environment Setup**
2. **Use provided pre-generated outputs** for T2/T3/T4
3. **Run:**
   - **T5**: `unified_test_generator.py`
   - **T6**: the intra-IE or inter-IE payload pipeline above

This validates that the toolchain executes end-to-end and produces payloads.

## Troubleshooting Notes

- **If `pycrate_asn1dir` import fails:**
  - Ensure that `pip3 install -r installed_packages.txt` was executed in the correct Python environment (e.g., the activated virtual environment).
  - Confirm that you are using **Python 3.10.x**.

- **If some scripts expect large input files** (e.g., specification excerpts or cached intermediate data):
  - Use the **pre-generated intermediate artifacts** committed in this repository (recommended for Phase-2 evaluation).

- **If you choose to run optional toolchains (T1 / T4):**
  - **T1** requires a valid **Mathpix API key**.
  - **T4** requires a valid **OpenAI API key**.
  - These steps are **optional** and **not required** to validate the functionality or reproducibility of the artifact.

## Security / Safety

This A2 toolchain **only generates testcases and payloads intended for use in the provided simulation environment**.
OTA exploits targeting commercial devices are not included.
