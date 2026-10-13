# ML prediction on NASA discharge data

Source: [1e1fc5c CSV export](https://raw.githubusercontent.com/fmardero/battery_aging/1e1fc5c5b1a7dd3d44db0df0c429b6e893d4692c/discharge.csv), citing [NASA battery aging](https://data.nasa.gov/dataset/li-ion-battery-aging-datasets). BatteryLake catalog reference: dataset_01.

169,766 time-series rows → 636 discharge cycles. Train: B0005/B0006/B0007 (504 cycles). Test: B0018 (132 cycles), never used for fitting.

Random Forest: 80 trees, leaf size 4, max depth 9, seed 42. Features use only the first 600 seconds of discharge plus cycle number. Full-cycle capacity, elapsed full-discharge duration, future cycles and EOL labels are excluded from inputs.

| Task | Test MAE | Test RMSE | Constant baseline MAE |
|---|---:|---:|---:|
| SOH (percentage points) | 2.409 | 3.042 | 7.402 |
| RUL (cycles) | 10.731 | 14.095 | 21.259 |

Four NASA cells only. No hyperparameter tuning on test data. RUL uses retrospective first observed 80% crossing. Not valid for arbitrary chemistries or synthetic rack cells.

SOH is capacity / first observed capacity. RUL is evaluated only through the first observed crossing; post-EOL rows remain in the replay but are not included in RUL metrics.

No third-party pickle/joblib was loaded. Our trained forests are exported as JSON and run in the server using standard Python.

![ML replay dashboard](dashboard-ml.png)

[Prediction CSV](ml-cycle-predictions.csv) · [Metrics and replay JSON](ml-results.json)

Reproduce: `python -m pip install -r requirements-ml.txt` then `python -B train_ml.py`.