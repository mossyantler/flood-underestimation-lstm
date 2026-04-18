# Config Layout

이 디렉토리는 실험 설정 파일을 역할별로 나눈다.

- 루트 `configs/`의 `camelsh_hourly_*_drbc_holdout_broad.yml`:
  현재 논문 본문과 공식 비교 실험에서 사용하는 canonical broad config다.
- `configs/basin_splits/`:
  raw basin membership file을 둔다. usability gate 적용 전 단계의 split membership을 기록한다.
- `configs/dev/`:
  local sanity 같은 개발용 설정을 둔다. 공식 결과표나 논문 baseline count는 이 경로를 기준으로 읽지 않는다.

공식 baseline의 실제 실행 count는 raw split file이 아니라 prepared split과 split manifest를 기준으로 해석한다.
