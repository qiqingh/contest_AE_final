# A2 – Constraint-Driven Toolchain (CONSET)

This directory contains the complete **A2 constraint-driven toolchain** used in the paper to:
1) preprocess 3GPP specifications (optional),
2) extract IEs and field pairs,
3) (optionally) query an LLM to synthesize DSL rules,
4) generate DSL-guided semantic test cases,
5) produce replayable (OTA-style) payloads (for simulation usage).

> **Important note (Phase-2 AE):**
> - The **LLM-dependent steps are OPTIONAL** and **not required** for functional/reproducible assessment.
> - For Phase-2, reviewers can run the required steps using the **pre-generated intermediate artifacts** provided in this repository (e.g., extracted contexts, field pairs, DSL rules, and/or generated testcases).

---

## Environment Requirements

- OS: Ubuntu 22.04 LTS
- Python: 3.10.x (tested with Python 3.10.12)
- Install Python dependencies (recommended in a venv):

```
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r installed_packages.txt
```

## Quick sanity imports (manual)
```
python3 -c "from pycrate_asn1dir import RRCNR; print('pycrate_asn1dir.RRCNR: OK')"
python3 -c "from pycrate_asn1rt.utils import bitstr_to_bytes; print('pycrate_asn1rt.utils.bitstr_to_bytes: OK')"
```

## Toolchain Overview (T1–T6)

The A2 pipeline is organized into six toolchains.
Recommended Phase-2 path: run T2 → T3 → T5 → T6 (no external keys required).

## T1 – 3GPP Preprocessing (OPTIONAL)

This step converts specification PDFs into parseable text/snippets.
**Requires a Mathpix API key**. If you do not have a key, you may skip T1 and use the preprocessed outputs provided in this repo.

```
cd contest_AE_final/A2_constraintdriven_toolchain/toolchain1_3GPP_preprocessing/code
python3 mathpix_processor.py
```

Inputs: 3GPP spec PDFs (see contest_AE_final/A2_constraintdriven_toolchain/toolchain1_3GPP_preprocessing/pdf_specifications if included)
Outputs: extracted / normalized text artifacts used by later stages

## T2 – IE Collection (REQUIRED for full regeneration)

This step identifies candidate IEs and selects representative sets.

###  T2 (intra-IE)

```
cd contest_AE_final/A2_constraintdriven_toolchain/toolchain2_IE_collection/intra-IE/code
python3 00_extract_IE_id.py
python3 01_filter_IE_with_ASN.py
python3 02_greedy_set_cover_intra.py
```

### T2 (inter-IE)

```
cd contest_AE_final/A2_constraintdriven_toolchain/toolchain2_IE_collection/inter-IE/code
python3 00_extract_IE_id.py
python3 01_filter_IE_with_ASN.py
python3 02_greedy_set_cover_inter.py
```

### Expected outputs:

- IE lists / filtered IE sets
- selected IE coverage sets (greedy set cover)

If you only want to validate later stages, you may use the repository’s pre-generated IE lists (if provided).

## T3 – Field-Pair Context Extraction (REQUIRED for full regeneration)

This step extracts **evidence contexts** for candidate field pairs.

### T3 (intra-IE)

```
cd contest_AE_final/A2_constraintdriven_toolchain/toolchain3_field_pair_context_extraction/intra-IE/code
python3 00_intra-IE_context_extract.py --all-pairs --no-self
```

### T3 (inter-IE)

```
cd contest_AE_final/A2_constraintdriven_toolchain/toolchain3_field_pair_context_extraction/inter-IE/code
python3 00_generate_aggressive_inter_ie_config.py
python3 01_inter_ie_enhanced_extractor.py
```

### Expected outputs:

- extracted field-pair evidence/context snippets (used by T4 or for offline inspection)

## T4 – LLM-Based DSL Synthesis (OPTIONAL)

This step turns extracted evidence into DSL rules using an LLM.
**Requires an OpenAI API key**. For Phase-2 evaluation, this is **not required** because **pre-generated DSL rules** are included.

To run anyway, set your API key in your environment:

export OPENAI_API_KEY="YOUR_KEY"

### T4 (intra-IE)

```
cd contest_AE_final/A2_constraintdriven_toolchain/toolchain4_field_pair_LLM_query/intra-IE/code
python3 00_aggregate_intra_ie_constraints.py
python3 01_generate_intra_ie_dsl.py
```

### T4 (inter-IE)

```
cd contest_AE_final/A2_constraintdriven_toolchain/toolchain4_field_pair_LLM_query/inter-IE/code
python3 00_aggregate_inter_ie_field_pairs.py
python3 01_generate_inter_ie_dsl_concurrent.py
```

### Expected outputs:

- DSL rule files for intra-IE and inter-IE constraints

## T5 – DSL → Testcase Generation (REQUIRED)

This step converts DSL rules into structured test case specifications.

```
cd contest_AE_final/A2_constraintdriven_toolchain/toolchain5_dsl_to_testcase/code
python3 unified_test_generator.py
```

Inputs: DSL rules (either from T4 or pre-generated)
Outputs: generated testcases (structured descriptions)


## T6 – OTA-Style Testcase Payload Generation (REQUIRED for A3 replay inputs)

This step reconstructs messages, re-encodes them, computes offsets, and emits payload files.

### T6 (intra-IE)

```
cd contest_AE_final/A2_constraintdriven_toolchain/toolchain6_generate_OTA_testcase/intra-IE/code
python3 03_re-construct.py
python3 04_re-encode.py
python3 05_cal_offset.py
python3 06_payload.py
python3 07_rename.py
python3 08_rename.py
```

### T6 (inter-IE)

```
cd contest_AE_final/A2_constraintdriven_toolchain/toolchain6_generate_OTA_testcase/inter-IE/code
python3 03_re-construct.py
python3 04_re-encode.py
python3 05_cal_offset.py
python3 06_payload.py
python3 07_rename.py
python3 08_rename.py
```

### Outputs:
- replayable payloads / testcase files consumed by the A1/A3 simulation environment

## Suggested Minimal Path for Phase-2 AE

If you want a straightforward Phase-2 run without any external API keys:
	1.	Install deps
	2.	Use provided pre-generated outputs for T2/T3/T4 
	3.	Run:
	•	T5: unified_test_generator.py
	•	T6: the intra-IE or inter-IE payload pipeline above

This validates that the toolchain executes end-to-end and produces payloads.

## Troubleshooting Notes

	•	If pycrate_asn1dir import fails:
	•	Ensure pip3 install -r installed_packages.txt was executed in the correct Python environment.
	•	Confirm you are using Python 3.10.x.
	•	If some scripts expect large input files (spec excerpts, caches):
	•	Use the pre-generated intermediate artifacts committed in the repo (recommended for Phase-2).
	•	If you run T1/T4:
	•	T1 requires Mathpix API key.
	•	T4 requires OpenAI API key.
	•	These are optional and not needed to validate functionality.

## Security / Safety

This A2 toolchain **only generates testcases and payloads intended for use in the provided simulation environment**.
OTA exploits targeting commercial devices are not included.