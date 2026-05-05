# logs/ Agent Notes

루트 `AGENTS.md`를 먼저 따른다. 이 폴더는 실행 로그와 임시 진단 로그를 두는 공간이며 기본적으로 gitignored다.

---

## 디렉토리 구조

```text
logs/
├── extreme_rain_all_validation_epochs/   # all-validation-epoch stress test 실행 로그
└── quantile_analysis/                    # quantile/hydrograph 분석 실행 로그
```

새 로그 묶음은 작업명이나 공식 workflow 이름으로 top-level 폴더를 만들고, 파일명에는 seed/epoch/split처럼 재현에 필요한 식별자를 넣는다.

---

## 구성 규칙

- 로그는 재현성 보조 자료이지 canonical 결과 표가 아니다. 논문/분석에 쓰는 집계 결과는 `output/`의 적절한 `tables/`, `metadata/`, `logs/` 위치에 정리한다.
- 새 로그를 만들 때는 실행 목적, script 이름, seed/epoch/split이 드러나는 파일명을 사용한다.
- 오래 걸리는 remote/GPU 실행 로그를 정리할 때는 원본을 덮어쓰기보다 필요한 요약 산출물을 별도로 만든다.
- 사용자의 기존 로그를 삭제하거나 축약하지 않는다. 정리가 필요하면 새 위치로 복사/요약한다.
