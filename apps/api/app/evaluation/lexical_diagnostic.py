"""Read-only operator diagnostic for the pinned public repository; no source is emitted."""
import json
from pathlib import Path

from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.evaluation.retrieval import measure_query

# Fixed strategies; user questions are always bound parameters, never SQL fragments.
BASE = """to_tsvector('simple', coalesce(c.symbol, '') || ' ' || c.source_text)"""
PATH = """to_tsvector('simple', f.path)"""
ENGLISH = """to_tsvector('english', replace(coalesce(c.symbol, '') || ' ' || c.source_text, '_', ' '))"""
EPATH = """to_tsvector('english', replace(f.path, '_', ' '))"""
STRATEGIES = {
    'baseline': (BASE, PATH, "plainto_tsquery('simple', :question)", False),
    'english_or': (ENGLISH, EPATH,
                   "replace(plainto_tsquery('english', replace(:question, '_', ' '))::text, ' & ', ' | ')::tsquery", False),
    'english_or_boost': (ENGLISH, EPATH,
                         "replace(plainto_tsquery('english', replace(:question, '_', ' '))::text, ' & ', ' | ')::tsquery", True),
}


def statement(source, path, query, boosted):
    boost = " + CASE WHEN lower(coalesce(c.symbol, '')) = lower(trim(:question)) THEN 5.0 ELSE 0 END" if boosted else ""
    score = f"ts_rank_cd({source}, q.q) + ts_rank_cd({path}, q.q){boost}"
    return text(f"""
        WITH q AS (SELECT {query} AS q), matches AS (
          SELECT c.symbol, c.start_line, c.end_line, f.path, s.published, s.commit_sha,
                 c.id, {score} AS score
          FROM code_chunks c
          JOIN indexed_files f ON f.id = c.file_id AND f.tenant_id = c.tenant_id AND f.repository_id = c.repository_id
          JOIN code_snapshots s ON s.id = f.snapshot_id AND s.tenant_id = f.tenant_id AND s.repository_id = f.repository_id
          JOIN repositories r ON r.id = s.repository_id AND r.tenant_id = s.tenant_id CROSS JOIN q
          WHERE r.full_name = :repository AND r.enabled AND numnode(q.q) > 0
            AND ({source} @@ q.q OR {path} @@ q.q)
        )
        SELECT ranked.path, ranked.symbol, ranked.start_line, ranked.end_line, ranked.score,
          counts.repository_history_matches, counts.published_matches, (SELECT numnode(q) FROM q) AS query_nodes
        FROM (SELECT count(*) AS repository_history_matches,
                     count(*) FILTER (WHERE published AND commit_sha = :commit) AS published_matches
              FROM matches) AS counts
        LEFT JOIN LATERAL (SELECT path, symbol, start_line, end_line, score, id FROM matches
                           WHERE published AND commit_sha = :commit
                           ORDER BY score DESC, path, start_line, id LIMIT 10) AS ranked ON true
        ORDER BY ranked.score DESC, ranked.path, ranked.start_line, ranked.id
    """)


def main():
    dataset = json.loads(Path('evaluation/repopilot-6349190.json').read_text())
    if dataset['repository'] != 'roshan-pandit1/RepoPilot' or dataset['commit_sha'] != '63491908290e6874dbaaf2b15c2a96473aad1324':
        raise SystemExit('Unexpected benchmark')
    engine = create_engine(get_settings().database_url, hide_parameters=True)
    output = {'repository': dataset['repository'], 'commit': dataset['commit_sha'], 'strategies': {}}
    with engine.connect() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        connection.execute(text("SET LOCAL statement_timeout = '3s'"))
        counts = connection.execute(text("""SELECT count(*) AS chunks FROM code_chunks c
          JOIN indexed_files f ON f.id = c.file_id AND f.repository_id = c.repository_id AND f.tenant_id = c.tenant_id
          JOIN code_snapshots s ON s.id = f.snapshot_id AND s.repository_id = f.repository_id AND s.tenant_id = f.tenant_id
          JOIN repositories r ON r.id = s.repository_id AND r.tenant_id = s.tenant_id
          WHERE r.full_name = :repository AND r.enabled AND s.published AND s.commit_sha = :commit"""),
          {'repository': dataset['repository'], 'commit': dataset['commit_sha']}).scalar_one()
        output['published_chunks'] = counts
        if counts != 278:
            raise SystemExit('Published snapshot does not match expected chunk count')
        for name, (src, path, query, boosted) in STRATEGIES.items():
            rows = []
            stmt = statement(src, path, query, boosted)
            for question in dataset['queries']:
                params = {'question': question['question'], 'repository': dataset['repository'], 'commit': dataset['commit_sha']}
                result = connection.execute(stmt, params).mappings().all()
                labels = [dict(item) for item in result if item['path'] is not None]
                metrics = measure_query(question['relevance'], labels)
                rows.append({'id': question['id'], 'returned': len(labels),
                    'history_matches': result[0]['repository_history_matches'],
                    'snapshot_matches': result[0]['published_matches'], 'query_nodes': result[0]['query_nodes'],
                    'relevant_ranks': metrics['relevant_ranks']})
            output['strategies'][name] = rows
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
