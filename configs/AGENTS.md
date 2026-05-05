# configs/ Agent Notes

루트 `AGENTS.md`를 먼저 따른다. 이 폴더는 공식 config, basin split, pilot split의 source-of-truth를 둔다.

---

## 디렉토리 구조

```text
configs/
├── basin_splits/                 # broad DRBC holdout raw split 기준
├── pilot/
│   ├── basin_splits/             # scaling pilot 및 fixed subset split
│   │   ├── scaling_100/
│   │   ├── scaling_300/          # 현재 Model 1/2 main comparison 고정 split
│   │   └── scaling_600/
│   └── diagnostics/              # subset 선택 근거 diagnostic config/output pointer
└── dev/
    └── basin_splits/             # local sanity, 임시 subset split
```

---

## 구성 규칙

- `configs/pilot/basin_splits/scaling_300/`은 현재 Model 1 / Model 2 main comparison의 고정 train/validation/test split이다. 이 split을 바꾸면 공식 실험 조건이 바뀌므로 관련 docs와 scripts 설명을 함께 갱신한다.
- `configs/basin_splits/`는 broad DRBC holdout setup의 raw split 기준이다. 파일명과 split 의미를 임의로 바꾸지 않는다.
- YAML config의 핵심 통제변수(`model`, `head`, `loss`, `seq_length`, `predict_last_n`, basin files, seed)는 연구 설계 조건이다. 실험용 변경은 dev/pilot config로 분리한다.
- basin ID 파일은 한 줄에 하나의 문자열 ID 형식을 유지하고, leading zero를 보존한다.
- paired aggregate의 공식 seed는 루트 `AGENTS.md` 기준을 따른다. 현재 final aggregate는 Model 1 / Model 2 seed `111 / 222 / 444`를 사용하고 seed `333`은 제외한다.
