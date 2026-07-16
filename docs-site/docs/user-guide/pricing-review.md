# Pricing Review

Pricing Review is a global workspace opened from the dashboard. It does not require a
twin because refresh credentials and cached provider pricing are account-level state.

## Provider-By-Provider Refresh

AWS, Azure, and GCP refresh independently. This keeps slow or failing providers from
blocking review of the others and makes the credential/account context explicit.

Before an authenticated refresh, the confirmation shows which stored pricing connection
and cloud scope will be used. A missing or invalid AWS/GCP default disables that
provider refresh with a recovery path to Cloud Accounts. Azure catalog refresh uses
the unauthenticated public Retail Prices API and therefore shows the requested pricing
region rather than an account credential.

## Status

Provider cards distinguish fresh, stale, review-required, unavailable, and active
refresh states. They show age/max age, selected account metadata, and latest run.

## Evidence Details

Collapsed details expose the full decision path without overwhelming the default view:

- pricing intent and expected canonical unit;
- source classification and provider query dimensions;
- selected raw row/value;
- accepted and rejected candidates with reasons;
- normalization/build path;
- contract and publication status;
- latest refresh run and errors.

Azure tier-series evidence includes every selected `tierMinimumUnits` row and the
normalized absolute-limit table. Rejected routing preferences, reservation products,
storage products, SKUs, and meters are bounded and remain available with reasons.

## Review Decision

When one candidate is deterministic and publishable, it can flow into generated
pricing. When candidates are ambiguous, alternatives remain visible and the user
records a reviewed selection.

The stored decision selects a mapping; it does not overwrite provider prices. The
candidate contract already has a typed `ai_suggestion` field so a future advisory
reviewer can be added without changing the UI contract. The current runtime does not
call OpenAI and reports AI review as disabled. Deterministic logic and manual review are
the implemented path.

Fallback values are diagnostic emergency exits, not the target state and not
publishable cost inputs.
