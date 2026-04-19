# Script Layout

이 디렉토리는 역할에 따라 스크립트를 구분한다.

- 루트 `scripts/`:
  데이터 준비, basin 분석, screening, integrity check처럼 canonical workflow에 직접 연결되는 스크립트를 둔다.
- `scripts/official/`:
  공식 broad 실험 실행 진입점을 둔다.
- `scripts/pilot/`:
  deterministic scaling pilot용 전국 stratified subset 생성, static attribute distribution diagnostics, diagnostics 해석용 plot 생성, 실행 진입점을 둔다. 이 경로는 최종 basin 수를 정하기 위한 운영 pilot이며, 공식 main comparison runner와 분리한다. pilot runner는 `NH_RESUME=1`, `NH_SAVE_ALL_OUTPUT=False`, `NH_SAVE_VALIDATION_RESULTS=False` 같은 환경변수 override를 받아 storage-constrained 실행을 지원한다.
- `scripts/dev/`:
  local sanity, 빠른 로컬 점검처럼 개발용 실행 진입점을 둔다.

저장소 무결성 점검은 아래처럼 실행한다.

```bash
uv run scripts/check_repo_integrity.py
```
