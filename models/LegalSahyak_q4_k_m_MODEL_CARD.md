---
language:
- en
library_name: llama-cpp-python
tags:
- legal
- india
- gguf
- quantized
- rag
- llama-3.1
pipeline_tag: text-generation
base_model: unsloth/Meta-Llama-3.1-8B-Instruct
license: other
---

# LegalSahyak (Q4_K_M GGUF)

## Model Description
`LegalSahyak_q4_k_m.gguf` is a quantized GGUF model intended for local legal question answering workflows, especially when paired with retrieval over contracts and Indian statutes.

- Base model: `unsloth/Meta-Llama-3.1-8B-Instruct`
- Adaptation: LoRA fine-tuning (rank `r=128`) and merge
- Quantization: `q4_k_m` GGUF
- Primary runtime target: `llama.cpp` / `llama-cpp-python`

## Intended Use
- Contract clause explanation and extraction
- Statute-grounded legal QA in a retrieval-augmented (RAG) pipeline
- Local/offline inference where low memory usage is needed

This model should be used with retrieval and human review for any high-stakes legal scenario.

## Out-of-Scope Use
- Autonomous legal advice without human oversight
- Any use requiring guaranteed legal correctness or jurisdictional completeness
- Sensitive decisions where model hallucinations can cause harm

## Training Data
The training pipeline in `models/train.py` uses two public datasets:

1. `Prarabdha/indian-legal-supervised-fine-tuning-data`
2. `opennyaiorg/aalap_instruction_dataset`

Training was performed in two stages:

1. Knowledge injection on legal supervised examples
2. Behavioral alignment on instruction-following data

## Training Procedure (Summary)
- Context length: up to `8192`
- Precision during training: `bfloat16`
- LoRA target modules: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`
- Optimizer: `adamw_8bit`
- Scheduler: cosine
- Export: merged weights -> GGUF quantized as `q4_k_m`

## Inference
Example with `llama-cpp-python`:

```python
from llama_cpp import Llama

llm = Llama(
    model_path="LegalSahyak_q4_k_m.gguf",
    n_ctx=4096,
    n_gpu_layers=20,
    verbose=False,
)

resp = llm.create_chat_completion(
    messages=[
        {"role": "system", "content": "You are a legal assistant. Use provided context only."},
        {"role": "user", "content": "Explain the notice period clause in simple words."},
    ],
    max_tokens=512,
    temperature=0.0,
)

print(resp["choices"][0]["message"]["content"])
```

## Model File Details
- Filename: `LegalSahyak_q4_k_m.gguf`
- Size (bytes): `4920738464`
- Approx size: `4.58 GiB`
- SHA256: `F32460DD8E7DC927B3CF33065D1E753FC1F85ED102A678512C8A5F520F544405`

## Limitations
- Can produce plausible but incorrect legal text
- Performance depends heavily on retrieval quality and prompt constraints
- May not reflect the latest statutory amendments
- Not a substitute for licensed legal counsel

## Bias, Risk, and Safety
- Dataset and model biases may propagate into outputs
- Should not be used as the sole basis for legal, compliance, or policy decisions
- Recommended controls:
  - Ground responses in retrieved sources
  - Log model outputs and review manually
  - Add refusal/uncertainty handling when context is missing



## Citation
If you use this model in research or products, cite:

- The base model (`Meta-Llama-3.1`)
- The datasets listed above
- This repository (`Legalsahyak`)
