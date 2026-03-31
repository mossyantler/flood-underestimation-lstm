# Documentation Layout

이 디렉토리는 실행 가능한 코드와 분리하여 관리해야 할 프로젝트 문서를 보관한다.
현재 프로젝트의 공식 공간 기준은 DRBC Delaware River Basin 공식 경계이고, 기본 basin 데이터셋은 `CAMELSH`다.

- `workflow/`: 데이터 준비, basin 선정, source CSV 해석, 운영 절차 같은 작업 흐름 문서.
- `research/`: 모델 아키텍처, 실험 설계, 선행연구 정리.

현재 `workflow/`에서 핵심적으로 보는 문서는 아래 두 개다.

- [`workflow/basin.md`](/Users/jang-minyeop/Project/CAMELS/docs/workflow/basin.md): 현재 공식 basin 정의, DRBC + CAMELSH subset 기준, 다음 basin analysis 단계 정리
- [`workflow/basin_explain.md`](/Users/jang-minyeop/Project/CAMELS/docs/workflow/basin_explain.md): basin analysis table에 쓰는 source CSV와 변수 해석 가이드

에이전트 작업 맥락은 루트의 `agents.md`를 참조한다.
생성된 출력이나 임시 파일은 여기에 두지 않으며, Git에서 무시된다.
