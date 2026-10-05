"""Genuine CPU sequence models with chronological, purged evaluation."""
from __future__ import annotations
import time
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from .validation import chronological_purged_split


def _run_sequence_alpha(payload=None):
    import torch
    from torch import nn
    from .panel import load_context, make_feature_panel, numeric_xy
    from .common import response, summary
    request = payload or {}
    names = request.get("architectures", ["patchtst"])
    supported = {"patchtst", "itransformer", "lstm", "mlp"}
    if not isinstance(names, list) or not names or set(names) - supported:
        raise ValueError(f"Supported sequence architectures: {sorted(supported)}")
    seed = int(request.get("random_seed", 7))
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    ctx = load_context(request)
    horizon = int(request.get("prediction_horizon", 5))
    panel, target = make_feature_panel(ctx, horizon)
    features, target = numeric_xy(panel, target)
    window = int(request.get("sequence_length", 63))
    patch = int(request.get("patch_length", 21))
    heads = int(request.get("attention_heads", 4))
    depth = int(request.get("transformer_depth", 2))
    dropout = float(request.get("dropout_rate", .1))
    epochs = int(request.get("epochs", 15))
    if not 1 <= epochs <= 100 or not 1 <= depth <= 4 or heads not in {2, 4, 8} or not 0 <= dropout < .6:
        raise ValueError("Invalid neural training parameters")
    if not 5 <= window <= 252 or patch < 1 or patch > window:
        raise ValueError("Invalid sequence or patch length")
    train, test = chronological_purged_split(panel, horizon, int(request.get("embargo_period", 5)))
    features = panel[list(features.columns)].replace([np.inf, -np.inf], np.nan)
    imputer = SimpleImputer(strategy="median")
    training_values = imputer.fit_transform(features.iloc[train])
    scaler = StandardScaler().fit(training_values)
    values = scaler.transform(imputer.transform(features)).astype(np.float32)
    sequences, labels, positions = [], [], []
    for _, group in panel.groupby("ticker", sort=True):
        indices = group.index.to_numpy()
        for i in range(window - 1, len(indices)):
            sample = indices[i-window+1:i+1]
            sessions = ctx.returns.index.get_indexer(pd.to_datetime(panel.loc[sample, "date"]))
            if np.any(np.diff(sessions) != 1):
                continue
            sequences.append(values[sample])
            labels.append(float(target.iloc[indices[i]]))
            positions.append(int(indices[i]))
    if not sequences:
        raise ValueError("Insufficient contiguous observations for sequence training")
    X, y, positions = np.asarray(sequences), np.asarray(labels, dtype=np.float32), np.asarray(positions)
    train_mask, test_mask = np.isin(positions, train), np.isin(positions, test)
    if train_mask.sum() < 50 or test_mask.sum() < 20:
        raise ValueError("Insufficient purged sequence samples")
    train_x, test_x = torch.from_numpy(X[train_mask]), torch.from_numpy(X[test_mask])
    train_y = torch.from_numpy(y[train_mask])
    channels = X.shape[2]
    hidden = 32

    class Encoder(nn.Module):
        def __init__(self, architecture):
            super().__init__()
            self.architecture = architecture
            if architecture == "patchtst":
                self.embedding = nn.Linear(patch, hidden)
                self.position = nn.Parameter(torch.zeros(1, window // patch, hidden))
                self.head = nn.Linear(hidden * channels, 1)
            elif architecture == "itransformer":
                self.embedding = nn.Linear(window, hidden)
                self.head = nn.Linear(hidden * channels, 1)
            elif architecture == "lstm":
                self.lstm = nn.LSTM(channels, hidden, depth, batch_first=True,
                                    dropout=dropout if depth > 1 else 0.)
                self.head = nn.Linear(hidden, 1)
            else:
                self.mlp = nn.Sequential(nn.Flatten(), nn.Linear(window * channels, 64),
                                        nn.GELU(), nn.Dropout(dropout), nn.Linear(64, 1))
            if architecture in {"patchtst", "itransformer"}:
                layer = nn.TransformerEncoderLayer(hidden, heads, 64, dropout,
                                                    batch_first=True, activation="gelu")
                self.encoder = nn.TransformerEncoder(layer, depth, enable_nested_tensor=False)
        def forward(self, x):
            if self.architecture == "mlp":
                return self.mlp(x).squeeze(-1)
            if self.architecture == "lstm":
                sequence, _ = self.lstm(x)
                return self.head(sequence[:, -1]).squeeze(-1)
            variables = x.transpose(1, 2)
            if self.architecture == "patchtst":
                patches = variables[:, :, -(window // patch) * patch:].unfold(-1, patch, patch)
                tokens = self.embedding(patches).reshape(-1, window // patch, hidden) + self.position
                encoded = self.encoder(tokens).mean(1).reshape(len(x), -1)
            else:
                encoded = self.encoder(self.embedding(variables)).reshape(len(x), -1)
            return self.head(encoded).squeeze(-1)

    comparisons, forecasts, history = [], [], []
    dates = pd.to_datetime(panel["date"].iloc[positions[test_mask]]).reset_index(drop=True)
    for architecture in names:
        torch.manual_seed(seed)
        model = Encoder(architecture)
        optimizer = torch.optim.AdamW(model.parameters(), lr=.001)
        start = time.perf_counter()
        for epoch in range(epochs):
            model.train()
            order = rng.permutation(len(train_x))
            loss_sum = 0.
            for offset in range(0, len(order), 128):
                batch = order[offset:offset+128]
                optimizer.zero_grad()
                loss = nn.functional.mse_loss(model(train_x[batch]), train_y[batch])
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.)
                optimizer.step()
                loss_sum += float(loss.detach()) * len(batch)
            history.append({"architecture": architecture, "epoch": epoch + 1,
                            "training_mse": loss_sum / len(train_x)})
        duration = time.perf_counter() - start
        model.eval()
        with torch.no_grad():
            pred = np.concatenate([model(batch).numpy() for batch in test_x.split(256)])
        actual = y[test_mask]
        monthly = pd.DataFrame({"date": dates, "prediction": pred, "actual": actual})
        ics = []
        from .performance import fast_spearman_ic
        for month, group in monthly.groupby(monthly.date.dt.to_period("M")):
            ic = fast_spearman_ic(group.prediction.to_numpy(), group.actual.to_numpy())
            ics.append(ic)
            forecasts.append({"architecture": architecture, "month": str(month), "ic": ic})
        comparisons.append({"architecture": architecture,
            "spearman_ic": fast_spearman_ic(pred, actual),
            "monthly_ic_ir": float(np.mean(ics) / np.std(ics, ddof=1)) if len(ics) > 1 and np.isfinite(ics).all() and np.std(ics, ddof=1) > 1e-12 else None,
            "mae": float(np.mean(np.abs(pred - actual))), "training_time_seconds": duration,
            "train_samples": int(train_mask.sum()), "test_samples": int(test_mask.sum())})
    return response("12", [summary("Models", len(names)), summary("Test samples", int(test_mask.sum()))],
        charts={"architecture_comparison": comparisons, "monthly_oos_ic": forecasts, "training_loss": history},
        tables={"architecture_comparison": comparisons},
        meta={"training": "actual_pytorch_cpu", "validation": "chronological_purged_holdout",
              "normalization": "training_only", "missing_feature_policy": "training_median_imputation; quote gaps never imputed", "as_of_date": str(ctx.closes.index.max()),
              "architecture_scope": "Channel-independent patch encoder; inverted variable-token encoder; LSTM; MLP. TFT/Mamba excluded.",
              "attribution": "Attention and integrated-gradient outputs excluded until implemented"})


# PyTorch initialization uses global RNG state; serialize requests for reproducibility.
import threading
_TRAINING_LOCK = threading.Lock()

def run_sequence_alpha(payload=None):
    with _TRAINING_LOCK:
        return _run_sequence_alpha(payload)
