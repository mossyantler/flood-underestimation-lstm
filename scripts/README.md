# Script Layout

이 디렉토리는 역할에 따라 스크립트를 구분한다.

- 루트 `scripts/`:
  데이터 준비, basin 분석, screening, integrity check, NeuralHydrology resume run 평탄화 helper처럼 canonical workflow에 직접 연결되는 스크립트를 둔다. 현재 DRBC screening 쪽 canonical 진입점에는 `build_drbc_basin_analysis_table.py`, `build_drbc_streamflow_quality_table.py`, `build_drbc_preliminary_screening_table.py`, `build_drbc_provisional_screening_table.py`, `build_drbc_event_response_table.py`가 포함된다.
- `scripts/official/`:
  공식 실험 실행 진입점을 둔다. 현재는 full broad runner `run_broad_multiseed.sh`와, compute-constrained main comparison에서 fixed `scaling_300` subset을 seed `111 / 222 / 333`과 Model 1 / Model 2에 공통 적용하는 `run_subset300_multiseed.sh`를 함께 둔다.
- `scripts/pilot/`:
  deterministic scaling pilot용 전국 stratified subset 생성, static attribute distribution diagnostics, observed-flow event-response diagnostics, random same-size subset benchmark, diagnostics 해석용 plot 생성, 실행 진입점을 둔다. 이 경로는 basin-count selection의 근거를 남기는 운영 pilot 경로이며, 현재는 채택된 `300` subset의 representativeness audit 근거도 함께 둔다. pilot runner는 `NH_RESUME=1`, `NH_SAVE_ALL_OUTPUT=False`, `NH_SAVE_VALIDATION_RESULTS=False` 같은 환경변수 override를 받아 storage-constrained 실행을 지원하고, resume 후에는 `scripts/flatten_nh_resume_run.py`를 통해 nested `continue_training_from_epoch...` 체인을 자동으로 평탄화한다.
- `scripts/dev/`:
  local sanity, 빠른 로컬 점검, subset 기반 Model 1/Model 2 비교 helper처럼 개발용 실행 진입점을 둔다. `run_subset_model_comparison.sh`는 broad official config를 기반으로 subset basin file과 runtime override만 바꿔 `300` 같은 subset run을 실행하는 하위 helper이고, 현재 채택된 `300` main comparison은 `scripts/official/run_subset300_multiseed.sh`가 이 helper를 감싸는 구조다.

저장소 무결성 점검은 아래처럼 실행한다.

```bash
uv run scripts/check_repo_integrity.py
```
