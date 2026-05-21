# dashboard/ Agent Notes

루트 `AGENTS.md`를 먼저 따른다.
이 디렉토리는 CAMELS 실험 분석을 검토하기 위한 React / Next.js 대시보드 workspace다.

분석의 source-of-truth는 계속 `output/`, `docs/experiment/analysis/`, `docs/experiment/method/`, `configs/`에 둔다.
`dashboard/`는 연구 결론을 새로 정의하는 공간이 아니라, 이미 생성된 분석 산출물을 읽기 쉽게 보여 주는 UI와 그에 필요한 작은 snapshot asset만 보관하는 공간이다.

---

## 디렉토리 구조

```text
dashboard/
├── app/                 # Next.js App Router entry, layout, page, global CSS
├── components/          # dashboard 화면을 이루는 React component
├── lib/                 # dashboard용 typed snapshot data와 formatting helper
├── public/              # 정적 asset
│   ├── figures/         # output/에서 복사한 핵심 figure preview
│   └── research/        # UI reference / design research image
├── figma/               # Figma source/export, visual QA screenshot
├── README.md            # 실행 방법, source data, design rule 요약
├── package.json         # npm script와 dependency
├── package-lock.json    # npm dependency lockfile
└── .gitignore           # .next/, node_modules/, out/, tsbuildinfo, env 제외
```

`node_modules/`, `.next/`, `out/`, `*.tsbuildinfo`, `.env*`는 생성물 또는 로컬 환경 파일이다.
직접 편집하거나 canonical 산출물처럼 다루지 않는다.

---

## 개발 환경

이 폴더는 루트의 `uv` 기반 Python workflow와 분리된 npm 기반 Next.js workspace다.
현재 `package.json` 기준으로 Next.js App Router, React, TypeScript, `lucide-react`를 사용한다.

로컬 macOS에서 실행할 때는 루트 규칙과 같이 Homebrew PATH를 먼저 잡고, `dashboard/` 안에서 npm 명령을 실행한다.

```bash
export PATH="/opt/homebrew/bin:$PATH"
cd dashboard
npm install
npm run dev
```

개발 서버 기본 주소는 `http://localhost:3000`이다.
이미 3000번 port가 사용 중이면 `npm run dev -- -p 3001`처럼 다른 port를 지정한다.

검증 명령은 변경 범위에 맞춰 선택한다.

```bash
npm run typecheck
npm run build
```

UI component, data type, formatting helper를 바꿨다면 최소 `npm run typecheck`를 실행한다.
Next.js config, route/layout, dependency, static asset loading에 영향을 주는 변경이면 `npm run build`까지 확인한다.
dependency는 npm과 `package-lock.json`을 기준으로 관리하며, yarn/pnpm으로 lockfile을 새로 만들지 않는다.

dashboard는 gitignored `output/` tree 전체를 runtime dependency로 삼지 않도록 설계한다.
앱 렌더링에 필요한 값은 작은 typed snapshot으로 `lib/`에 두고, 큰 원본 CSV·figure gallery·checkpoint는 `output/` 또는 `runs/`에 그대로 둔다.

---

## 디자인 환경

기본 visual system은 `../vercel/DESIGN.md`다.
dashboard는 실험 분석을 반복해서 훑어보는 작업 화면이므로, marketing landing page가 아니라 dense analytic surface로 유지한다.

디자인 작업의 기준 자료는 아래처럼 구분한다.

| 위치 | 역할 |
| --- | --- |
| `../vercel/DESIGN.md` | color, typography, spacing, rounded, component token 기준 |
| `figma/dashboard layout rough design.fig` | CAMELS dashboard rough design source. app shell, context sidebar, main workbench, card/table/detail page 규격 기준 |
| `.lazyweb/design-research/experiment-analysis-dashboard-2026-05-14/report.md` | 초기 dashboard design research 참고 |
| `public/research/` | 화면 안에서 참조하거나 보존할 UI reference image |
| `figma/` | Figma source/export, local visual QA screenshot |

UI는 light/dark theme 모두에서 읽히도록 만든다.
ink typography, thin hairline, mono metadata label, 작은 accent color를 우선하고, 큰 hero section, 장식용 gradient/orb, 과한 card stacking은 피한다.
카드는 반복 metric, figure preview, table-like item처럼 실제로 frame이 필요한 요소에만 쓴다.

컨트롤은 익숙한 UI 패턴을 쓴다.
아이콘이 필요한 버튼은 가능한 `lucide-react`를 사용하고, 모드 전환은 segmented control 또는 tab, binary 설정은 toggle/checkbox, 수치 조정은 input/slider처럼 의미가 드러나는 control을 사용한다.

의미 있는 UI 변경 뒤에는 화면을 직접 확인한다.
최소 desktop width와 mobile width에서 text overflow, 겹침, theme contrast, figure aspect ratio, hover/focus state를 확인하고, 필요한 경우 Browser/Playwright screenshot을 `figma/`에 남긴다.
시각 검증용 screenshot은 결과 설명 자료이지 분석 source-of-truth가 아니다.

---

## 구성 규칙

- **source-of-truth 경계**: dashboard의 숫자, 표기, figure caption을 고칠 때는 먼저 `output/model_analysis/`, `docs/experiment/analysis/`, `docs/experiment/method/`, `configs/` 중 어떤 파일이 근거인지 확인한다. dashboard 안의 `lib/dashboard-data.ts`만 보고 연구 결론을 확정하지 않는다.
- **snapshot data**: 화면에 필요한 작은 정적 데이터는 `lib/`에 typed object로 둔다. 값이 최신 산출물에서 온 경우 `generatedAt`과 source path를 `README.md` 또는 코드 주변에서 추적 가능하게 유지한다.
- **큰 분석 산출물 금지**: 대용량 CSV, checkpoint, full hydrograph gallery, 모델 run output은 이 폴더에 넣지 않는다. 원본은 `output/` 또는 `runs/`에 두고, dashboard에는 렌더링에 필요한 작은 preview asset만 복사한다.
- **asset 배치**: 논문/분석 figure preview는 `public/figures/`, 외부 UI reference나 design research image는 `public/research/`, 화면 QA screenshot과 Figma export는 `figma/`에 둔다.
- **UI 구현 위치**: route-level composition은 `app/`, 재사용 가능한 화면 조각과 interaction component는 `components/`, 순수 formatting/data helper는 `lib/`에 둔다.
- **디자인 기준**: visual system은 `../vercel/DESIGN.md`를 따른다. 마케팅 landing page처럼 만들지 말고, dense analytic surface, 얇은 hairline, mono metadata label, 절제된 accent, light/dark theme 일관성을 유지한다.
- **dependency 관리**: 이 workspace는 `package-lock.json`이 있는 npm 프로젝트다. dependency를 추가하면 `package.json`과 `package-lock.json`을 함께 갱신한다.
- **subagent 운영**: dashboard 수정은 범위를 명확히 나눈 수정 subagent를 통해 진행하고, 수정/생성이 의도대로 이루어졌는지는 별도의 검증 subagent를 통해 확인한다.
- **검증**: 의미 있는 UI나 data shape 변경 뒤에는 최소 `npm run typecheck`를 실행한다. 배포 또는 build 영향이 있는 변경이면 `npm run build`까지 확인한다.
- **문서 동기화**: 실행 명령, source data 경로, preview asset, 디자인 기준이 바뀌면 `dashboard/README.md`도 함께 갱신한다. 공식 실험 경로 또는 분석 결론이 바뀌는 경우에는 관련 `docs/experiment/...` 문서와 root 규칙의 동기화 범위도 확인한다.

---

## 작업 체크리스트

dashboard를 수정할 때는 아래를 먼저 확인한다.

1. 화면에 표시할 값이 dashboard 내부 추정인지, canonical output/doc/config에서 온 값인지 구분한다.
2. 새 파일이 `app/`, `components/`, `lib/`, `public/`, `figma/` 중 어디에 속하는지 확인한다.
3. 원본 분석 산출물을 dashboard에 복사해야 한다면 작은 preview인지 확인하고, 대용량 원본은 `output/`에 그대로 둔다.
4. UI 변경이 `../vercel/DESIGN.md`의 밀도, typography, color, theme 규칙과 충돌하지 않는지 확인한다.
5. 변경 후 `npm run typecheck` 또는 필요한 build/smoke check를 실행하고, README 경로와 설명이 stale하지 않은지 확인한다.
