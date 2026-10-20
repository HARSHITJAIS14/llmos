# IITK GPU server access

Connect FortiClient VPN on the Mac, then:

```sh
ssh gpu3
source /data/harshitj23/screen-understanding/activate.sh
tmux new -A -s perception
```

The login is `harshitj23@gpu3.cse.iitk.ac.in` (confirmed remotely). The Mac SSH configuration uses the existing `~/.ssh/id_ed25519_csews` key. No password is stored in SSH config, and no private key was copied to the server. A timestamped backup of the prior config is beside `~/.ssh/config`.

SSH has 30-second keepalives, a 15-second connection timeout, and 10-minute connection reuse. VPN is still required. A new connection with reuse disabled was verified successfully with password prompts disabled.

Private workspace: `/data/harshitj23` with permissions 700. GPU observed: one NVIDIA A40, 46068 MiB visible. Check availability before starting a workload:

```sh
nvidia-smi
df -h /data
```

Miniforge replaces the retired Mambaforge installer from the older setup notes. The installer is downloaded on the Mac, checked against the official GitHub release SHA256, transferred using SSH, and checked again remotely. Installation verified: Miniforge 26.7.2-0, with an isolated offline clone using Python 3.14.7 and pip 26.2.1. Model packages are not installed yet. Before installing the perception stack, create a Python 3.11/3.12 environment with versions supported by the selected models once package access works; this bootstrap environment is not a validated model runtime. Activation explicitly loads conda and configures Hugging Face and pip caches under `/data/harshitj23/cache`. No global shell initialization changes are needed.

## Campus internet authentication

Direct internet is now working after the user authenticated using `~/authenticator.py` inside tmux. Keep that session running. Before large downloads, check `curl -fsSI --max-time 15 https://huggingface.co` and `https://pypi.org/simple/`. Before authentication, Fortinet intercepted HTTPS with an IITK hostname certificate; the explicit proxy separately requested authentication. Certificate verification remains enabled. Do not put campus passwords in this repository or SSH config.

Official proxy guidance: https://www.iitk.ac.in/cc/faq/general-faq
Miniforge: https://github.com/conda-forge/miniforge

## Files and notebooks

```sh
# From the Mac, copy a selected screenshot (avoid syncing .env files):
scp /path/to/screen.png gpu3:/data/harshitj23/screen-understanding/

# If Jupyter is installed later, run on gpu3:
jupyter lab --ip=127.0.0.1 --no-browser --port=8888

# In another Mac terminal:
ssh -N -L 8888:127.0.0.1:8888 gpu3
```

Open the token-protected Jupyter URL at localhost:8888. Keep services bound to loopback and tunnel them over SSH. Detach tmux with Ctrl-B then D; reconnect with `tmux attach -t perception`.

## Detector benchmarks completed

The isolated `/data/harshitj23/envs/detector-py310` environment reuses system PyTorch 2.0.0+cu117 read-only and installs detector dependencies locally. It uses Python 3.10 rather than the bootstrap Python 3.14 environment. The first detector dependencies were transferred from the Mac before campus internet authentication was completed.

Run with `/data/harshitj23/envs/detector-py310/bin/python benchmark_detector.py` from `/data/harshitj23/screen-understanding`. Supply `--weights models/screenparser.pt` or `models/omniparser-detector.pt`, `--image app_screenshot_raw.png`, and a fresh `--output runs/NAME`. Results and a visual comparison are saved locally under `results/`.

Checkpoint revisions: ScreenParser `f029e565f1206577402e43206454522075be3f72`; OmniParser V2 `f55d0750e5b94db2125ef0b45b0fa4a85ddc59b4`, file `icon_detect/model.pt`. Local and remote checkpoint hashes match. These runs test detectors only, not ScreenVLM or the full OmniParser OCR/caption pipeline.

## Semantic stages benchmarked (2026-10-18)

Use `/data/harshitj23/envs/perception-py311/bin/python` for OmniParser semantics. This isolated environment contains PyTorch 2.5.1+cu124, Transformers 4.49.0, EasyOCR, and Florence dependencies. It does not alter the original detector environment. Model snapshots are under `/data/harshitj23/screen-understanding/models/`; download manifests record revisions.

From `/data/harshitj23/screen-understanding`:

```sh
HF_HOME=/data/harshitj23/cache/huggingface CUDA_VISIBLE_DEVICES=0 \
/data/harshitj23/envs/perception-py311/bin/python benchmark_omni_semantics.py \
  --weights models/omniparser-detector.pt --image app_screenshot_raw.png \
  --caption models/OmniParser/icon_caption --processor models/Florence2processor \
  --upstream omniparser_upstream_utils.py --ocr-batch-size 64 \
  --output runs/CHOOSE_A_NEW_NAME
```

Default OCR batching gave 2.533 s warm median. Batch size 64 gave 1.980 s on the same screenshot, with three warm repeats. The same 80 geometry proposals were retained, with four changed text fields and changed ordering. These are not accuracy-equivalent to the richer recursive Gemini description. OCR and icon captions do not establish screen hierarchy, valid clickability, hidden state, or action outcomes.

ScreenVLM runtime compatibility is handled with a separate library overlay at `/data/harshitj23/screen-understanding/libs/screenvlm-transformers` (Transformers 4.55.2, tokenizers 0.21.4). Set `PYTHONPATH` to that directory only for ScreenVLM; leave it unset for Florence. The benchmark enables generation caching explicitly and records generation limits and truncation. Raw outputs and an inspection report are under local `results/`.

Latest assessment: [semantic-evaluation.md](results/semantic-evaluation.md), with visual inspection in [semantics.html](results/semantics.html). The checkpoint-matched ScreenVLM run (Transformers 4.55.2, SDPA, caching enabled) hit its 60-second generation bound and repeated text on this screenshot. It is not currently a successful dense parsing baseline. OmniParser OCR/caption output is measurable and faster but has documented semantic errors.
