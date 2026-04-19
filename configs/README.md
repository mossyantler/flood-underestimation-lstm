# Config Layout

이 디렉토리는 실험 설정 파일을 역할별로 나눈다.

- 루트 `configs/`의 `camelsh_hourly_*_drbc_holdout_broad.yml`:
  현재 논문 본문과 공식 비교 실험에서 사용하는 canonical broad config다.
- `configs/pilot/`:
  deterministic scaling pilot 전용 config, basin split, prepared pool manifest, distribution diagnostics, diagnostics plot을 둔다. 이 경로는 최종 basin 수를 정하기 위한 운영 결정용 pilot이며, 공식 `Model 1 vs Model 2` 본 비교를 대체하지 않는다.
- `configs/basin_splits/`:
  raw basin membership file을 둔다. usability gate 적용 전 단계의 split membership을 기록한다.
- `configs/dev/`:
  local sanity 같은 개발용 설정을 둔다. 공식 결과표나 논문 baseline count는 이 경로를 기준으로 읽지 않는다.

공식 baseline의 실제 실행 count는 raw split file이 아니라 prepared split과 split manifest를 기준으로 해석한다.
scaling pilot은 raw broad pool `1923`을 source-of-truth로 삼되, 실제 실행용 subset은 prepared broad train/validation basin에서 뽑은 `configs/pilot/basin_splits/scaling_*` 경로를 사용한다. pilot basin 수는 DRBC test metric이 아니라 non-DRBC validation 결과와 `configs/pilot/diagnostics/`의 분포 보존 결과 및 `configs/pilot/diagnostics/plots/`의 해석용 시각화를 함께 보고 정한다.
