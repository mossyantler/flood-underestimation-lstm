# Config Layout

이 디렉토리는 실험 설정 파일을 역할별로 나눈다.

- 루트 `configs/`의 `camelsh_hourly_*_drbc_holdout_broad.yml`:
  현재 논문 본문과 공식 비교 실험의 reference broad config다. 다만 현재 compute-constrained main comparison 실행은 이 broad config를 그대로 복사하지 않고, `scripts/runs/official/run_subset300_multiseed.sh`에서 `configs/pilot/basin_splits/scaling_300/` basin file을 override해 사용한다.
- `configs/pilot/`:
  deterministic scaling pilot 전용 config, basin split, prepared pool manifest, static/observed-flow distribution diagnostics, random same-size subset benchmark, diagnostics plot을 둔다. 이 경로는 원래 최종 basin 수를 정하기 위한 운영 결정용 pilot이었고, 현재는 선택 결과가 `300`으로 닫힌 상태에서 adopted subset manifest와 representativeness audit 근거를 같이 보관한다.
- `configs/basin_splits/`:
  raw basin membership file을 둔다. usability gate 적용 전 단계의 split membership을 기록한다.
- `configs/dev/`:
  local sanity 같은 개발용 설정을 둔다. 공식 결과표나 논문 baseline count는 이 경로를 기준으로 읽지 않는다.

공식 baseline의 실제 실행 count는 raw split file이 아니라 prepared split과 split manifest를 기준으로 해석한다.
현재 compute-constrained main comparison은 raw broad pool `1923`이 아니라 prepared broad train/validation basin에서 고정한 `configs/pilot/basin_splits/scaling_300/` 경로를 사용한다. 이 `300` 선택은 DRBC test metric이 아니라 non-DRBC validation 결과와 `configs/pilot/diagnostics/`의 static/observed-flow representativeness 진단, random same-size subset benchmark, compute cost를 함께 보고 확정했다.
