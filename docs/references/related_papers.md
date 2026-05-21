# 관련 논문 목록

> **연구 주제**: Multi-basin LSTM 기반 수문 예측에서 극한 홍수 첨두 과소추정 감소 — Deterministic vs. Probabilistic quantile 비교

---

## 1. Multi-basin LSTM & 홍수 첨두 과소추정

### ⭐ 핵심 논문

| 제목 | 저자 | 연도 | 링크 |
|------|------|------|------|
| **Does Multiple Basin Training Strategy Guarantee Superior Machine Learning Performance for Streamflow Predictions in Gaged Basins?** | Tran, Nguyen, Kim, Ivanov | 2025 | [EGUsphere](https://egusphere.copernicus.org/preprints/2025/egusphere-2025-769/) |
| **Deep learning rainfall–runoff predictions of extreme events** | Frame, Kratzert, Klotz, Gauch et al. | 2022 | [HESS](https://hess.copernicus.org/articles/26/3377/2022/hess-26-3377-2022.html) |
| **Improving Cross-Basin Flood Prediction in Data-Scarce Regions using Differentiable Hydrological Modelling and Transfer Learning** | Chai, Ouyang, Gu et al. | 2025 (preprint) | [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6215488) |
| **Towards Universal Runoff Forecasting: A KAN-WLSTM Framework for Robust Multi-Basin Hydrological Modeling** | Sai, Liu, Wang | 2025 | [Water/MDPI](https://www.mdpi.com/2073-4441/17/21/3152) |

> **읽기 우선 추천**: Tran et al. (2025)은 multi-basin training이 peak flow 과소추정을 악화시킬 수 있다는 점을 직접 다루며 연구 가설과 가장 직접적으로 연결됨. Frame et al. (2022)은 LSTM 극단값 예측의 benchmark 역할.

---

## 2. Probabilistic LSTM & Quantile 예측

### ⭐ 핵심 논문

| 제목 | 저자 | 연도 | 링크 |
|------|------|------|------|
| **The need for uncertainty: why probabilistic LSTMs are key to improving flood predictions and enabling learned warning rules** | Baste, Lerch, Klotz, Loritz | 2026 (preprint) | [EGUsphere](https://egusphere.copernicus.org/preprints/2026/egusphere-2026-469/) |
| **Bayesian LSTM with stochastic variational inference for estimating model uncertainty in process-based hydrological models** | Li, Marshall, Liang, Sharma | 2021 | [WRR](https://agupubs.onlinelibrary.wiley.com/doi/abs/10.1029/2021WR029772) |
| **A probabilistic machine learning framework for daily extreme events forecasting** | Sattari, Foroumandi, Gavahi et al. | 2025 | [Expert Systems](https://www.sciencedirect.com/science/article/pii/S0957417424028719) |
| **Uncertainty quantification for hydrological models based on neural networks: the dropout ensemble** | Althoff, Rodrigues, Bazame | 2021 | [Springer](https://link.springer.com/article/10.1007/s00477-021-01980-8) |

> **읽기 우선 추천**: Baste et al. (2026)은 연구 방향과 거의 동일한 질문을 던지는 최신 preprint. Li et al. (2021)은 Bayesian 접근으로 uncertainty 추정하는 방법론 논문.

---

## 3. Pinball Loss & Calibration & Coverage 평가

| 제목 | 저자 | 연도 | 링크 |
|------|------|------|------|
| **Probabilistic individual load forecasting using pinball loss guided LSTM** | Wang, Gan, Sun et al. | 2019 | [Applied Energy](https://www.sciencedirect.com/science/article/pii/S0306261918316465) |
| **A New Loss Function for Enhancing Peak Prediction in Time Series Data with High Variability** | Hajiabbasi Somehsaraie et al. | 2025 | [Forecasting/MDPI](https://www.mdpi.com/2571-9394/7/4/75) |
| **Quantile regression neural networks: Implementation in R and application to precipitation downscaling** | Cannon | 2011 | [Computers & Geosciences](https://www.sciencedirect.com/science/article/pii/S009830041000292X) |

> **읽기 우선 추천**: Hajiabbasi Somehsaraie et al. (2025)은 pinball loss를 이용해 peak 예측 개선을 직접 다루는 논문으로 연구와 매우 관련성이 높음.

---

## 4. CAMELS & Large-Sample Hydrology (기반 논문)

| 제목 | 저자 | 연도 | 링크 |
|------|------|------|------|
| **Rainfall–runoff modelling using long short-term memory (LSTM) networks** | Kratzert, Klotz, Brenner et al. | 2018 | [HESS](https://hess.copernicus.org/articles/22/6005/2018/) |
| **Towards learning universal, regional, and local hydrological behaviors via machine learning** | Kratzert, Klotz, Shalev et al. | 2019 | [HESS](https://hess.copernicus.org/articles/23/5089/2019/) |
| **Toward improved predictions in ungauged basins: Exploiting the power of machine learning** | Kratzert, Klotz, Herrnegger et al. | 2019 | [WRR](https://agupubs.onlinelibrary.wiley.com/doi/abs/10.1029/2019wr026065) |
| **HESS Opinions: Never train a Long Short-Term Memory (LSTM) network on a single basin** | Kratzert, Gauch, Klotz et al. | 2024 | [HESS](https://hess.copernicus.org/articles/28/4187/2024/) |
| **A note on leveraging synergy in multiple meteorological data sets with deep learning** | Kratzert, Klotz, Hochreiter et al. | 2021 | [HESS](https://hess.copernicus.org/articles/25/2685/2021/) |

---

## 5. Regional Holdout / PUB (Prediction in Ungauged Basins)

| 제목 | 저자 | 연도 | 링크 |
|------|------|------|------|
| **Continuous streamflow prediction in ungauged basins: LSTMs clearly outperform traditional hydrological models** | Arsenault, Martel, Brunet et al. | 2023 | [HESS](https://hess.copernicus.org/articles/27/139/2023/) |
| **Generalization of an Encoder-Decoder LSTM model for flood prediction in ungauged catchments** | Zhang, Ragettli, Molnar et al. | 2022 | [Journal of Hydrology](https://www.sciencedirect.com/science/article/pii/S0022169422011477) |
| **Toward improved deep learning-based regionalized streamflow modeling: Exploiting basin similarity** | Xu, Li, Hu et al. | 2025 | [Environmental Modelling & Software](https://www.sciencedirect.com/science/article/pii/S1364815225000581) |

---

## 6. Physics-Informed / Differentiable Hydrology (후속 참고)

| 제목 | 저자 | 연도 | 링크 |
|------|------|------|------|
| **Physics-informed, differentiable hydrologic models for capturing unseen extreme events** | Song, Sawadekar, Frame et al. | 2025 (preprint) | [ESSOAr](https://essopenarchive.org/doi/full/10.22541/essoar.172304428.82707157) |
| **The suitability of differentiable, physics-informed ML hydrologic models for ungauged regions** | Feng, Beck, Lawson et al. | 2023 | [HESS](https://hess.copernicus.org/articles/27/2357/2023/) |

---

## 검색 키워드 (재현용)

```
multi-basin LSTM flood peak underestimation streamflow prediction
probabilistic quantile LSTM hydrological prediction uncertainty estimation
CAMELS dataset deep learning streamflow regional generalization
extreme flood event prediction neural network peak flow bias
prediction in ungauged basins PUB regional holdout LSTM generalization
quantile regression neural network streamflow uncertainty calibration coverage
NeuralHydrology LSTM static attributes physics-informed hydrological model
Kratzert LSTM rainfall runoff CAMELS large sample hydrology
pinball loss interval score probabilistic streamflow forecast evaluation
```
