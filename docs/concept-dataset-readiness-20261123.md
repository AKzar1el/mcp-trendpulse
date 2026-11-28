# Prompt-injection benchmark readiness (2026-11-23)

No gated datasets, labels, screenshots, benchmark samples or paid APIs were downloaded.

| Dataset/repository | Latest provider modification | Rights and access | Decision |
| --- | --- | --- | --- |
| NotInject (Hugging Face leolee99/NotInject) | 2025-04-04, official Hub metadata | Public/ungated, MIT | GO for a small static benign false-positive evaluation, pin a revision and attribute |
| BrowseSafe++ (perplexity-ai/browsesafe-plus-plus) | 2026-11-03, official Hub metadata | Gated auto, mixed: train CC BY 4.0; test evaluation-only; SDK MIT | CONDITIONAL GO for train split after user accepts HF access; never redistribute test inputs |
| AgentDojo (ethz-spylab/agentdojo) | Latest GitHub push 2026-06-02 | MIT, public, not archived | GO as reusable research/evaluation harness; do not assume browser-specific tasks or free model execution |

NotInject: small/older public dataset of benign text that resembles prompt-injection instructions. A static benchmark need not be actively updated every week, but it does not establish current attack prevalence.

BrowseSafe++: official 38,675 paired pages across 24 attack types; 29,500 training pairs and 9,175 held-out test pairs. Public card reports gated access and license=other; training material uses CC BY 4.0, test inputs have separate evaluation-only restrictions. Accessing gated content requires the user's explicit account acceptance. Never upload protected data to a public repo.

AgentDojo: public MIT library has valid 2026 development, but most recent main push was June 2, 2026, so it is not a weekly-updated dataset; dependencies and paid LLM calls are separate concerns.

Source integration discovery: the full BrowseSafe++ metadata response exceeded TrendPulse's established 256 KiB safety ceiling. The optional collector was repaired by requesting only documented Hugging Face metadata fields using its expand[] API. This returned the 2026-11-03 date, gating status and license card without downloading sample rows. All other collectors retain their safety caps.

Usage strategy: pin dataset versions, disclose sources and licenses; use NotInject benign examples now, evaluate with AgentDojo offline fixtures, and only use BrowseSafe++ training examples after the user accepts its actual terms. Do not use test labels as training or tuning data. Source dates are not proof of user demand.

Sources:
- https://huggingface.co/datasets/leolee99/NotInject
- https://browsesafe.perplexity.ai/
- https://huggingface.co/datasets/perplexity-ai/browsesafe-plus-plus
- https://github.com/perplexityai/browsesafe-plus-plus/blob/main/LICENSE.md
- https://github.com/ethz-spylab/agentdojo
- https://huggingface.co/docs/huggingface_hub/main/en/package_reference/hf_api
