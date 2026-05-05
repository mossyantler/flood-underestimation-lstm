# data/ Agent Notes

루트 `AGENTS.md`를 먼저 따른다. 이 폴더는 NeuralHydrology generic format으로 준비된 dataset과 loader가 사용하는 파생 실행용 데이터를 둔다.

---

## 디렉토리 구조

```text
data/
└── CAMELSH_generic/                         # prepared CAMELSH generic data (gitignored)
    └── drbc_holdout_broad/                  # 현재 hourly generic dataset 기준
        ├── attributes/                      # NH loader용 static attributes
        ├── splits/                          # loader/runtime용 파생 split 파일
        ├── time_series/                     # NetCDF time-series
        └── time_series_csv/                 # CSV export 또는 점검용 시계열
```

---

## 구성 규칙

- `data/CAMELSH_generic/drbc_holdout_broad/`가 현재 CAMELSH hourly generic dataset 기준이다. CAMELS-US local dataset을 새 의존성으로 되살리지 않는다.
- 공식 basin split의 source-of-truth는 `configs/basin_splits/`와 `configs/pilot/basin_splits/scaling_300/`이다. `data/`의 split 파일은 loader/runtime 편의를 위한 파생물로 취급한다.
- `data/CAMELSH_generic/`는 gitignored prepared data 공간이다. 재현성은 raw data, configs, scripts, docs/run records로 남긴다.
- prepared data는 재생성 가능한 전처리 결과로 취급한다. 파일 구조나 변수명을 바꾸면 config, scripts, docs를 함께 갱신한다.
- NetCDF/time-series 파일은 대용량일 수 있으므로 직접 편집하지 말고, 필요하면 변환 script를 수정해 다시 생성한다.
- target `Streamflow`와 dynamic forcing 변수명은 config와 NeuralHydrology loader가 기대하는 이름을 유지한다.
