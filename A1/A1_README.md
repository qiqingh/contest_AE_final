## A1: Simulation Testbed

The A1 component provides a simulation-based 5G SA testbed built on an
instrumented OAI gNB. To simplify evaluation, we provide a pre-built
Docker image as well as optional remote desktop access.

### Option 1: Docker-based setup (recommended)

This is the easiest and recommended way to run A1 and A3.

#### Step 1: Pull the pre-built Docker image

```
sudo docker pull kqing0515/oai_testing:v3
```

Step 2: Launch the container

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
