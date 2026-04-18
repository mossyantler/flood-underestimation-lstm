# Script Layout

이 디렉토리는 역할에 따라 스크립트를 구분한다.

- 루트 `scripts/`:
  데이터 준비, basin 분석, screening, integrity check처럼 canonical workflow에 직접 연결되는 스크립트를 둔다.
- `scripts/official/`:
  공식 broad 실험 실행 진입점을 둔다.
- `scripts/dev/`:
  local sanity, 빠른 로컬 점검처럼 개발용 실행 진입점을 둔다.

저장소 무결성 점검은 아래처럼 실행한다.

```bash
uv run scripts/check_repo_integrity.py
```
