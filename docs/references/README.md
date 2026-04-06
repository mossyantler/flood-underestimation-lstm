# Reference Notes

이 폴더는 `workflow/`나 `research/`의 공식 설계 문서를 대체하지 않는다. 외부 강의, 영상, 교재, 블로그, 보조 메모를 `현재 CAMELS 연구 맥락으로 번역한 참고 노트`를 두는 곳이다.

역할은 세 가지로 한정한다.

1. 외부 자료의 핵심 개념을 프로젝트 언어로 다시 정리한다.
2. 바로 코드나 실험 설계에 연결될 만한 해석 포인트를 메모한다.
3. 공식 방법론은 아니지만, 후속 feature engineering이나 해석 아이디어의 배경지식을 축적한다.

반대로 아래 내용은 이 폴더에 두지 않는다.

- 현재 저장소의 공식 workflow와 screening 기준
- 논문 본문에 직접 들어갈 연구 설계의 source of truth
- auto-generated memory file, slide export, 임시 산출물

현재 `references/`의 자료는 아래와 같다.

- [`youtube-river-basin-analysis-study-guide.md`](youtube-river-basin-analysis-study-guide.md): 유역 형상, 하천망, 형상계수, 경사, 차수 같은 전통 수문학 개념을 CAMELS basin analysis와 모델 오류 해석 관점으로 연결한 학습 가이드

문서는 보통 아래 순서로 읽는다.

1. 공식 workflow나 연구 설계는 먼저 [`../README.md`](../README.md), [`../workflow/basin.md`](../workflow/basin.md), [`../research/design.md`](../research/design.md)에서 확인한다.
2. 그 다음 외부 개념을 보강하고 싶을 때 `references/` 노트를 읽는다.
3. 참고 노트에서 얻은 아이디어가 실제 기준으로 승격되면, 다시 `workflow/`나 `research/` 문서로 옮겨 적는다.
