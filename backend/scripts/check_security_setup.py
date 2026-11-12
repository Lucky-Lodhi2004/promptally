"""Read-only security readiness report. Never prints secret values."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.core.config import settings
from backend.app.core.security_configuration import security_configuration_issues

if __name__ == '__main__':
    issues = security_configuration_issues(settings)
    for issue in issues:
        print('ACTION REQUIRED:', issue)
    if not issues:
        print('Security configuration checks passed. External proxy and provider settings still require validation.')
    raise SystemExit(1 if issues else 0)
