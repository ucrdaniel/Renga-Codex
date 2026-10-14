import os
import sys
import pytest

pytestmark=pytest.mark.integration

@pytest.mark.skipif(sys.platform!='win32' or os.environ.get('RENGA_BRIDGE_RUN_INTEGRATION')!='1',
                    reason='Actual local Renga opt-in test; hosted CI is not proof of integration')
def test_real_renga_roundtrip():
    from pathlib import Path
    import runpy
    runpy.run_path(str(Path(__file__).resolve().parents[2]/'scripts/run_live_tests.py'),run_name='__main__')
