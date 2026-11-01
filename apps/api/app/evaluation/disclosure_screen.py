"""Offline screening of the pinned synthetic request; never prints source or secrets."""
from __future__ import annotations

import hashlib
import json
import re

from app.evaluation.provider_harness import EXPECTED_PATH, load_fixture, require

_PATTERNS = {
    'provider_or_github_key': rb'\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,})\b',
    'private_key': rb'-----BEGIN [A-Z ]*PRIVATE KEY-----',
    'email_address': rb'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
    'credential_header': rb'(?i)\b(?:set-cookie|authorization):\s*[^\s]+',
    'known_injection': (rb'(?i)(?:ignore previous instructions|reveal your github token|'
                        rb'change the system prompt|fetch unrelated repository data|'
                        rb'run this shell command|post the report to an external server)'),
}


def screen_exact(root, payload, manifest):
    """Screen an already reconstructed request; pattern matching is not a secrecy proof."""
    from app.evaluation.experiment_executor import canonical, digest

    _, case, source, _, file, _ = load_fixture(root)
    raw = canonical(payload)
    require(digest(raw) == manifest['request_sha256'] and digest(source) == manifest['source_sha256'],
            'screen_hash_mismatch')
    require(set(payload) == {'model', 'instructions', 'input', 'text', 'max_output_tokens',
                             'service_tier', 'prompt_cache_options', 'store', 'truncation'}
            and payload['model'] == manifest['model'] and payload['service_tier'] == 'default'
            and payload['max_output_tokens'] == 2048 and payload['prompt_cache_options'] == {'ttl': '30m'}
            and payload['store'] is False and payload['truncation'] == 'disabled', 'screen_request_mismatch')
    data = json.loads(payload['input'][0]['content'])
    require(len(payload['input']) == 1 and payload['input'][0]['role'] == 'user'
            and data['title'] == case['title'] and data['body'] == case['body']
            and not data['comments'] and not data['labels']
            and all(item['path'] == EXPECTED_PATH for item in data['evidence']), 'screen_content_mismatch')
    hits = {name: {'source': len(re.findall(pattern, source)), 'request': len(re.findall(pattern, raw))}
            for name, pattern in _PATTERNS.items()}
    require(all(not count for item in hits.values() for count in item.values()), 'screen_sensitive_pattern')
    lines = source.splitlines(keepends=True)
    ranges = []
    for start, end in ((1, 5), (6, 8)):
        part = b''.join(lines[start - 1:end])
        ranges.append({'start_line': start, 'end_line': end, 'bytes': len(part),
                       'sha256': hashlib.sha256(part).hexdigest()})
    return {'status': 'pattern_screen_passed; human review and current billing confirmation required',
        'source_path': EXPECTED_PATH, 'source_blob': file.blob_sha, 'source_sha256': digest(source),
        'source_ranges': ranges, 'request_sha256': digest(raw),
        'manifest_sha256': digest(canonical(manifest)), 'instructions_sha256': digest(payload['instructions'].encode()),
        'output_schema_sha256': digest(canonical(payload['text']['format']['schema'])),
        'request_fields': sorted(payload), 'input_fields': sorted(data), 'issue_title': case['title'],
        'title_sha256': digest(data['title'].encode()), 'body_sha256': digest(data['body'].encode()),
        'screened_patterns': hits, 'evidence': manifest['evidence'],
        'limitations': ['Pattern screening cannot prove that arbitrary secrets or injection are absent.',
                        'The authorization header value and provider-internal processing are not reviewed here.',
                        'Exact request and source disclosure require human review before any paid approval.']}
