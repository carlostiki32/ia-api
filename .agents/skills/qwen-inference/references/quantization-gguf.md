# Quantization and GGUF

Running Qwen3.5-9B locally on consumer hardware means quantization. The decision is not religious — it is empirical. Measure on your task before committing.

## Quantization landscape for Qwen3.5-9B

Qwen3.5-9B ships in these distribution formats publicly:

- **Official FP16/BF16** — full precision, from the Hugging Face repos. Needs ~18 GB VRAM.
- **Ollama GGUF (Q4_K_M)** — default for `ollama pull qwen3.5:9b`, ~6.6 GB. Good default for consumer GPUs.
- **Unsloth GGUF variants** — Q2_K up to Q8_0, with extensive divergence/KL benchmarks published.
- **bitsandbytes (via Transformers)** — nf4/int8 quant on load, convenient but not competitive with GGUF for local inference throughput.
- **AWQ / GPTQ** — less common for Qwen3.5 specifically; check availability before assuming.

## Quant naming (GGUF conventions)

- **Q2_K, Q3_K, Q4_K, Q5_K, Q6_K, Q8_0** — base bit widths, increasing quality and size.
- **_S / _M / _L / _XL suffixes** — "small / medium / large / extra large" within the same base bit width, trading file size for fewer quant errors on specific tensors.
- **imatrix variants** — use an importance matrix computed from calibration data to reduce quant error on frequently-activated weights. Generally higher quality than non-imatrix at the same size.

Rough size ranking (smaller → larger → higher quality):
`Q2_K < Q3_K_S < Q3_K_M < Q4_K_S < Q4_K_M < Q4_K_L < Q5_K_M < Q6_K < Q8_0 < BF16`

## Sensible starting points

Based on the Unsloth benchmark corpus (150+ measurements of divergence/KL/PPL) and operational experience:

| Quant | Size (approx) | Use case |
|---|---|---|
| **Q4_K_M** | ~6.6 GB | Default. Good quality/size trade for 9B. Starts here unless you have a reason. |
| **Q4_K_L** | ~7 GB | Slightly better quality preserving important tensors at higher precision. Worth it if you have VRAM headroom. |
| **Q4_K_XL** | ~7.5 GB | One step further. Diminishing returns vs Q5. |
| **Q5_K_M** | ~7.7 GB | Noticeable quality lift over Q4 in reasoning tasks. Measure. |
| **Q6_K** | ~9 GB | Near-FP16 quality. Reserved for quality-critical deployments with VRAM to spare. |
| **Q8_0** | ~12 GB | Effectively lossless vs FP16 for most tasks. Use if you have the VRAM and want margin. |
| **Q3_K_M or below** | < 5 GB | Only if VRAM-constrained to the point of impossibility. Expect measurable quality loss. Test on your task. |

## VRAM budgeting

VRAM usage at runtime = model weights + KV cache + activation overhead + vision encoder (if enabled).

Approximate weights:

| Quant | Weights (GB) | Minimum realistic VRAM for reasonable context |
|---|---:|---:|
| Q4_K_M | 6.6 | 10 GB (fits on RTX 3060 12GB, 3070 8GB tight) |
| Q5_K_M | 7.7 | 12 GB |
| Q6_K | 9 | 12-16 GB |
| Q8_0 | 12 | 16 GB |
| BF16 | 18 | 24 GB |

KV cache is significant at long context. At 32K context, KV cache can be 2-4 GB extra for a 9B model. At 131K+ context, KV cache dominates — it can exceed the weight size.

Practical tuning: if VRAM is tight, **lower `num_ctx` first, before downgrading quant**. A Q4_K_M at 8K context usually outperforms a Q3_K_M at 32K context for typical tasks.

## Sensitivity to quantization

Qwen3.5-9B's hybrid architecture (Gated DeltaNet + Gated Attention) means some layer types are more quant-sensitive than others. The Unsloth benchmarks show:

- Attention layers tolerate aggressive quantization better than gated layers in some configurations.
- Imatrix variants (calibrated) noticeably help at Q3 and below; at Q5+ the difference is smaller.
- Q2_K quality degradation is not uniform across task types — reasoning and code suffer more than simple chat.

**Conclusion:** do not assume smaller = proportionally worse. Measure on your actual task distribution.

## How to measure quant quality

Don't rely on published PPL numbers alone — they don't reflect your workload. Minimum viable benchmark:

1. **Pick 20-50 representative prompts** from your actual traffic (or realistic simulations if you don't have traffic yet).
2. **Generate at your target sampling config** on the candidate quant and on a reference (Q8_0 or BF16 if you can run it briefly).
3. **Grade outputs pairwise** — blind comparison is ideal but even side-by-side inspection catches most regressions.
4. **Check task-specific metrics** — if extraction, measure extraction accuracy; if code, compile and run tests; if reasoning, check correctness on known-answer problems.

A 30-minute grading session catches quality issues that published benchmarks miss.

## Quantization on different backends

- **Ollama:** GGUF native. `ollama pull qwen3.5:9b` gets Q4_K_M. Other quants: `ollama pull qwen3.5:9b-q5_K_M` (check the Ollama library for available tags).
- **llama.cpp:** GGUF native. Direct consumption.
- **vLLM:** supports AWQ, GPTQ, FP8, INT8 natively. GGUF support is limited — for vLLM, use non-GGUF quantization schemes when possible.
- **SGLang:** similar to vLLM.
- **Transformers:** bnb 4-bit/8-bit works out of the box via `BitsAndBytesConfig`. GGUF requires auxiliary tooling.

If you start on Ollama and later want to move to vLLM, you will likely re-quantize to a different format. Budget for that migration; don't assume GGUF → vLLM is free.

## Anti-patterns

- Downloading the smallest quant available "to save disk" when you have the VRAM for a better one. The download is one-time; the quality cost is every request.
- Assuming the imatrix/non-imatrix variants are interchangeable at the same size. They're not — imatrix is almost always better.
- Trusting a single PPL number to represent "quality". PPL correlates weakly with task quality at moderate quant levels.
- Comparing quants across different quantization pipelines (e.g., Unsloth Q4_K_M vs a random uploader's Q4_K_M) as if they were equivalent. The calibration data and imatrix choices differ.
- Using aggressive quants (Q2/Q3) for clinical, legal, or code-generation workloads without extensive task-specific testing. The failure modes are subtle and easy to miss in casual testing.
