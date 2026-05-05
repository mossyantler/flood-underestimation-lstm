# scripts/ Agent Notes

루트 `AGENTS.md`를 먼저 따른다. 이 폴더는 데이터 준비, basin 분석, reference 보강, figure 생성, run 실행 진입점을 둔다.

---

## 디렉토리 구조

```text
scripts/
├── _lib/         # 여러 script에서 import하는 공용 helper
├── basin/        # DRBC/all-basin screening, event response, reference, plot
│   ├── all/
│   ├── drbc/
│   ├── event_regime/
│   ├── plots/
│   ├── reference/
│   └── split_diagnostics/
├── data/         # CAMELSH download, matching, NH generic dataset preparation
├── model/        # Model 1/2 결과 분석, hydrograph, stress test, sequence helper
├── ops/          # repo/server 운영 helper, integrity check, resume flattening
├── scaling/      # scaling pilot split/diagnostics/plots
└── runs/         # 학습·평가 실행 성격의 entry point
    ├── official/
    ├── pilot/
    └── dev/
```

루트 `scripts/`에는 `README.md`와 `AGENTS.md`만 두는 것을 기본으로 한다. 실제 실행 파일은 목적별 하위 폴더에 둔다.

---

## 구성 규칙

- 새 Python script는 `uv run`으로 실행 가능해야 하며, 필요한 경우 PEP 723 `# /// script` dependency header를 사용한다.
- `scripts/runs/`에는 실제 shell runner만 둔다. 공식 runner는 `scripts/runs/official/`, scaling pilot runner는 `scripts/runs/pilot/`, local sanity와 subset comparison runner는 `scripts/runs/dev/`에 둔다.
- Model 1/2 결과 분석은 `scripts/model/`, pilot subset/diagnostic은 `scripts/scaling/`, basin cohort/screening/event analysis는 `scripts/basin/`에 둔다. `dev` 성격의 exploratory 분석이라도 run이 아니면 목적별 상위 폴더에 둔다.
- 데이터 준비는 `scripts/data/`, 운영 helper는 `scripts/ops/`, import 전용 helper는 `scripts/_lib/`에 둔다.
- one-off 분석도 가능한 한 반복 가능한 script로 남긴다. 입력/출력 경로는 argparse 기본값으로 드러나게 한다.
- 산출물은 `output/`, 학습 run은 `runs/`, scratch는 `tmp/`를 사용한다. scripts가 공식 output layout을 바꾸면 docs도 함께 갱신한다.
- macOS 로컬에서 실행 안내를 쓸 때는 Homebrew PATH 규칙 `export PATH="/opt/homebrew/bin:$PATH"`를 고려한다.
- 스크립트별 역할, 입출력 경로, 실행 순서의 상세 목록은 `scripts/README.md`를 참조한다.
