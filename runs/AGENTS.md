# runs/ Agent Notes

루트 `AGENTS.md`를 먼저 따른다. 이 폴더는 NeuralHydrology 학습 run, checkpoint, validation output을 두는 gitignored 실행 결과 공간이다.

---

## 디렉토리 구조

```text
runs/
├── scaling_pilot/       # basin 수 선택용 pilot run
└── subset_comparison/   # fixed scaling_300 Model 1/2 main comparison run
    └── <run_name>/      # NH run directory: config, checkpoints, validation outputs
```

각 `<run_name>/`은 NeuralHydrology가 만든 구조를 유지한다. 내부 파일을 평탄화하거나 이름을 바꾸면 resume, validation export, 분석 스크립트가 깨질 수 있다.

---

## 구성 규칙

- checkpoint와 optimizer state는 실험 재현성에 중요하다. 명시적 요청 없이 삭제, 이동, 덮어쓰기, flattening을 하지 않는다.
- resume/flatten 작업은 기존 helper script를 우선 사용하고, 실행 전후 `model_epoch*.pt`, `optimizer_state_epoch*.pt`, `validation/model_epoch*` 위치를 확인한다.
- 분석용 산출물은 가능하면 `output/model_analysis/`로 export하고, `runs/` 내부 구조에 직접 의존하는 코드는 최소화한다.
- 실패 run도 원인 분석 가치가 있을 수 있으므로, NaN loss나 interrupted run을 임의로 정리하지 않는다.
