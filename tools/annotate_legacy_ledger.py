"""Annotate legacy CLAIM_LEDGER.csv with validity classifications."""
import os
import pandas as pd

def annotate_legacy_ledger():
    src_path = "audit/CLAIM_LEDGER.csv"
    out_path = "audit/CLAIM_LEDGER_LEGACY_ANNOTATED.csv"
    
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"Missing {src_path}")
        
    df_ledger = pd.read_csv(src_path)
    df_raw = pd.read_csv("results/raw_results.csv")
    df_v5 = pd.read_csv("results/confirmatory/heldout_v5_results.csv")
    
    annotations = []
    matched_counts = []
    
    for idx, row in df_ledger.iterrows():
        filt = str(row["filter"]).strip()
        cid = row["claim_id"]
        
        # Test if query executes
        try:
            m_raw = len(df_raw.query(filt))
        except Exception:
            m_raw = -1
            
        try:
            m_v5 = len(df_v5.query(filt))
        except Exception:
            m_v5 = -1
            
        if m_raw == -1 and m_v5 == -1:
            annotation = "FILTER_ERROR"
            counts = "Syntax Error / Missing Columns"
        elif m_raw == 0 and m_v5 == 0:
            annotation = "INVALID_EMPTY_FILTER"
            counts = "raw: 0, v5: 0 (Grid mismatch: n_robots=8, n_tasks=30 vs nominal 4/15)"
        elif m_raw > 0 or m_v5 > 0:
            annotation = "VALID"
            counts = f"raw: {max(0, m_raw)}, v5: {max(0, m_v5)}"
        else:
            annotation = "INVALID_EMPTY_FILTER"
            counts = f"raw: {m_raw}, v5: {m_v5}"
            
        annotations.append(annotation)
        matched_counts.append(counts)
        
    df_ledger["audit_annotation"] = annotations
    df_ledger["matched_population_details"] = matched_counts
    
    df_ledger.to_csv(out_path, index=False)
    print(f"Wrote annotated legacy ledger to {out_path} ({len(df_ledger)} claims annotated).")
    for idx, row in df_ledger.iterrows():
        print(f"  {row['claim_id']:10s} | {row['audit_annotation']:20s} | {row['matched_population_details']}")

if __name__ == "__main__":
    annotate_legacy_ledger()
