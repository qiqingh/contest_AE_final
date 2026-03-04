# A1 Simulation Environment: Docker Image Build Documentation

This document describes how the simulation environment was constructed.

## Base Image

```
ubuntu:22.04
```

## Components

The Docker image integrates two components in a single container:

### 1. 5Ghoul (adapted for Ubuntu 22.04)

The 5Ghoul framework was cloned from the official repository and adapted for Ubuntu 22.04:

- Updated system dependencies from Ubuntu 18.04 to 22.04 equivalents
- Fixed compilation issues introduced by the OS upgrade
- Compiled the framework from source inside the container

Official repository: https://github.com/asset-group/5ghoul-5g-nr-attacks

### 2. OpenAirInterface 5G SA (2025.w05 branch)

OAI was built from the official repository following the OAI installation and compilation documentation:

- Branch: `2025.w05`
- Build targets: `nr-softmodem` (gNB) and `nr-uesoftmodem` (UE)

Official repository: https://gitlab.eurecom.fr/oai/openairinterface5g

## Integration

The two components are integrated by modifying the 5Ghoul gNB configuration file at:

```
/home/5ghoul-5g-nr-attacks/configs/5gnr_gnb_config.json
```

The gNB and UE binary paths are updated to point to the OAI 2025.w05 build outputs:

```json
"/home/openairinterface5g/cmake_targets/ran_build/build/nr-softmodem",
"/home/openairinterface5g/cmake_targets/ran_build/build/nr-uesoftmodem"
```

This allows 5Ghoul's downlink interception hooks to operate with the 2025.w05 OAI stack.

## TODO

We acknowledge that the current Docker image is relatively large, as it retains the full build environment and intermediate artifacts from both 5Ghoul and OAI compilation. The image is closer to a development environment than a minimal simulation image. We are working on an optimized version that retains only the necessary binaries and runtime dependencies to reduce the image size. We appreciate your patience and understanding in the meantime.