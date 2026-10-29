"""Disposable-PostgreSQL synthetic search plan benchmark. Never run on application data."""
import json
import math
import os
import re
import statistics
import time

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

SIZES = (1000, 10000, 50000)
QUERIES = ('verify_webhook_signature', 'repository authorization webhook', 'where is source processing handled')
REPETITIONS = 12


def percentile(values, fraction):
    if not values:
        return None
    return round(sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)], 3)


def validate_database_name(database):
    return bool(database and re.fullmatch(r'repopilot_test_[a-zA-Z0-9_]+', database))


def query_sql(files, chunks):
    source = "to_tsvector('english', replace(coalesce(c.symbol, '') || ' ' || c.source_text, '_', ' '))"
    path = "to_tsvector('english', replace(f.path, '_', ' '))"
    q = "replace(plainto_tsquery('english', replace(:query, '_', ' '))::text, ' & ', ' | ')::tsquery"
    score = f"ts_rank_cd({source}, q.query) + ts_rank_cd({path}, q.query) + CASE WHEN lower(c.symbol) = lower(trim(:query)) THEN 5.0 ELSE 0 END"
    return text(f"""SELECT c.id, c.symbol FROM {chunks} c JOIN {files} f ON c.file_id = f.id
      CROSS JOIN (SELECT {q} AS query) q
      WHERE c.tenant_id = 1 AND c.repository_id = 1 AND f.tenant_id = 1 AND f.repository_id = 1
        AND f.snapshot_id = 1 AND ({source} @@ q.query OR {path} @@ q.query)
      ORDER BY {score} DESC, f.path, c.start_line, c.id LIMIT 30""")


def plan_nodes(plan):
    nodes = []
    def walk(node):
        nodes.append({k: node[k] for k in ('Node Type', 'Index Name', 'Actual Rows', 'Rows Removed by Filter',
            'Sort Method', 'Sort Space Used', 'Sort Space Type', 'Shared Hit Blocks', 'Shared Read Blocks',
            'Local Hit Blocks', 'Local Read Blocks', 'Temp Read Blocks', 'Temp Written Blocks') if k in node})
        for child in node.get('Plans', []):
            walk(child)
    walk(plan['Plan'])
    return nodes


def run():
    url = os.environ.get('PERF_DATABASE_URL', '')
    if not url:
        raise SystemExit('A dedicated repopilot_test_* PostgreSQL database is required')
    parsed = make_url(url)
    if parsed.get_backend_name() != 'postgresql' or not validate_database_name(parsed.database):
        raise SystemExit('A dedicated repopilot_test_* PostgreSQL database is required')
    engine = create_engine(url, hide_parameters=True)
    report = {'method': 'Generated temporary tables; C2 lexical expressions; not application data.',
              'sizes': [], 'queries': list(QUERIES), 'repetitions_per_query': REPETITIONS,
              'cpu_memory': 'Not measured; EXPLAIN sort memory and buffers reported when available.',
              'p99': 'Not reported: fewer than 100 samples per condition.', 'paid_calls': 0}
    with engine.connect() as conn:
        for size in SIZES:
            files, chunks = f'perf_files_{size}', f'perf_chunks_{size}'
            conn.exec_driver_sql(f'CREATE TEMP TABLE {files} (id integer PRIMARY KEY, tenant_id integer NOT NULL, repository_id integer NOT NULL, snapshot_id integer NOT NULL, path text NOT NULL)')
            conn.exec_driver_sql(f'CREATE TEMP TABLE {chunks} (id integer PRIMARY KEY, file_id integer NOT NULL, tenant_id integer NOT NULL, repository_id integer NOT NULL, symbol text NOT NULL, source_text text NOT NULL, start_line integer NOT NULL)')
            conn.exec_driver_sql(f"""INSERT INTO {files} SELECT n, CASE WHEN mod(n, 10) = 0 THEN 2 ELSE 1 END,
                CASE WHEN mod(n, 10) = 0 THEN 2 ELSE 1 END, CASE WHEN mod(n, 10) = 1 THEN 2 ELSE 1 END,
                'src/module_' || n || '/handler.py' FROM generate_series(1, {size // 10}) n""")
            conn.exec_driver_sql(f"""INSERT INTO {chunks} SELECT n, ((n - 1) / 10) + 1,
                CASE WHEN mod(((n - 1) / 10) + 1, 10) = 0 THEN 2 ELSE 1 END,
                CASE WHEN mod(((n - 1) / 10) + 1, 10) = 0 THEN 2 ELSE 1 END,
                CASE WHEN mod(n, 200) = 42 THEN 'verify_webhook_signature' ELSE 'handle_record_' || n END,
                CASE WHEN mod(n, 200) = 42 THEN 'def verify_webhook_signature(raw): return verify_signature(raw)'
                     WHEN mod(n, 13) = 0 THEN 'def handle_record(): authorize repository access and process webhook'
                     ELSE 'def handle_record(): process generated source record' END, mod(n - 1, 10) + 1
                FROM generate_series(1, {size}) n""")
            conn.exec_driver_sql(f'CREATE INDEX ON {chunks} (tenant_id, repository_id)')
            conn.exec_driver_sql(f"CREATE INDEX ON {chunks} USING gin (to_tsvector('simple', coalesce(symbol, '') || ' ' || source_text))")
            conn.exec_driver_sql(f"CREATE INDEX ON {files} USING gin (to_tsvector('simple', path))")
            conn.exec_driver_sql(f'ANALYZE {files}')
            conn.exec_driver_sql(f'ANALYZE {chunks}')
            conn.commit()
            eligible = conn.exec_driver_sql(f'SELECT count(*) FROM {chunks} c JOIN {files} f ON c.file_id=f.id WHERE c.tenant_id=1 AND c.repository_id=1 AND f.snapshot_id=1').scalar_one()
            entry = {'total_chunks': size, 'eligible_published_chunks': eligible, 'conditions': {}}
            saved_results = {}
            stmt = query_sql(files, chunks)
            for condition in ('existing_indexes', 'candidate_english_gin'):
                build_seconds = 0.0
                if condition == 'candidate_english_gin':
                    start = time.perf_counter()
                    conn.exec_driver_sql(f"CREATE INDEX perf_english_chunks_{size} ON {chunks} USING gin (to_tsvector('english', replace(coalesce(symbol, '') || ' ' || source_text, '_', ' ')))")
                    conn.exec_driver_sql(f"CREATE INDEX perf_english_paths_{size} ON {files} USING gin (to_tsvector('english', replace(path, '_', ' ')))")
                    conn.commit()
                    build_seconds = time.perf_counter() - start
                    conn.exec_driver_sql(f'ANALYZE {files}')
                    conn.exec_driver_sql(f'ANALYZE {chunks}')
                    conn.commit()
                latencies, timeouts, plans = [], 0, {}
                for query in QUERIES:
                    try:
                        with conn.begin_nested():
                            conn.exec_driver_sql("SET LOCAL statement_timeout = '3s'")
                            raw = conn.execute(text('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + str(stmt)), {'query': query}).scalar_one()
                            plans[query] = {'planning_ms': raw[0]['Planning Time'], 'execution_ms': raw[0]['Execution Time'], 'nodes': plan_nodes(raw[0])}
                    except DBAPIError as exc:
                        if getattr(exc.orig, 'sqlstate', None) != '57014':
                            raise
                        plans[query] = {'timeout': True}
                    for _ in range(REPETITIONS):
                        start = time.perf_counter()
                        try:
                            with conn.begin_nested():
                                conn.exec_driver_sql("SET LOCAL statement_timeout = '3s'")
                                result = [(r.id, r.symbol) for r in conn.execute(stmt, {'query': query})]
                            latencies.append((time.perf_counter() - start) * 1000)
                            if query == 'verify_webhook_signature' and (not result or result[0][1] != query):
                                raise RuntimeError('Exact-symbol result correctness failed')
                            if condition == 'existing_indexes':
                                saved_results.setdefault(query, result)
                                if saved_results[query] != result:
                                    raise RuntimeError('Unstable result ordering')
                            elif query in saved_results and saved_results[query] != result:
                                raise RuntimeError('Candidate index changed result ordering')
                        except DBAPIError as exc:
                            if getattr(exc.orig, 'sqlstate', None) != '57014':
                                raise
                            timeouts += 1
                index_rows = conn.execute(text("""SELECT indexname, pg_relation_size(CAST(format('%I.%I', schemaname, indexname) AS regclass)) AS bytes
                    FROM pg_indexes WHERE schemaname = pg_my_temp_schema()::regnamespace::text AND tablename IN (:files, :chunks)"""), {'files': files, 'chunks': chunks}).all()
                entry['conditions'][condition] = {'sample_count': len(latencies), 'timeout_count': timeouts,
                    'latency_p50_ms': percentile(latencies, .5), 'latency_p95_ms': percentile(latencies, .95),
                    'mean_ms': round(statistics.mean(latencies), 3) if latencies else None,
                    'index_build_seconds': round(build_seconds, 3),
                    'indexes': [{'name': row.indexname, 'bytes': row.bytes} for row in index_rows],
                    'plans': plans, 'correctness': 'passed for comparable completed queries',
                    'reference_queries_available': len(saved_results)}
                conn.commit()
            report['sizes'].append(entry)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    run()
