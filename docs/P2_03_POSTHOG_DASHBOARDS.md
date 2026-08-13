# P2-03 PostHog dashboard build sheet

The application-side analytics contract is implemented and documented in
[`P2_03_OBSERVABILITY.md`](./P2_03_OBSERVABILITY.md). This file is the exact
external setup checklist for the PostHog project. It intentionally does not
include raw prompts, answers, filenames, document text, tokens, or email data.

## Create these saved insights

In PostHog, open **Insights → New insight**, use the event names below, save the
insight with the exact title, then add it to a dashboard named **BizGuide P2-03
Product Health**.

| Saved insight | Insight type | Events / filters | Useful breakdown |
| --- | --- | --- | --- |
| Activation funnel | Funnel | `auth_completed` (`mode = sign_up`) → `workspace_viewed` (`view = businesses`) → `business_created` → `workspace_viewed` (`view = upload`) → `upload_queued` → `chat_completed` | `mode` on first step; 14-day conversion window |
| Activation: indexed path | Funnel | Same first four steps, then `upload_indexed` → `chat_completed` | Compare against queued path |
| Chat request volume | Trends | `chat_submitted` | Daily/weekly |
| Chat outcomes | Trends | `chat_completed`, `chat_failed` | Event name |
| Source-backed answer share | Trends | `chat_completed` | `grounding` |
| Chat latency | Trends | `chat_completed` | `duration` |
| Upload outcomes | Trends | `upload_started`, `upload_queued`, `upload_indexed`, `upload_failed` | Event name |
| Upload rejection reasons | Trends | `upload_rejected` | `reason` |
| Ingestion processing health | Trends | `document_processing_completed`, `document_processing_failed` | Event name |
| Workspace engagement | Trends | `workspace_viewed`, `business_selected`, `workflow_task_created` | Event name / `view` |
| Seven-day activation retention | Retention | First: `auth_completed` (`mode = sign_up`); returning: `chat_completed` or `upload_indexed` or `workflow_task_created` | 7-day retention |

## Dashboard acceptance checks

- [ ] All 11 insights are saved and added to **BizGuide P2-03 Product Health**.
- [ ] The activation funnel uses unique users and a 14-day conversion window.
- [ ] Trends use daily intervals and a 7-day default date range.
- [ ] `chat_completed` is broken down by `grounding`, `streamed`, and `duration` in the relevant charts.
- [ ] Upload outcomes and processing health are separate charts so queue success is not mistaken for indexing success.
- [ ] Live Events shows the expected event names after one production canary flow.
- [ ] Inspect one event payload and verify it contains no prompt, answer, document filename/content/snippet, token, email, or arbitrary object.
- [ ] Verify PostHog autocapture, pageview capture, and session recording remain disabled.

## Current status

The source contract and this build sheet are complete. The actual dashboard
objects are an external PostHog project action and cannot be honestly marked
complete from this coding workspace until the project is opened while signed
in and the checklist above is checked off.
