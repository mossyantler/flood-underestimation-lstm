# vendor/ Agent Notes

루트 `AGENTS.md`를 먼저 따른다. 이 폴더는 upstream dependency source를 vendored copy로 둔다.

---

## 디렉토리 구조

```text
vendor/
└── neuralhydrology/              # vendored NeuralHydrology source
    ├── neuralhydrology/          # import되는 package code
    ├── docs/                     # upstream documentation
    ├── examples/                 # upstream examples
    └── test/                     # upstream tests
```

일부 공식/준공식 실행 경로는 `vendor/neuralhydrology`를 import path 앞에 둔다. 따라서 이 폴더는 단순 참고자료이면서도 runtime behavior와 재현성에 직접 영향을 줄 수 있다.

---

## 구성 규칙

- `vendor/neuralhydrology/`는 upstream 코드 참조/패치 검토용이다. 프로젝트 behavior 변경은 가능하면 wrapper, config, local script 쪽에서 해결하고 vendor를 직접 수정하지 않는다.
- vendor 코드를 수정해야 하면 변경 이유, upstream 대비 차이, 영향을 받는 config/script, 기존 run 재현성 영향을 문서화한다.
- upstream behavior를 확인할 때는 vendored code를 읽되, 공식 실험 경로와 산출물 위치는 프로젝트 docs/scripts 기준으로 설명한다.
- 대규모 upstream sync나 vendor 재배치는 명시적 요청 없이는 수행하지 않는다.
