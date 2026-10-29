from app.evaluation.lexical_diagnostic import STRATEGIES, statement


def test_candidate_diagnostics_bind_user_query_and_filter_snapshot():
    for source, path, query, boosted in STRATEGIES.values():
        compiled = statement(source, path, query, boosted)
        assert 'question' in compiled._bindparams
        assert 'repository' in compiled._bindparams
        assert 'commit' in compiled._bindparams
        sql = str(compiled)
        assert 'published AND commit_sha' in sql
        assert 'c.tenant_id' in sql and 'f.tenant_id' in sql
        assert 'LIMIT 10' in sql
