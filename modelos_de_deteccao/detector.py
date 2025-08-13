# -*- coding: utf-8 -*-
import can, time, json, joblib, numpy as np, pandas as pd
from collections import defaultdict
from pathlib import Path

CHANNEL = "can0"

def entropy(bytes_like):
    if not bytes_like:
        return 0.0
    arr = np.frombuffer(bytes(bytes_like), dtype=np.uint8)
    counts = np.bincount(arr, minlength=256)
    probs = counts[counts > 0] / arr.size
    return float(-(probs * np.log2(probs)).sum())

def choose_model():
    print("Selecione o modelo:")
    print("  1) One-Class SVM (OCSVM)")
    print("  2) Isolation Forest (IForest)")
    print("  3) K-Means")
    opt = input("Opção [1/2/3]: ").strip()
    return {"1":"ocsvm","2":"iforest","3":"kmeans"}.get(opt, "ocsvm")

def load_bundle(kind: str):
    if kind == "ocsvm":
        pkl = Path("ocsvm.pkl"); thr = Path("ocsvm_thresh.json")
    elif kind == "iforest":
        pkl = Path("iforest.pkl"); thr = Path("iforest_thresh.json")
    else:
        pkl = Path("kmeans.pkl"); thr = Path("kmeans_thresh.json")
    if not pkl.exists():
        raise SystemExit(f"Modelo não encontrado: {pkl}")
    obj = joblib.load(pkl)
    cfg = {}
    if thr.exists():
        try:
            cfg = json.loads(thr.read_text())
        except Exception:
            cfg = {}
    return obj, cfg

def get_feature_cols(model_or_bundle, default_cols=("dlc","delta_time","entropy")):
    # tenta detectar colunas usadas no treino
    if isinstance(model_or_bundle, dict):
        cols = model_or_bundle.get("feature_names")
        if cols: return list(cols)
        pipe = model_or_bundle.get("pipeline")
        if pipe is not None and hasattr(pipe, "feature_names_in_"):
            return list(pipe.feature_names_in_)
    else:
        if hasattr(model_or_bundle, "feature_names_in_"):
            return list(model_or_bundle.feature_names_in_)
    return list(default_cols)

def decide_rule(kind: str, cfg: dict):
    rule = (cfg.get("rule") or "").lower()
    thr  = float(cfg.get("threshold", -1.0 if kind in ("ocsvm","iforest") else 1e9))
    # regras do JSON (se fornecidas)
    if "distance" in rule and ">=" in rule:
        return ("distance", thr, lambda metric,thr: metric >= thr, "dmin")
    if "-score" in rule and ">=" in rule:
        return ("negscore", thr, lambda metric,thr: metric >= thr, "-score")
    if "score" in rule and "<" in rule:
        return ("score", thr, lambda metric,thr: metric < thr, "score")
    # padrões por modelo
    if kind in ("ocsvm","iforest"):
        return ("score", thr, lambda metric,thr: metric < thr, "score")
    else:
        return ("distance", thr, lambda metric,thr: metric >= thr, "dmin")

def main():
    kind = choose_model()
    obj, cfg = load_bundle(kind)
    cols = get_feature_cols(obj)
    print(f"Modelo selecionado: {kind} | colunas: {cols}")

    # prepara funções por tipo
    scaler = None; kmeans = None; pipe = None; estimator = None

    if isinstance(obj, dict):
        scaler = obj.get("scaler")
        kmeans = obj.get("kmeans")
        pipe   = obj.get("pipeline")
        estimator = obj.get("pipeline") or obj.get("model") or obj.get("estimator")
    else:
        estimator = obj

    # regra de decisão
    mode, THRESH, is_anom_fn, metric_name = decide_rule(kind, cfg)
    print(f"Threshold={THRESH} | regra: {('distance>=thr' if mode=='distance' else ('-score>=thr' if mode=='negscore' else 'score<thr'))}")

    # bus
    bus = can.interface.Bus(channel=CHANNEL, bustype="socketcan")
    last_ts_by_id = defaultdict(lambda: None)

    print("Detector online. Ctrl+C para sair.")
    try:
        while True:
            msg = bus.recv(timeout=1.0)
            if msg is None:
                continue

            now = msg.timestamp if getattr(msg, "timestamp", None) else time.time()
            can_id = msg.arbitration_id
            data   = bytes(msg.data)
            dlc    = len(data)

            last = last_ts_by_id[can_id]
            dt = (now - last) if last is not None else 0.0
            last_ts_by_id[can_id] = now
            H = entropy(data)

            X = pd.DataFrame([[dlc, dt, H]], columns=cols)

            metric = None

            if kind == "kmeans":
                if pipe is not None:
                    # pipeline (ex.: scaler + kmeans)
                    try:
                        dists = pipe.transform(X)          # matriz de distâncias
                        metric = float(np.min(dists, axis=1)[0])
                    except Exception as e:
                        raise SystemExit(f"Pipeline KMeans não suporta transform(): {e}")
                else:
                    if kmeans is None:
                        raise SystemExit("kmeans.pkl não contém 'kmeans' (e nem 'pipeline').")
                    if scaler is not None:
                        Xs = scaler.transform(X)
                    else:
                        Xs = X.values
                    dists = kmeans.transform(Xs)
                    metric = float(np.min(dists, axis=1)[0])

            elif kind in ("ocsvm","iforest"):
                model = estimator
                if hasattr(model, "score_samples"):
                    s = float(model.score_samples(X)[0])
                else:
                    s = float(model.decision_function(X)[0])
                metric = (-s) if mode == "negscore" else s

            else:
                raise SystemExit("Tipo de modelo desconhecido.")

            is_anom = is_anom_fn(metric, THRESH)

            payload_hex = " ".join(f"{b:02X}" for b in data)
            base = (f"({now:.6f}) can0 {can_id:03X} [{dlc}] {payload_hex} "
                    f"dt={dt*1000:.3f}ms H={H:.3f} {metric_name}={metric:.4f} thr={THRESH:.4f}")
            print(("ALERTA:" if is_anom else "ok    :"), base)

    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
