# Overview

This repository provides the complete artifact for evaluating **CONSET**, the
constraint-guided semantic testing framework presented in the paper
*“Semantics Over Syntax: Uncovering Pre-Authentication 5G Baseband Vulnerabilities.”*

The artifact is organized into three logical components that together enable
end-to-end validation of the paper’s methodology and key claims:

- **A1 — Simulation Testbed:**  
  A simulation-based 5G SA testing environment built on OAI and 5Ghoul, used to
  inject crafted RRC messages and observe UE behavior in a controlled setting.

- **A2 — Constraint-Driven Toolchain:**  
  A modular analysis and test-generation pipeline that extracts
  specification-level semantic constraints and translates them into executable
  test cases.

- **A3 — Test Cases and Exploits:**  
  Generated test cases and proof-of-concept exploit payloads that trigger
  reproducible UE crashes in the simulation environment.

All experiments are conducted **exclusively in an isolated simulation
environment**. The artifact does **not** include over-the-air (OTA) exploits for
commercial networks or devices.

For evaluator convenience, the artifact supports two execution modes:
local execution using Docker, and an optional pre-configured remote desktop
environment provided via the HotCRP Artifact Evaluation interface.

The sections below describe how to set up, execute, and validate each component
(A1–A3).

# A1: Simulation Testbed

The A1 component provides a simulation-based 5G SA testbed built on an
instrumented OAI gNB. To simplify evaluation, we provide a pre-built
Docker image as well as optional remote desktop access.

### Option 1: Docker-based setup (recommended)

This is the easiest and recommended way to run A1 and A3.

#### Step 1: Pull the pre-built Docker image

```
sudo docker pull kqing0515/oai_testing:v3
```
#### Step 2: Launch the container

```
sudo docker run -it \
  --name oai25_testing \
  --cpus="8" \
  --privileged \
  --ipc=host \
  --network=host \
  --mount type=tmpfs,destination=/dev/shm \
  --mount type=tmpfs,destination=/dev/mqueue \
  kqing0515/oai_testing:v3
```

After the container starts, the OAI-based simulation environment and all
required dependencies for A1/A3 are available inside the container.

This setup runs entirely in a local simulation environment and does
not require any real 5G radio hardware.

### Option 2: Optional remote desktop access

For reviewer convenience, we also provide access to a pre-configured
remote desktop environment where the Docker-based A1/A3 setup is already
installed and ready to run.
- This option avoids any local installation.
- **Remote access details (including the access link) are provided
privately via the HotCRP Artifact Evaluation interface.**
- The remote environment is intended only for artifact evaluation.

# A2 – Constraint-Driven Toolchain (CONSET)

This directory contains the complete **A2 constraint-driven toolchain** used in the paper to:
1) preprocess 3GPP specifications (optional),
2) extract IEs and field pairs,
3) (optionally) query an LLM to synthesize DSL rules,
4) generate DSL-guided semantic test cases,
5) produce replayable (OTA-style) payloads (for simulation usage).

> **Important note (Phase-2 AE):**
> - The **LLM-dependent steps are OPTIONAL** and **not required** for functional/reproducible assessment.
> - Reviewers can run the required steps using the **pre-generated intermediate artifacts** provided in this repository (e.g., extracted contexts, field pairs, DSL rules, and/or generated testcases).

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

### Inputs: 
3GPP spec PDFs (see contest_AE_final/A2_constraintdriven_toolchain/toolchain1_3GPP_preprocessing/pdf_specifications if included)
### Outputs: 
extracted / normalized text artifacts used by later stages

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

### Inputs: 
DSL rules (either from T4 or pre-generated)
### Outputs: 
generated testcases (structured descriptions)


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

# A3: Test Cases and Proof-of-Concept Exploits

This directory contains the generated test cases and proof-of-concept
exploit payloads used to validate the vulnerability-triggering behavior
described in the paper. All A3 experiments are conducted **only in a
simulation environment** based on OAI and 5Ghoul.

⚠️ **Important:**  
All provided exploits are **simulation-only** and are **not usable
over-the-air (OTA)**.

---

## Prerequisites

- Docker is installed and running
- The A1 simulation environment is launched using the provided Docker image: kqing0515/oai_testing:v3
- Reviewers may either:
- Run everything locally using Docker, **or**
- Use the **pre-configured remote desktop environment** provided via HotCRP
  (recommended, as the container and payloads are already set up)

---

## Step 1: Copy Payloads into the Docker Container

After the Docker container is running, copy the prepared payloads into
the container.

On the host machine:

```
sudo docker ps
```
Identify the running container ID (CONTAINER_ID), then run:

```
sudo docker cp contest_AE_final/A3_test_case_exploits/payloads \
CONTAINER_ID:/home/5ghoul-5g-nr-attacks/modules/exploits/5gnr_gnb
```

## 📌 Note:
If you are using the provided remote desktop environment, this step can
be skipped—the payloads have already been placed in the correct location.

## Step 2: Enter the Docker Container

```
sudo docker exec -it CONTAINER_ID /bin/bash
```

Inside the container:

```
cd /home/5ghoul-5g-nr-attacks/modules/exploits/5gnr_gnb
cp ./payloads/* ./
cd /home/5ghoul-5g-nr-attacks
```

## Step 3: Recompile Exploits

Recompile all exploit payloads using:

```
sudo bin/5g_fuzzer --list-exploits
```

## ⚠️ Note:

Some compilation warnings or errors may appear during this step.
These can be safely ignored as long as the target exploit is successfully
registered.

## Step 4: Run a Specific Exploit Payload

The available exploit names can be found in:
```
contest_AE_final/A3_test_case_exploits/compiled_payloads/
```

To run a specific exploit:

```
sudo ./bin/5g_fuzzer \
  --exploit=PAYLOAD_NAME \
  --MCC=001 \
  --MNC=01 \
  --GlobalTimeout=false \
  --EnableMutation=false
```

### Example

If the exploit file is:

```
mac_sch_6e99a9e9.cpp
```
Run:
```
sudo ./bin/5g_fuzzer \
  --exploit=mac_sch_6e99a9e9 \
  --MCC=001 \
  --MNC=01 \
  --GlobalTimeout=false \
  --EnableMutation=false
```

## Expected Behavior (With Exploit)

When running a valid exploit payload, the simulator should frequently
report:

```
[!] UE process crashed
```

This indicates successful triggering of the vulnerability in the simulated UE.

## Baseline Behavior (Without Exploit)

As a control experiment, run the simulator **without loading any exploit**:
```
sudo bin/5g_fuzzer \
  --EnableSimulator=true \
  --EnableMutation=false \
  --GlobalTimeout=false
```

Expected output in this case is typically:

```
[!] UE process stopped
[!] UE process started
```

Crashes ([!] UE process crashed) should occur **rarely**, although some instability in the simulator is known and expected.

## Notes

- All crashes observed in A3 are **simulation-only** and occur in a
controlled laboratory environment.
- These experiments are intended to validate the **exploitability and
reproducibility** of the generated test cases, not to demonstrate real-world OTA attacks.
