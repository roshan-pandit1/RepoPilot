"""Validate resolved Compose settings without printing credentials or changing services."""
import json
import subprocess
import sys
from urllib.parse import urlsplit


def check():
    config = json.load(sys.stdin)
    assert config['name'] == 'repopilot-local'
    for key, expected in (('postgres-data', 'repopilot-local_postgres-data'),
                          ('redis-data', 'repopilot-local_redis-data')):
        assert config['volumes'][key]['external'] is True
        assert config['volumes'][key]['name'] == expected
    services = config['services']
    assert services['postgres']['environment']['POSTGRES_DB'] == 'repopilot'
    inspection = subprocess.run(['docker', 'inspect', 'repopilot-local-api-1'],
                                capture_output=True, text=True, check=True)
    running = json.loads(inspection.stdout)[0]
    assert running['Config']['Labels']['com.docker.compose.project'] == 'repopilot-local'
    inspected_pg = subprocess.run(['docker', 'inspect', 'repopilot-local-postgres-1'],
                                  capture_output=True, text=True, check=True)
    postgres = json.loads(inspected_pg.stdout)[0]
    assert postgres['Config']['Labels']['com.docker.compose.project'] == 'repopilot-local'
    assert postgres['Config']['Labels']['com.docker.compose.service'] == 'postgres'
    assert any(mount['Name'] == 'repopilot-local_postgres-data'
               and mount['Destination'] == '/var/lib/postgresql/data'
               for mount in postgres['Mounts'] if mount['Type'] == 'volume')
    assert postgres['State']['Running']
    assert any(item['source'] == 'postgres-data' and item['target'] == '/var/lib/postgresql/data'
               for item in services['postgres']['volumes'])
    old_env = dict(item.split('=', 1) for item in running['Config']['Env'] if '=' in item)
    paid = {'INVESTIGATION_PROVIDER': 'mock', 'INVESTIGATION_REAL_ENABLED': 'false',
            'INVESTIGATION_PAID_BACKGROUND_ENABLED': 'false', 'INVESTIGATION_COUNT_EXTERNAL_ENABLED': 'false',
            'EMBEDDING_PROVIDER': 'disabled', 'EMBEDDING_ALLOW_PAID': 'false'}
    for name in ('api', 'worker', 'dispatcher'):
        service = services[name]
        assert service['image'] == 'repopilot-local-demo-api:cie'
        env = service['environment']
        assert env['DATABASE_URL'] == old_env['DATABASE_URL']
        url = urlsplit(env['DATABASE_URL'].replace('postgresql+psycopg://', 'postgresql://', 1))
        assert url.hostname == 'postgres' and url.path == '/repopilot' and url.port == 5432
        assert env['REDIS_URL'] == 'redis://redis:6379/0'
        assert all(env.get(key) == value for key, value in paid.items())
        assert env['APP_ENV'] == 'development' and env['GITHUB_OAUTH_ENABLED'] == 'true'
        assert env['DEMO_AUTH_ENABLED'] == 'false'
        assert env['WEB_ORIGIN'] == 'http://localhost:3000'
        assert env['GITHUB_CALLBACK_URL'] == 'http://localhost:3000/api/auth/callback'
        assert all(env.get(key) for key in ('GITHUB_APP_ID', 'GITHUB_CLIENT_ID',
                                            'GITHUB_CLIENT_SECRET', 'GITHUB_TOKEN_ENCRYPTION_KEY'))
        assert env['GITHUB_APP_ID'] != '0'
    assert services['web']['image'] == 'repopilot-local-demo-web:cie'
    assert services['web']['environment']['API_INTERNAL_URL'] == 'http://api:8000'
    for name, port, target in (('api', '8001', 8000), ('web', '3000', 3000)):
        ports = services[name]['ports']
        assert (len(ports) == 1 and ports[0]['host_ip'] == '127.0.0.1'
                and str(ports[0]['published']) == port and ports[0]['target'] == target
                and ports[0]['protocol'] == 'tcp')
    print('Compose target, isolated volumes, OAuth and disabled-provider settings verified.')


if __name__ == '__main__':
    if not __debug__:
        print('Configuration checks cannot run with Python optimization.', file=sys.stderr)
        raise SystemExit(1)
    try:
        check()
    except (AssertionError, KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError):
        print('Compose configuration check failed; stop and review without printing secrets.', file=sys.stderr)
        raise SystemExit(1) from None
