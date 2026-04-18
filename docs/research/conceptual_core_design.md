# Model 3 Conceptual Core Design

## 서술 목적

이 문서는 현재 논문 범위 밖의 future-work 메모로서, Model 3 — physics-guided probabilistic hybrid — 의 **conceptual core** 상세 설계를 정리한다. 즉 LSTM encoder 뒤에 어떤 상태 변수, 어떤 flux, 어떤 routing을 두고, 그 출력을 quantile head로 어떻게 연결할지를 후속 설계 관점에서 기록한다.

## 다루는 범위

- conceptual core의 상태 변수, flux 방정식, routing 구조
- LSTM → flux head → conceptual core → quantile head 연결 흐름
- 기존 vendor `HybridModel + SHM` 대비 우리 설계가 다른 점
- physics regularization loss 설계
- 구현 전략과 NeuralHydrology 통합 방향

## 다루지 않는 범위

- Model 1 / Model 2 config 및 학습 규칙 (→ `experiment_protocol.md`)
- event extraction / basin screening (→ `event_response_spec.md`, `basin_screening_method.md`)
- quantile head 내부 구현 (→ `probabilistic_head_guide.md`)

이 문서는 참고 설계 문서이며, 현재 논문의 공식 비교 실험은 `Model 1 vs Model 2`에 한정한다.

---

## 1. 설계 철학

### 1.1 왜 vendor SHM 방식을 그대로 쓰면 안 되는가

현재 vendored NeuralHydrology의 `HybridModel + SHM`은 **naive dynamic-parameter** 방식이다.

```text
LSTM h_t → Linear → sigmoid → [dd, f_thr, sumax, beta, perc, kf, ki, kb]
                                   ↓
                              SHM conceptual model (8개 파라미터 전체가 시점별로 변동)
                                   ↓
                              y_hat = qf_out + qi_out + qb_out
```

이 구조의 문제는 Acuña Espinoza et al. (2024, "To bucket or not to bucket?")에서 명확히 지적됐다:

1. **LSTM이 conceptual model을 덮어쓴다.** LSTM이 모든 파라미터를 자유롭게 조절하면, conceptual structure가 실질적인 물리 제약이 아니라 장식이 된다. 심지어 "nonsense" 구조를 넣어도 LSTM이 보상해서 성능이 유지된다.
2. **해석 가능성이 보장되지 않는다.** 파라미터 전체를 동적으로 바꾸면, 학습된 파라미터 궤적이 물리적으로 의미 있는지 확인하기 어렵다.
3. **성능 이득이 없다.** 순수 LSTM 대비 hybrid가 streamflow prediction 성능에서 유의미한 이점을 보이지 않았다.

또한 Frame et al. (2022)는 MC-LSTM의 mass conservation 제약만으로는 extreme flood peak underestimation을 해결하지 못하며, 오히려 unconstrained LSTM보다 성능이 떨어질 수 있음을 보였다.

### 1.2 우리 설계의 핵심 원칙

위 비판을 수용하되, 우리 연구의 고유한 질문 — "probabilistic head 위에 physics-guided core를 얹으면 **peak magnitude, timing, basin generalization**에서 추가 이득이 있는가?" — 에 맞게 설계한다.

핵심 원칙 네 가지:

| # | 원칙 | 이유 |
|---|------|------|
| P1 | **Flux-constrained, not parameter-free** | LSTM이 conceptual 파라미터 θ 전체를 시점별로 자유롭게 바꾸는 것이 아니라, 물리적으로 bounded된 소수의 flux와 coefficient만 제안한다 |
| P2 | **State update는 conceptual core가 담당** | storage 갱신과 routing은 differentiable하지만 고정된 수식으로 수행한다. LSTM이 state를 직접 쓰지 않는다 |
| P3 | **Probabilistic head는 conceptual core 뒤에 온다** | core가 만든 base hydrograph 위에서 quantile 분포를 예측한다. deterministic core + probabilistic tail의 구조 |
| P4 | **비교 공정성 유지** | backbone (CudaLSTM), input, split, optimizer budget은 Model 1/2와 동일하게 유지한다 |

### 1.3 기존 방식과의 차이 요약

| 항목 | Vendor SHM Hybrid | 우리 Model 3 |
|------|-------------------|--------------|
| LSTM이 제어하는 것 | 모든 conceptual 파라미터 (8개) | 제한된 flux/coefficient (5개) |
| 파라미터 동적 범위 | sigmoid로 전 범위 | bounded sigmoid + softplus로 물리 범위 제한 |
| State update 주체 | Conceptual model (하지만 LSTM이 파라미터를 바꿔서 사실상 덮어쓸 수 있음) | Conceptual core (고정 수식, LSTM은 flux만 제안) |
| 출력 head | Regression (y_hat) | Quantile head (q50, q90, q95, q99) |
| Physics loss | 없음 | mass balance, non-negativity, storage bounds regularization |

---

## 2. 전체 아키텍처

```text
┌─────────────────────────────────────────────────────────────────────┐
│  Inputs: Dynamic forcing (11) + Static attributes (8)              │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  InputLayer  │  (embedding, same as M1/M2)
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   CudaLSTM   │  hidden_size = 128, same as M1/M2
                    │   Encoder    │
                    └──────┬──────┘
                           │
                      h_t (128-dim)
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐    │     ┌──────▼──────┐
       │  Flux Head   │    │     │  Quantile   │
       │  (bounded)   │    │     │  Residual   │
       └──────┬──────┘    │     │  Head       │
              │            │     └──────┬──────┘
              │            │            │
     flux predictions      │      ε_quantiles
     (melt, ET_pot_frac,   │     (residual increments)
      infiltration_frac,   │
      routing_k_fast,      │
      routing_k_slow)      │
              │            │
       ┌──────▼──────────────────┐
       │   Conceptual Core       │
       │   (differentiable,      │
       │    fixed equations)     │
       │                         │
       │   Snow → Soil → Split   │
       │   → Fast → Slow         │
       │   → Base hydrograph     │
       └──────────┬──────────────┘
                  │
           Q_base (base hydrograph)
                  │
           ┌──────▼──────┐
           │  Probabilistic
           │  Combination │
           │              │
           │  q50 = Q_base + ε_50
           │  q90 = q50 + softplus(Δ90)
           │  q95 = q90 + softplus(Δ95)
           │  q99 = q95 + softplus(Δ99)
           └──────┬──────┘
                  │
            Final output:
            {y_hat, y_quantiles}
```

### 2.1 아키텍처 요약

Model 3는 **세 개의 하위 모듈**로 나뉜다:

1. **Flux Head**: `h_t → bounded flux/coefficient` (learned, but physically constrained)
2. **Conceptual Core**: `flux + forcing → state update → base hydrograph` (fixed equations, differentiable)
3. **Probabilistic Residual Head**: `h_t → quantile residuals on top of base hydrograph` (learned)

---

## 3. Conceptual Core 상세 설계

### 3.1 상태 변수

최소 골격으로 네 개의 storage를 둔다:

| Storage | 변수명 | 단위 | 역할 |
|---------|--------|------|------|
| Snow storage | $S_{\text{snow}}$ | mm | 고체 강수 축적, 융설 방출 |
| Soil moisture storage | $S_{\text{soil}}$ | mm | 불포화대 수분, 증발산 공급원, runoff generation 조절 |
| Fast runoff storage | $S_{\text{fast}}$ | mm | 지표/근표면 빠른 유출, 첨두 shape 결정 |
| Slow/baseflow storage | $S_{\text{slow}}$ | mm | 지하수/기저유출, recession 결정 |

architecture.md에서 5번째로 언급된 `channel/routing storage`는 첫 논문에서는 생략한다. Nash cascade 등의 routing을 넣으면 파라미터가 늘어나고, hourly 기준으로 소규모 basin에서는 fast/slow 두 reservoir의 시정수 차이만으로도 routing 효과를 근사할 수 있다.

### 3.2 Flux Head 출력

LSTM `h_t`에서 **5개의 bounded flux/coefficient**를 제안한다:

| Flux/Coefficient | 변수명 | 물리 범위 | Bounding 방식 | 역할 |
|------------------|--------|-----------|---------------|------|
| Snowmelt rate | $f_{\text{melt}}$ | [0, $S_{\text{snow}}$] | sigmoid × $S_{\text{snow}}$ | snow storage에서 방출할 비율 |
| ET fraction | $f_{\text{ET}}$ | [0, 1] | sigmoid | PET 대비 실제 ET 비율 |
| Infiltration fraction | $f_{\text{inf}}$ | [0, 1] | sigmoid | effective precipitation 중 soil로 가는 비율 (나머지 → fast) |
| Fast routing coefficient | $k_{\text{fast}}$ | [0.5, 48] hours | sigmoid × range + offset | fast reservoir 시정수 |
| Slow routing coefficient | $k_{\text{slow}}$ | [48, 2000] hours | sigmoid × range + offset | slow reservoir 시정수 |

핵심: LSTM은 이 5개 값만 제안하고, 나머지 state update는 고정된 물수지 방정식이 수행한다. 이것이 "flux-constrained"의 의미다.

```python
class FluxHead(nn.Module):
    """LSTM h_t → 5 bounded flux/coefficient values."""

    def __init__(self, n_in: int):
        super().__init__()
        self.projection = nn.Linear(n_in, 5)

    def forward(self, h_t, s_snow):
        raw = self.projection(h_t)  # (batch, seq, 5)

        f_melt = torch.sigmoid(raw[..., 0]) * s_snow      # [0, S_snow]
        f_ET   = torch.sigmoid(raw[..., 1])                # [0, 1]
        f_inf  = torch.sigmoid(raw[..., 2])                # [0, 1]
        k_fast = 0.5 + torch.sigmoid(raw[..., 3]) * 47.5   # [0.5, 48]
        k_slow = 48.0 + torch.sigmoid(raw[..., 4]) * 1952  # [48, 2000]

        return f_melt, f_ET, f_inf, k_fast, k_slow
```

### 3.3 물수지 방정식 (Conceptual Core Forward Step)

매 시간 스텝 $t$에서 아래 순서로 상태를 갱신한다. 모든 방정식은 differentiable하지만 구조는 고정이다.

#### Step 1: Precipitation partitioning

```math
P_{\text{rain},t} = \begin{cases} P_t & \text{if } T_t \ge T_{\text{th}} \\ 0 & \text{otherwise} \end{cases}
```
```math
P_{\text{snow},t} = P_t - P_{\text{rain},t}
```

온도 threshold $T_{\text{th}}$는 0°C를 기본으로 하되, differentiable soft threshold를 사용한다:

```math
\alpha_t = \sigma\bigl(\gamma \cdot (T_t - T_{\text{th}})\bigr)
```
```math
P_{\text{rain},t} = \alpha_t \cdot P_t, \qquad P_{\text{snow},t} = (1 - \alpha_t) \cdot P_t
```

여기서 $\gamma = 2.0$은 transition steepness, $T_{\text{th}} = 0$°C는 고정 상수다.

#### Step 2: Snow module

```math
M_t = f_{\text{melt},t} \quad (\text{LSTM이 제안, } 0 \le M_t \le S_{\text{snow},t})
```
```math
S_{\text{snow},t+1} = S_{\text{snow},t} + P_{\text{snow},t} - M_t
```

유효 강수 (effective precipitation):

```math
P_{\text{eff},t} = P_{\text{rain},t} + M_t
```

#### Step 3: Soil moisture and ET

```math
\text{ET}_t = f_{\text{ET},t} \cdot \text{PET}_t \cdot \min\!\left(1,\; \frac{S_{\text{soil},t}}{S_{\text{soil,max}}}\right)
```

soil에 들어가는 물과 surface runoff:

```math
Q_{\text{inf},t} = f_{\text{inf},t} \cdot P_{\text{eff},t}
```
```math
Q_{\text{surf},t} = (1 - f_{\text{inf},t}) \cdot P_{\text{eff},t}
```

soil 갱신:

```math
S_{\text{soil},t}^{*} = S_{\text{soil},t} + Q_{\text{inf},t} - \text{ET}_t
```

overflow 처리 (soil이 포화될 때):

```math
Q_{\text{perc},t} = \max\!\left(0,\; S_{\text{soil},t}^{*} - S_{\text{soil,max}}\right)
```
```math
S_{\text{soil},t+1} = \min\!\left(S_{\text{soil},t}^{*},\; S_{\text{soil,max}}\right)
```

여기서 $S_{\text{soil,max}}$는 **static attribute인 `soil_depth`에서 유도**한다. basin마다 다르고 시간에 따라 변하지 않는 상수다.

#### Step 4: Runoff partitioning and routing

fast reservoir (지표/근표면 유출):

```math
S_{\text{fast},t+1} = S_{\text{fast},t} + Q_{\text{surf},t} - Q_{\text{fast},t}
```
```math
Q_{\text{fast},t} = \frac{S_{\text{fast},t} + Q_{\text{surf},t}}{k_{\text{fast},t}}
```

slow reservoir (기저유출):

```math
S_{\text{slow},t+1} = S_{\text{slow},t} + Q_{\text{perc},t} - Q_{\text{slow},t}
```
```math
Q_{\text{slow},t} = \frac{S_{\text{slow},t} + Q_{\text{perc},t}}{k_{\text{slow},t}}
```

#### Step 5: Base hydrograph

```math
Q_{\text{base},t} = Q_{\text{fast},t} + Q_{\text{slow},t}
```

### 3.4 Static Attribute의 역할

conceptual core에서 static attributes는 다음과 같이 사용한다:

| Static attribute | 사용 위치 | 역할 |
|------------------|-----------|------|
| `soil_depth` | $S_{\text{soil,max}}$ | soil storage 상한 (basin별 상수) |
| `area` | unit conversion | mm → m³/s 변환 시 사용 |
| `snow_fraction` | 초기 $S_{\text{snow},0}$ 스케일링 | snow storage 초기값 참고 |
| `baseflow_index` | 초기 $S_{\text{slow},0}$ 스케일링 | slow storage 초기값 참고 |

나머지 static attributes (`slope`, `aridity`, `permeability`, `forest_fraction`)는 LSTM InputLayer에서 기존과 동일하게 사용된다.

---

## 4. Probabilistic Residual Head

### 4.1 왜 residual 구조인가

conceptual core가 만든 $Q_{\text{base}}$는 물수지 방정식의 결과이므로, 평균적인 수문곡선은 잡을 수 있지만 extreme tail을 충분히 열기는 어렵다. 따라서 quantile head를 **conceptual base 위의 residual**로 설계한다.

```text
h_t → Residual Quantile Head → [ε_50, Δ_90, Δ_95, Δ_99]

q50 = Q_base + ε_50
q90 = q50 + softplus(Δ_90)
q95 = q90 + softplus(Δ_95)
q99 = q95 + softplus(Δ_99)
```

이 구조의 장점:

1. **Physics가 anchor**: $Q_{\text{base}}$가 있으므로 quantile head가 "scratch부터 유량을 만드는" 부담을 줄인다.
2. **Tail은 여전히 학습 가능**: $\varepsilon_{50}$이 base를 보정하고, $\Delta_{90}, \Delta_{95}, \Delta_{99}$가 extreme tail을 연다.
3. **Crossing 방지**: Model 2와 동일한 monotonic increment 구조.
4. **비교 가능성**: q50으로 point metric을 계산하므로 Model 1/2와 직접 비교 가능.

### 4.2 Residual Head 구현

```python
class ResidualQuantileHead(nn.Module):
    """Q_base + learned residual quantiles."""

    def __init__(self, n_in: int, quantiles: list[float]):
        super().__init__()
        self._n_quantiles = len(quantiles)
        self._median_idx = quantiles.index(0.5)
        self._projection = nn.Linear(n_in, self._n_quantiles)
        self._softplus = nn.Softplus()

    def forward(self, h_t: torch.Tensor, q_base: torch.Tensor):
        raw = self._projection(h_t)  # (batch, seq, n_quantiles)

        # base correction (ε_50) + positive increments
        base_correction = raw[..., :1]  # unbounded, can be ± correction
        positive_increments = self._softplus(raw[..., 1:])

        # q50 = Q_base + ε_50
        q_median = q_base.unsqueeze(-1) + base_correction

        # q90, q95, q99 = cumulative positive increments above q50
        upper = q_median + torch.cumsum(positive_increments, dim=-1)
        quantiles = torch.cat([q_median, upper], dim=-1)

        y_hat = quantiles[..., self._median_idx]
        return {'y_hat': y_hat, 'y_quantiles': quantiles.squeeze(-2)}
```

---

## 5. Physics Regularization Loss

### 5.1 총 손실 함수

```math
\mathcal{L}_{\text{total}} = \mathcal{L}_{\text{pinball}} + \lambda_{\text{mass}} \mathcal{L}_{\text{mass}} + \lambda_{\text{neg}} \mathcal{L}_{\text{neg}} + \lambda_{\text{bound}} \mathcal{L}_{\text{bound}}
```

### 5.2 각 항의 정의

**Pinball loss** ($\mathcal{L}_{\text{pinball}}$): Model 2와 동일.

```math
\mathcal{L}_{\text{pinball}} = \sum_k w_k \cdot \text{Pinball}(y, \hat{q}_{\tau_k})
```

**Mass balance regularization** ($\mathcal{L}_{\text{mass}}$): 매 시간 스텝의 물수지 잔차를 패널티.

```math
\mathcal{L}_{\text{mass}} = \frac{1}{T} \sum_{t=1}^{T} \left( P_{\text{eff},t} - \text{ET}_t - Q_{\text{fast},t} - Q_{\text{slow},t} - \Delta S_{\text{soil},t} - \Delta S_{\text{fast},t} - \Delta S_{\text{slow},t} \right)^2
```

이 항은 conceptual core 내부에서 수식적으로는 자동 보장되지만, 수치 오차와 gradient flow 안정성을 위해 soft regularization으로 명시적으로 둔다.

**Non-negativity regularization** ($\mathcal{L}_{\text{neg}}$): 모든 storage와 flux가 음수가 되지 않도록.

```math
\mathcal{L}_{\text{neg}} = \frac{1}{T} \sum_{t=1}^T \sum_{s \in \mathcal{S}} \text{ReLU}(-s_t)^2
```

여기서 $\mathcal{S} = \{S_{\text{snow}}, S_{\text{soil}}, S_{\text{fast}}, S_{\text{slow}}, Q_{\text{fast}}, Q_{\text{slow}}\}$.

**Storage bounds regularization** ($\mathcal{L}_{\text{bound}}$): soil storage가 물리적 상한을 유지하도록.

```math
\mathcal{L}_{\text{bound}} = \frac{1}{T} \sum_{t=1}^T \text{ReLU}(S_{\text{soil},t} - S_{\text{soil,max}})^2
```

### 5.3 정규화 가중치 초기 설정

| 항 | 가중치 | 초기값 | 비고 |
|----|--------|--------|------|
| $\lambda_{\text{mass}}$ | mass balance | 0.1 | 수식상 자동 보장되므로 작게 시작 |
| $\lambda_{\text{neg}}$ | non-negativity | 0.5 | 음수 storage/flux는 물리적으로 불가 |
| $\lambda_{\text{bound}}$ | storage bounds | 0.1 | overflow는 이미 수식에서 처리하므로 보조 |

가중치는 첫 실험에서 위 값으로 고정하고, 필요하면 후속 ablation에서 sensitivity를 본다.

---

## 6. Model 1 / Model 2 / Model 3 비교에서 바뀌는 것

| 항목 | Model 1 | Model 2 | Model 3 |
|------|---------|---------|---------|
| `model` | `cudalstm` | `cudalstm` | `cudalstm_conceptual` (신규) |
| `head` | `regression` | `quantile` | `residual_quantile` (신규) |
| `loss` | `nse` | `pinball` | `pinball + physics_reg` |
| conceptual core | 없음 | 없음 | `flux_routed_core` (신규) |
| backbone size | 128 | 128 | **128** (동일) |
| dynamic inputs | 11개 | 11개 | **11개** (동일) |
| static attributes | 8개 | 8개 | **8개** (동일, 일부는 core에서도 사용) |
| split / dates | 동일 | 동일 | **동일** |
| quantiles | — | [0.5, 0.9, 0.95, 0.99] | **[0.5, 0.9, 0.95, 0.99]** |
| seed protocol | 3-seed | 3-seed | **3-seed** |

핵심: backbone, input, split, quantile set, optimizer budget은 모두 동일. 차이는 conceptual core 존재 여부와 head 구조뿐.

---

## 7. NeuralHydrology 통합 전략

### 7.1 신규 파일

```text
vendor/neuralhydrology/neuralhydrology/modelzoo/
├── flux_routed_core.py        # ConceptualCore class
├── cudalstm_conceptual.py     # CudaLSTMConceptual model class
└── (head.py 수정)             # ResidualQuantileHead 추가
```

### 7.2 CudaLSTMConceptual 클래스 구조

```python
class CudaLSTMConceptual(BaseModel):
    """CudaLSTM + FluxRoutedCore + ResidualQuantileHead"""

    module_parts = ['embedding_net', 'lstm', 'flux_head', 'conceptual_core', 'residual_head']

    def __init__(self, cfg):
        super().__init__(cfg)
        self.embedding_net = InputLayer(cfg)
        self.lstm = nn.LSTM(
            input_size=self.embedding_net.output_size,
            hidden_size=cfg.hidden_size,
        )
        self.dropout = nn.Dropout(p=cfg.output_dropout)
        self.flux_head = FluxHead(n_in=cfg.hidden_size)
        self.conceptual_core = FluxRoutedCore(cfg)
        self.residual_head = ResidualQuantileHead(
            n_in=cfg.hidden_size,
            quantiles=cfg.quantiles,
        )
        self._reset_parameters()

    def forward(self, data):
        x_d = self.embedding_net(data)
        lstm_output, (h_n, c_n) = self.lstm(input=x_d)
        lstm_output = lstm_output.transpose(0, 1)

        h_dropped = self.dropout(lstm_output)

        # Extract forcing for conceptual core
        precip = data['x_d']['Rainf']
        temp = data['x_d']['Tair']
        pet = data['x_d']['PotEvap']
        soil_depth = data['x_s']['soil_depth']  # static, per basin

        # Flux head: h_t → bounded fluxes
        fluxes = self.flux_head(h_dropped, ...)

        # Conceptual core: forcing + fluxes → base hydrograph + states
        core_out = self.conceptual_core(
            precip=precip, temp=temp, pet=pet,
            fluxes=fluxes, soil_depth=soil_depth,
        )

        # Residual quantile head: h_t + Q_base → quantiles
        pred = self.residual_head(h_dropped, core_out['q_base'])

        # Attach physics states for regularization loss
        pred.update({
            'internal_states': core_out['states'],
            'internal_fluxes': core_out['fluxes'],
            'q_base': core_out['q_base'],
        })
        return pred
```

### 7.3 Config 예시

```yaml
experiment_name: camelsh_hourly_model3_drbc_holdout_broad
model: cudalstm_conceptual
head: residual_quantile
loss: pinball_physics

quantiles: [0.5, 0.9, 0.95, 0.99]
quantile_loss_weights: [1.0, 1.0, 1.0, 1.0]

physics_reg:
  mass_balance_weight: 0.1
  nonnegativity_weight: 0.5
  storage_bounds_weight: 0.1

# Conceptual core settings
conceptual_core:
  temp_threshold: 0.0
  temp_transition_steepness: 2.0
  k_fast_range: [0.5, 48.0]
  k_slow_range: [48.0, 2000.0]
  snow_init: 0.0
  soil_init_fraction: 0.3
  fast_init: 0.0
  slow_init: 10.0

# Everything below is same as Model 1 / Model 2
hidden_size: 128
seq_length: 336
predict_last_n: 24
# ... (동일)
```

### 7.4 기존 vendor 코드 수정 범위

| 파일 | 변경 |
|------|------|
| `modelzoo/__init__.py` | `cudalstm_conceptual` 등록 |
| `modelzoo/head.py` | `ResidualQuantileHead` 추가 |
| `training/loss.py` | `pinball_physics` loss 함수 추가 |
| `utils/config.py` | `physics_reg`, `conceptual_core` config key 추가 |

---

## 8. 설계 선택의 근거와 대안

### 8.1 왜 flux 5개인가

| 선택된 flux | 왜 필요한가 | 제외된 대안 |
|-------------|-------------|-------------|
| $f_{\text{melt}}$ | snow storage 제어, snowmelt flood의 핵심 | degree-day factor를 시점별로 주는 것은 과도 |
| $f_{\text{ET}}$ | soil moisture drawdown, recession 영향 | PET 자체를 입력으로 쓰므로 fraction으로 충분 |
| $f_{\text{inf}}$ | fast vs slow partitioning, peak shape 결정 | curve number 등은 파라미터가 더 필요 |
| $k_{\text{fast}}$ | 첨두 timing과 magnitude | 고정하면 basin diversity를 못 잡음 |
| $k_{\text{slow}}$ | recession 속도 | 고정하면 baseflow 다양성을 못 잡음 |

5개를 넘기면 → "To bucket or not to bucket?"의 비판에 취약.
5개 미만이면 → routing coefficient가 빠져서 basin 다양성을 못 잡을 위험.

### 8.2 왜 residual quantile인가

대안 1: conceptual core → Q_base → 그 위에 별도 quantile head (pure add-on)
→ 문제: core가 deterministic이므로 q50 자체가 Q_base에 locked. 보정 여지가 없음.

대안 2: conceptual core를 아예 quantile-aware로 만들기 (5 storages × 4 quantiles)
→ 문제: 파라미터 폭증. 물수지 의미가 quantile마다 달라지는 비물리적 구조.

**선택: Q_base + learned residual** → 물리적 anchor를 유지하면서 tail을 열 수 있는 가장 parsimony한 구조.

### 8.3 왜 $Q_{\text{base}}$에 ε_50을 더하는가

Q_base는 순수 물수지 결과이므로 scaler, 단위, 분포 가정에서 약간의 systematic bias가 있을 수 있다. ε_50 (unbounded residual)은 이 bias를 보정한다. 만약 conceptual core가 완벽하다면 ε_50 → 0으로 수렴할 것이고, 그렇지 않으면 LSTM이 보정할 여지를 남긴다.

이것이 "physics가 anchor, AI가 보정"이라는 원칙의 구현이다.

---

## 9. 학습 진행 전략

### 9.1 Warm-up period

conceptual core의 storage를 안정화하기 위해 `warmup_period`를 둔다. 현재 `seq_length = 336` (14일) 중 처음 168시간 (7일)을 warmup으로 두고, 나머지 168시간에서만 loss를 계산한다.

다만 이렇게 하면 Model 1/2의 `predict_last_n = 24`와 공정 비교가 어려울 수 있으므로, 대안으로:
- `seq_length = 504` (21일)로 늘려서 warmup 168 + supervised 336 → predict_last_n 24는 동일 유지
- 또는 warmup은 loss 제외만 하고, 모든 모델에 동일하게 적용

이 부분은 구현 단계에서 ablation으로 확인한다.

### 9.2 초기 학습 안정화

physics regularization은 학습 초기에 gradient를 불안정하게 만들 수 있으므로:

1. 처음 5 epoch은 `λ_mass = λ_neg = λ_bound = 0`으로 두고 pinball loss만으로 학습
2. 5 epoch 이후 linear ramp-up으로 regularization 가중치를 점진적으로 올림
3. 10 epoch 이후 목표 가중치에 도달

이 전략은 LSTM이 먼저 합리적인 flux 범위를 학습한 뒤, physics 제약이 fine-tuning하는 효과를 준다.

---

## 10. 검증 계획

### 10.1 구현 검증 (단위 테스트)

1. **FluxHead bounds**: 출력이 항상 지정 범위 안에 있는지
2. **ConceptualCore mass balance**: $P_{\text{eff}} = \text{ET} + Q_{\text{fast}} + Q_{\text{slow}} + \Delta S$ 확인
3. **Non-negativity**: 모든 storage ≥ 0 확인
4. **Quantile ordering**: q50 ≤ q90 ≤ q95 ≤ q99 확인
5. **Gradient flow**: conceptual core를 통과해도 gradient가 vanish하지 않는지

### 10.2 실험 검증

1. Model 3 vs Model 2: 같은 split, 같은 seed, 같은 quantile set
2. **Flood-specific**: FHV, Peak-MAPE, Peak-Timing에서 Model 2 대비 이득이 있는지
3. **Basin generalization**: DRBC holdout에서 Model 2 대비 개선이 있는지
4. **Ablation**: physics regularization 유무 (λ = 0 vs λ > 0)
5. **States interpretability**: snow storage가 겨울에 증가하는지, soil이 건기에 감소하는지

---

## 11. 문서 정리

이 설계의 핵심을 한 문장으로 정리하면:

> Model 3는 CudaLSTM encoder가 5개의 bounded flux/coefficient만 제안하고, 고정된 물수지 방정식이 state update와 routing을 수행하며, 그 결과인 base hydrograph 위에 residual quantile head가 probabilistic tail을 여는 구조다.

이 설계는 (1) "To bucket or not to bucket?"의 비판을 수용해 LSTM이 conceptual model을 덮어쓰는 구조를 피하고, (2) Model 2의 probabilistic output 장점을 유지하면서, (3) physics-guided state/routing이 peak timing과 basin generalization에서 추가 이득을 줄 수 있는지를 future work로 검토할 수 있게 만든다.

---

## 관련 문서

- 현재 논문 범위의 두 모델 구조와 future-work 메모: [`architecture.md`](architecture.md)
- 연구 질문과 비교 가설: [`design.md`](design.md)
- 실행 규범과 config key: [`experiment_protocol.md`](experiment_protocol.md)
- quantile head 직관 설명: [`probabilistic_head_guide.md`](probabilistic_head_guide.md)
- hybrid 비판 문헌: "To bucket or not to bucket?" (Acuña Espinoza et al., HESS 2024)
- MC-LSTM extreme event 평가: Frame et al. (HESS, 2022)
