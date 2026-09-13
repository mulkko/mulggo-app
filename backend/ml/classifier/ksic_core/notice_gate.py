# -*- coding: utf-8 -*-
"""2차 ML 게이트(공고단위 메타분류기)의 피처 빌더.

학습(scripts/23, scripts/36)과 로딩(joblib.load 하는 쪽, 향후 predict.py) 양쪽이
반드시 이 모듈에서 import해야 한다 — pickle은 클래스를 정의된 모듈 경로로
저장하므로, 학습 스크립트 안에 클래스를 두면(__main__) 다른 곳에서 못 불러온다.

피처 정의는 scripts/22_build_notice_dataset.py가 만드는 notice_v2.csv 컬럼과
반드시 일치해야 한다.
"""
from __future__ import annotations

from scipy.sparse import hstack, csr_matrix
from sklearn.preprocessing import OneHotEncoder

SPAN_LABELS = ["지원대상", "지원제외", "제외예외", "제3자", "참고예시", "무관"]
CAT_COLS = ["rule_stage", "rule_conf", "rule_status", "표1유형", "표2유형", "추출상태"]
NUM_COLS = ["rule_n_codes", "rule_has_excluded", "원문길이", "n_spans", "has_support_span",
            "n_trig_code"] + [f"n_{l}" for l in SPAN_LABELS]


class FeatureBuilder:
    """규칙피처 전용(mode='rule'). scripts/23 여러 모드 중 배포모델(B)이 쓰는 것만."""

    def fit(self, d):
        self.ohe = OneHotEncoder(handle_unknown="ignore")
        self.ohe.fit(d[CAT_COLS].astype(str).values)
        self.num_mean = d[NUM_COLS].mean()
        self.num_std = d[NUM_COLS].std().replace(0, 1)
        return self

    def transform(self, d):
        Xcat = self.ohe.transform(d[CAT_COLS].astype(str).values)
        Xnum = csr_matrix(((d[NUM_COLS] - self.num_mean) / self.num_std).values)
        return hstack([Xcat, Xnum]).tocsr()
