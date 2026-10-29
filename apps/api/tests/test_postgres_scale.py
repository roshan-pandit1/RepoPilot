from app.evaluation.postgres_scale import percentile, query_sql, validate_database_name


def test_scale_guard_requires_named_disposable_database():
    assert validate_database_name('repopilot_test_scale_123')
    assert not validate_database_name('repopilot')
    assert not validate_database_name('repopilot_test_')
    assert not validate_database_name('repopilot_test_a;drop')


def test_scale_query_is_parameterized_and_has_authorization_filters():
    sql = query_sql('perf_files_1000', 'perf_chunks_1000')
    assert 'query' in sql._bindparams
    assert 'c.tenant_id = 1' in str(sql) and 'f.snapshot_id = 1' in str(sql)
    assert 'LIMIT 30' in str(sql)
    assert percentile([1, 2, 3, 4], .95) == 4
    assert percentile([], .95) is None
