"""
rul_predictor.py
================
Machine Learning pipeline for Remaining Useful Life (RUL) prediction.

Features
--------
- Models: Random Forest Regressor & XGBoost Regressor
- Metrics: MAE, RMSE, R² Score, and NASA C-MAPSS asymmetric score (S)
- Evaluation: Full cycle-level & engine last-observed-cycle level
- Model serialization (save/load joblib models)
- Feature Importance extraction

Public API
----------
    RULPredictor(model_type, params)
    compute_nasa_score(y_true, y_pred) -> float
    evaluate_predictions(y_true, y_pred) -> dict[str, float]
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional, Tuple, Dict, List

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.config import (
    ENGINE_ID_COL,
    CYCLE_COL,
    RUL_COL,
    RUL_CAPPED_COL,
    RF_PARAMS,
    XGB_PARAMS,
    MODELS_RUL_DIR,
)

# Attempt XGBoost import with safe fallback
try:
    from xgboost import XGBRegressor
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False


def compute_nasa_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Compute the official NASA C-MAPSS asymmetric scoring function.

    Formula:
        d_i = y_pred_i - y_true_i
        s_i = exp(-d_i / 13) - 1   if d_i < 0 (early prediction / underestimation)
              exp(d_i / 10)  - 1   if d_i >= 0 (late prediction / overestimation)
        S = sum(s_i)

    Overestimating RUL is penalized more heavily than underestimating.

    Parameters
    ----------
    y_true : np.ndarray
        Ground truth RUL values.
    y_pred : np.ndarray
        Predicted RUL values.

    Returns
    -------
    float
        Total NASA score (lower is better).
    """
    diffs = y_pred - y_true
    scores = np.where(
        diffs < 0,
        np.exp(-diffs / 13.0) - 1.0,
        np.exp(diffs / 10.0) - 1.0,
    )
    return float(np.sum(scores))


def evaluate_predictions(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """
    Compute MAE, RMSE, R², and NASA asymmetric score.

    Parameters
    ----------
    y_true : np.ndarray
        True RUL values.
    y_pred : np.ndarray
        Predicted RUL values.

    Returns
    -------
    Dict[str, float]
        Dictionary containing metric names and values.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))
    nasa_score = compute_nasa_score(y_true, y_pred)

    return {
        "MAE": round(mae, 4),
        "RMSE": round(rmse, 4),
        "R2": round(r2, 4),
        "NASA_Score": round(nasa_score, 2),
    }


class RULPredictor:
    """
    RUL Prediction model wrapper for Random Forest & XGBoost.
    """

    def __init__(
        self,
        model_type: str = "xgboost",
        params: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize RULPredictor.

        Parameters
        ----------
        model_type : str
            'random_forest' or 'xgboost'.
        params : dict, optional
            Custom hyperparameters to pass to the underlying regressor.
        """
        self.model_type = model_type.lower()
        self.feature_names: List[str] = []
        self.target_col: str = RUL_CAPPED_COL

        if self.model_type == "random_forest":
            model_params = {**RF_PARAMS, **(params or {})}
            self.model = RandomForestRegressor(**model_params)
        elif self.model_type in ("xgboost", "xgb"):
            if HAS_XGBOOST:
                model_params = {**XGB_PARAMS, **(params or {})}
                self.model = XGBRegressor(**model_params)
            else:
                print("  [WARNING] XGBoost not installed. Falling back to GradientBoostingRegressor.")
                self.model_type = "gradient_boosting"
                gb_params = {
                    "n_estimators": 100,
                    "max_depth": 5,
                    "learning_rate": 0.05,
                    "random_state": 42,
                }
                gb_params.update(params or {})
                self.model = GradientBoostingRegressor(**gb_params)
        else:
            raise ValueError(f"Unsupported model_type: '{model_type}'. Choose 'random_forest' or 'xgboost'.")

    def _prepare_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Optional[pd.Series]]:
        """Separate feature columns X from target column y."""
        ignore_cols = {ENGINE_ID_COL, CYCLE_COL, RUL_COL, RUL_CAPPED_COL}
        feature_cols = [c for c in df.columns if c not in ignore_cols]

        X = df[feature_cols]

        y = None
        if RUL_CAPPED_COL in df.columns:
            y = df[RUL_CAPPED_COL]
        elif RUL_COL in df.columns:
            y = df[RUL_COL]

        return X, y

    def fit(self, train_df: pd.DataFrame) -> RULPredictor:
        """
        Train the model on feature DataFrame.

        Parameters
        ----------
        train_df : pd.DataFrame
            Engine feature DataFrame containing RUL labels.

        Returns
        -------
        RULPredictor
            Self instance.
        """
        X_train, y_train = self._prepare_features(train_df)
        if y_train is None:
            raise ValueError("Training DataFrame must contain 'RUL_capped' or 'RUL' column.")

        self.feature_names = list(X_train.columns)
        print(f"  [model] Training {self.model_type} on {len(X_train):,} samples with {len(self.feature_names)} features...")
        
        self.model.fit(X_train, y_train)
        print(f"  [model] Training completed successfully.")
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """
        Predict RUL values for feature DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            Feature DataFrame.

        Returns
        -------
        np.ndarray
            Predicted RUL array (clipped to >= 0).
        """
        X, _ = self._prepare_features(df)
        
        # Ensure column order matches training
        if self.feature_names:
            missing = set(self.feature_names) - set(X.columns)
            if missing:
                raise ValueError(f"Missing features in inference data: {missing}")
            X = X[self.feature_names]

        preds = self.model.predict(X)
        return np.clip(preds, 0.0, None)

    def evaluate(self, test_df: pd.DataFrame) -> Tuple[Dict[str, float], Dict[str, float], pd.DataFrame]:
        """
        Evaluate model performance on test set.

        Computes evaluation metrics at:
        1. Full cycle level (all test cycles)
        2. Final observed cycle per engine (standard C-MAPSS benchmark protocol)

        Returns
        -------
        Tuple[Dict, Dict, pd.DataFrame]
            - cycle_metrics dict
            - engine_last_cycle_metrics dict
            - engine_predictions_df DataFrame
        """
        X_test, y_true_cycle = self._prepare_features(test_df)
        preds_cycle = self.predict(test_df)

        cycle_metrics = evaluate_predictions(y_true_cycle.values, preds_cycle)

        # Evaluation at engine last cycle
        eval_df = test_df[[ENGINE_ID_COL, CYCLE_COL]].copy()
        eval_df["true_RUL"] = y_true_cycle.values
        eval_df["predicted_RUL"] = np.round(preds_cycle, 2)

        # Group by engine_id to get the last cycle for each engine
        last_cycles_idx = eval_df.groupby(ENGINE_ID_COL)[CYCLE_COL].idxmax()
        engine_last_df = eval_df.loc[last_cycles_idx].sort_values(ENGINE_ID_COL).reset_index(drop=True)

        last_cycle_metrics = evaluate_predictions(
            engine_last_df["true_RUL"].values,
            engine_last_df["predicted_RUL"].values
        )

        return cycle_metrics, last_cycle_metrics, engine_last_df

    def get_feature_importances(self) -> pd.DataFrame:
        """
        Get sorted feature importances.

        Returns
        -------
        pd.DataFrame
            DataFrame with 'feature' and 'importance' columns.
        """
        if not hasattr(self.model, "feature_importances_"):
            return pd.DataFrame(columns=["feature", "importance"])

        imp = self.model.feature_importances_
        df_imp = pd.DataFrame({
            "feature": self.feature_names,
            "importance": imp
        }).sort_values("importance", ascending=False).reset_index(drop=True)

        return df_imp

    def save(self, filepath: Union[str, Path]) -> Path:
        """Save model to disk using joblib."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        save_dict = {
            "model_type": self.model_type,
            "feature_names": self.feature_names,
            "model": self.model,
        }
        joblib.dump(save_dict, filepath)
        print(f"  [model] Model saved to {filepath}")
        return filepath

    @classmethod
    def load(cls, filepath: Union[str, Path]) -> RULPredictor:
        """Load saved model from disk."""
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Model file not found: {filepath}")

        saved_dict = joblib.load(filepath)
        instance = cls(model_type=saved_dict["model_type"])
        instance.feature_names = saved_dict["feature_names"]
        instance.model = saved_dict["model"]
        return instance
