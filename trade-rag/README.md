# trade-rag

佳必琪 AI 工程師實習 Demo：把自己的 **台股 SNR 紙上交易規則**做成可檢索手冊（RAG）。

問答必須引用「檔名＋段落」。不是券商下單系統。

## 資料夾

| 路徑 | 用途 |
| --- | --- |
| `data/rules/` | 規則文件（從 `snr_backtest` README／邏輯抽樣） |
| `data/eval/` | 評測題 |
| `src/` | 之後放 ingest／retrieve／answer／UI |
| `indexes/` | FAISS 輸出（可重建，通常不進 Git） |

## 第一批規則

- RULE-001 時序與硬限制（盤中／夜盤）
- RULE-002 新聞熱度與預算池
- RULE-003 硬關條件
- RULE-004 零股 5→1
- RULE-005 進出場摘要

來源專案：`C:\Users\AUSER\Desktop\trade\snr_backtest`
