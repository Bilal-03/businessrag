# P2-03 observability dashboard specification

This document is the source of truth for the privacy-safe PostHog dashboards used by BizGuide. The browser client sends only the explicitly allow-listed events from `web/src/lib/observability.js`.

## Privacy contract

Never add prompts, answers, document contents, snippets, filenames, access tokens, refresh tokens, email addresses, phone numbers, or arbitrary UI state to analytics events. The event property allow-list is intentionally small and should stay that way. Sentry is for exceptions; PostHog is for aggregate product behavior.

## Recommended dashboards

### Activation funnel

Create a funnel with unique users and a 14-day conversion window:

1. `auth_completed` where `mode = sign_up`
2. `workspace_viewed` where `view = businesses`
3. `business_created`
4. `workspace_viewed` where `view = upload`
5. `upload_queued` or `upload_indexed`
6. `chat_completed`

This measures the path from account creation to a first useful, source-aware answer. Keep `upload_queued` and `upload_indexed` as separate breakdowns so queue latency is visible without treating a queued document as indexed.

### Chat reliability and grounding

Use a trends dashboard with:

- `chat_submitted` — demand
- `chat_completed` — successful responses
- `chat_failed` — failures
- `chat_completed` broken down by `grounding` — source-backed versus general answers
- `chat_completed` broken down by `streamed` — streaming adoption
- `chat_completed` broken down by `duration` — latency buckets (`<1s`, `1-3s`, `3-10s`, `10s+`)

Do not chart raw query text. The client sends only bounded history count, an input-length bucket, grounding state, citation count, streaming state, and duration bucket.

### Document ingestion health

Track:

- `upload_started` by `size` and `has_active_business`
- `upload_rejected` by `reason`
- `upload_queued` versus `upload_indexed`
- `document_processing_completed`
- `document_processing_failed`
- `upload_failed` by `reason` or HTTP `status`

Use a 7-day trend for processing failures and a table for rejection reasons. Do not include the uploaded file name.

### Workspace engagement

Track:

- `workspace_viewed` by `view`
- `business_selected`
- `business_created`, `business_updated`, `business_deleted`
- `workflow_task_created`, `workflow_task_updated`, `workflow_task_deleted`

The most useful retention proxy is the percentage of new users who return and produce either `chat_completed`, `upload_indexed`, or `workflow_task_created` within 7 days.

## Suggested saved insights

| Insight | Type | Primary event | Breakdown |
| --- | --- | --- | --- |
| Activation funnel | Funnel | `auth_completed` | `mode` |
| Daily active workspaces | Trends | `workspace_viewed` | `view` |
| Chat success rate | Trends/formula | `chat_completed` and `chat_failed` | `grounding` |
| Source-backed answer share | Trends | `chat_completed` | `grounding` |
| Upload processing outcomes | Trends | `document_processing_completed` / `document_processing_failed` | none |
| Task adoption | Trends | `workflow_task_created` | none |
| Seven-day activation retention | Retention | `auth_completed` | `mode = sign_up` |

## Release acceptance checks

- Verify events are visible in PostHog Live Events after a production canary.
- Verify no event contains a prompt, answer, document name/content, token, email, or arbitrary object.
- Keep autocapture, pageview capture, and session recording disabled unless a new privacy review explicitly approves them.
- Review dashboard volume weekly against the free-tier quota before adding new events.
