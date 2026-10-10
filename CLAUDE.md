# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This is an India water-crisis intelligence platform (drought, flood, heat) for the WeMakeDevs × AWS Environmental Hacks hackathon (Heat and Water track, ends 2026-10-11). **"Jal" is only the folder name.** The product name is undecided, so keep it in a single config string and don't hard-code it.

The approved design is [docs/superpowers/specs/2026-10-10-mvp-design.md](docs/superpowers/specs/2026-10-10-mvp-design.md). It covers scope, AWS architecture, schema, the intelligence-layer robustness rules and the build order. Read it before building anything. Add **Commands** and **Architecture** sections here once code exists.

Standing decisions:
- **LLM:** use the low-cost model, Claude Haiku 5.5 on Bedrock (`anthropic.claude-haiku-5-5`), via the `AnthropicBedrockMantle` client.
- **AWS:** the CLI `default` profile (account ending 9175), region **ap-south-1** (Mumbai). Bedrock access was verified on 2026-10-10: Haiku 5.5 answers through the inference profile `global.anthropic.claude-haiku-5-5` (Converse API). If the Mantle client is refused in ap-south-1, fall back to the legacy `AnthropicBedrock` client with that profile ID. The Sydney account (ending 6709) is **not** used.
- **The AI writes the words; code does the arithmetic.** Every number in briefs and plans comes from code.
- **Evidence quotes must be verbatim substrings** of the source post.
- **AWS:** the services listed in the spec. Redis, SES and a second Step Functions machine were deliberately dropped; the spec says why.

## References

[docs/references/](docs/references/) holds resources the user shares: hackathon rules, prior projects to borrow from, and data sources. Read the relevant file before designing or building. When the user shares a new link or repo, condense it into a new file there.

## Workflow: always go through the planning skills

Use the installed skills for every piece of work, and invoke each one before acting, including before clarifying questions. Default pipeline:

1. **`superpowers:brainstorming`**: for any new idea, feature or change in behaviour. It narrows scope and produces an approved design. For a hackathon, push hard on what the demo actually needs and cut everything else.
2. **`superpowers:writing-plans`**: turns the approved design into small, ordered tasks before any code is written.
3. **`superpowers:subagent-driven-development`** (or `superpowers:executing-plans` when working inline): carries out the plan.
4. **`superpowers:test-driven-development`** while implementing, and **`superpowers:systematic-debugging`** for any bug or failure.
5. **`superpowers:verification-before-completion`** before claiming anything works. Run it and show the output.

Alternatives (these overlap with the pipeline above, so pick one per task and don't stack them):
- **`spec-driven-development`**: use when you want lasting `requirements.md` / `design.md` / `tasks.md` docs, for example for judges or teammates.
- **`claude-mem:make-plan`** then **`claude-mem:do`**: a phased plan executed by subagents, as an alternative to steps 2–3.

UI work: **`frontend-design:frontend-design`** and **`ui-ux-pro-max:ui-ux-pro-max`**. Code review before submission: **`superpowers:requesting-code-review`** / **`code-review`**.

<!-- BEGIN AWS Agent Toolkit rules -->
# AWS Guidance

- Where these AWS rules conflict with the project's own instructions, the
  project's instructions take precedence.
- Prefer the AWS MCP Server for AWS interactions — it provides sandboxed
  execution, observability, and audit logging. If unavailable, use the
  AWS CLI directly.
- Before starting a task, check whether a relevant AWS skill is available.
  Load the skill with `retrieve_skill` and prefer its guidance over
  general knowledge.
- When uncertain about specific AWS details (API parameters, permissions,
  limits, error codes), verify against documentation rather than guessing.
  State uncertainty explicitly if you cannot confirm.
- When creating infrastructure, prefer infrastructure-as-code (AWS CDK or
  CloudFormation) over direct CLI commands.
- When working with infrastructure, follow AWS Well-Architected Framework
  principles.
- Do not use em dashes in AWS resource names or descriptions. Use
  hyphens instead.

## Secret Safety

- MUST load the `aws-secrets-manager` skill first for any secret,
  credential, API key, token, or password task. MUST NOT call
  `secretsmanager get-secret-value` or `batch-get-secret-value`, and MUST
  NOT hit the Secrets Manager Agent daemon directly. MUST use
  `{{resolve:secretsmanager:secret-id:SecretString:json-key}}` with
  `asm-exec` so the secret resolves at runtime without entering context.
<!-- END AWS Agent Toolkit rules -->
