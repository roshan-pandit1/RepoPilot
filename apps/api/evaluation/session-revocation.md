# Exposed session response

The authenticated, CSRF-protected Sign out operation sets `revoked_at`, clears the stored
encrypted GitHub token, and removes browser cookies. Session lookup hashes the presented cookie
and rejects rows that are revoked or expired. Signing out only revokes the current browser's
session. The API does not have a built-in sign-out-all-sessions action.

Sign out in each accessible browser session, then check the account-wide counts below. If an
affected session is inaccessible and there are still active sessions, an operator can revoke all
currently active sessions for this account. This logs out **all** active RepoPilot sessions for
that account, including legitimate sessions; obtain explicit account-owner approval first. It
does not revoke GitHub OAuth grants, rotate GitHub App credentials, delete records or disclose
session hashes. The `login` filter must identify exactly the intended user before applying it.

```sh
docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
BEGIN;
WITH revoked AS (
  UPDATE auth_sessions s SET revoked_at = now(), github_token_ciphertext = ''
  FROM users u
  WHERE s.user_id = u.id AND u.login = 'roshan-pandit1'
    AND s.revoked_at IS NULL AND s.expires_at > now()
  RETURNING 1
)
SELECT count(*) AS sessions_revoked FROM revoked;
COMMIT;
SQL
```

Use the read-only count query in `docs/verification.md` or below before and after. If `active`
is zero for the correct account, no unexpired non-revoked session for that account remains.
This verifies account-wide state without identifying or displaying the exposed sessions. An
unauthenticated `/v1/auth/me` returning 401 alone only verifies an absent session; it does not
prove revocation of a particular previously issued session. Automated fixture tests separately
verify replay of a revoked session is rejected.

```sh
docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
SELECT count(*) FILTER (WHERE s.revoked_at IS NULL AND s.expires_at > now()) AS active,
       count(*) FILTER (WHERE s.revoked_at IS NOT NULL) AS revoked,
       count(*) FILTER (WHERE s.revoked_at IS NULL AND s.expires_at <= now()) AS expired
FROM auth_sessions s JOIN users u ON u.id = s.user_id
WHERE u.login = 'roshan-pandit1';
SQL
```
